import ConfigParser
import json
import syslog
from jwcrypto import jwk, jwt

from shared import GlobalConfig, opaque_identifier, opaque_integer, opaque_mix, specific_cookie


syslog.openlog(ident='constantina.token')


class ConstantinaKeypair:
    """
    Constantina Keypair.

    All cookies issued by Constantina are JWE, for purposes of both integrity
    of cookie data, and obfuscation of the cookie purpose to disk forensics.
    This interface allows for management of keys in arbitrary config sections,
    and for doing validation of incoming JWE tokens.

    Each token uses both a signing keypair and an encryption keypair. As these
    tokens are validated, we may need to generate updated signing or encryption
    keys, so there are a number of supporting methods for this behavior here.

    section might be "current" or "last" when dealing with auth keypairs, or 
    a preference_id, when dealing with settings keys.

    To not leak how much time it takes to generate multiple keypair objects, 
    specify the time value as an input prior to creating multiples of these.
    """
    def __init__(self, config_file, section, time=jwt.time.time()):
        self.config_file = config_file
        self.section = section
        self.time = time

        self.__read_config(config_file)
        self.__set_defaults(section)

        # TODO: define init operations.
        # Get the config file section. If it doesn't exist, try and make the keypair

    def __read_config(self, config_file):
        self.config = ConfigParser.SafeConfigParser()
        self.config_path = GlobalConfig.get('paths', 'config_root')
        self.config.read(self.config_path + "/" + self.config_file)
        self.shadow = ConfigParser.SafeConfigParser()
        self.shadow.read(self.config_path + "/shadow.ini")

    def __set_defaults(self, section):
        self.key_format = self.shadow.get("defaults", "key_format")
        self.key_size = self.shadow.getint("defaults", "key_size")
        self.sign = self.__read_key("sign", self.section)
        self.encrypt = self.__read_key("encrypt", self.section)
        self.lifetime = self.shadow.getint("key_settings", "lifetime")
        self.sunset = self.shadow.getint("key_settings", "sunset")
        self.time = int(jwt.time.time())    # Don't leak multiple timestamps
        self.iat = {}

    def __read_key(self, key_type, section):
        """
        Read the desired key from the configuration file, and load it as
        a JWK for purpose of signing or encryption. This tries to load the
        exact parameters from the config file into their equivalent places
        in the JWK object. Namely, the k value goes in _key, and all the
        other ones of interest go in _params.
        Any objects that don't go into the JWK object get removed,
        including the date value we track separately.
        Persist the JWK key itself as key_type (either self.encrypt or self.sign)
        """
        jwk_data = {}
        exclude = ["date"]
        for dict_key, value in self.config.items(section):
            jwk_data[dict_key] = value
        for field in exclude:
            del jwk_data[field]
        setattr(self, key_type, jwk.JWK(**jwk_data))
        self.iat[key_type] = self.config.get(section, "date")
        return getattr(self, key_type)   # Read into the object, but also return it

    def __write_key(self, key_type, section, mode="current"):
        """
        Given a keyname, generate the key and write it to the config file.
        key_type here is either "sign" or "encrypt".

        Supports two modes:
           - current: just create a token dated to the current time
           - backdate: token is dated (ctime - sunset) to pre-age it.
        """
        setattr(self, key_type, jwk.JWK.generate(kty=self.key_format, size=self.key_size))
        # Whatever key properties exist, set them in the config
        data = getattr(self, key_type).__dict__
        for dict_key in data['_key'].keys():
            self.config.set(section, dict_key, data['_key'][dict_key])
        for dict_key in data['_params'].keys():
            self.config.set(section, dict_key, data['_params'][dict_key])
        # When did we create this key? When the class was instant'ed, unless
        # we're just generating the tokens and the "last" token needs to be
        # backdated so it only lasts half the configured lifetime.
        self.iat[key_type] = self.time
        self.config.set(section, "date", str(self.iat[key_type]))
        # syslog.syslog("iat: %d time: %d sunset: %d" % (self.iat[key_type]], self.time, self.sunset))
        if mode == "backdate":
            self.config.set(section, "date", str(self.iat[key_type] - self.sunset))

    def __regen_key(self, key_type, section, mode="current"):
        """
        Check the date associated with this key in the config file.
        If the key has expired, regenerate it (write a totally new key).
        """
        if self.config.get(section, "date") == '':
            self.__write_key(key_type, section, mode)
        else:
            keydate = self.config.getint(section, "date")
            if self.time > (keydate + self.lifetime):
                self.__write_key(key_type, section, mode)

    def regen_keypair(self, section, mode):
        """
        If the datestamps on either member of a keypair have expired, 
        generate new keys.
        """
        for key_type in ["sign", "encrypt"]:
            self.__regen_key(key_type, section, mode)

    def check_token(self, token):
        """
        Process a JWE settings token from a user cookie. If all the validation works,
        self.token becomes a valid JWT, and return True.
        If any part of this fails, do not set a cookie and return False.
        """
        try:
            decrypted = jwt.JWT(key=self.encrypt, jwt=token)
            validated = jwt.JWT(key=self.sign, jwt=decrypted.claims)
            return validated
        except:
            return False