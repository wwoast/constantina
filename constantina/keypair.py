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

    key_id might be "current" or "last" when dealing with auth keypairs, or
    a preference_id, when dealing with settings keys.

    To not leak how much time it takes to generate multiple keypair objects,
    specify the time value as an input prior to creating multiples of these.
    """
    def __init__(self, config_file, key_id, stamp="current", time=jwt.time.time()):
        self.config_file = config_file
        self.key_id = key_id
        self.stamp = stamp   # Backdate key issue time, or make it current?
        self.time = time     # The timestamp used if we set keys.

        self.__read_config(config_file)
        self.__set_defaults(key_id)

    def __read_config(self, config_file):
        self.config = ConfigParser.SafeConfigParser(allow_no_value=True)
        self.config_root = GlobalConfig.get('paths', 'config_root')
        self.config_path = self.config_root + "/" + self.config_file
        self.config.read(self.config_path)
        self.shadow = ConfigParser.SafeConfigParser()
        self.shadow.read(self.config_root + "/shadow.ini")

    def __set_defaults(self, key_id):
        """
        Default settings from config, and empty values for the encrypt/sign keys
        and the read-in iat (issued-at) times
        """
        self.key_format = self.shadow.get("defaults", "key_format")
        self.key_size = self.shadow.getint("defaults", "key_size")
        self.lifetime = self.shadow.getint("key_settings", "lifetime")
        self.sunset = self.shadow.getint("key_settings", "sunset")
        self.iat = {}
        self.encrypt = None
        self.sign = None
        self.regen_keypair(key_id)   # Check if any keys need to be regenerated
        self.read_keypair(key_id)    # Read keys after they've been updated

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

    def read_keypair(self, key_id):
        """Read in the keypair for this key_id"""
        for key_type in ["sign", "encrypt"]:
            section = key_type + "_" + key_id
            self.__read_key(key_type, section)

    def __write_key(self, key_type, section):
        """
        Given a keyname, generate the key and write it to the config file.
        key_type here is either "sign" or "encrypt".

        Supports two timestamping modes (stamp):
           - current: just create a token dated to the current time
           - backdate: token is dated (ctime - sunset) to pre-age it, but only if the
                key date was formerly undefined.
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
        current_date = self.config.get(section, "date")
        self.iat[key_type] = self.time
        # syslog.syslog("iat: %d time: %d sunset: %d" % (self.iat[key_type]], self.time, self.sunset))
        if self.stamp == "backdate" and current_date == '':
            self.config.set(section, "date", str(self.iat[key_type] - self.sunset))
        else:
            self.config.set(section, "date", str(self.iat[key_type]))

    def write_keypair(self, key_id):
        """
        Write new keypairs for the given key_id.
        Backdate the issued-at time if necessary, like when we issue new
        authorization keys for the first time.
        """
        for key_type in ["sign", "encrypt"]:
            section = key_type + "_" + key_id
            self.__write_key(key_type, section)
        # All settings created. Now write the config file
        with open(self.config_path, 'wb') as sfh:
            self.config.write(sfh)

    def regen_keypair(self, key_id):
        """
        If the datestamps on either member of a keypair have expired, or if the
        date parameter in the slot is un-set for either of the pair, generate
        new keys for both slots.
        """
        regen_pair = False
        for key_type in ["sign", "encrypt"]:
            section = key_type + "_" + key_id
            if self.config.get(section, "date") == '':
                regen_pair = True
                break
            else:
                keydate = self.config.getint(section, "date")
                if self.time > (keydate + self.lifetime):
                    regen_pair = True
                    break
        if regen_pair is True:
            self.write_keypair(key_id)

    def check_token(self, token):
        """
        Process a JWE settings token from a user cookie, checking to see if
        it is signed by this keypair's signing key, and encrypted with its
        encryption key.
        If all the validation works, return a validated JWT.
        If any part of this fails, do not set a cookie and return False.
        """
        try:
            decrypted = jwt.JWT(key=self.encrypt, jwt=token)
            validated = jwt.JWT(key=self.sign, jwt=decrypted.claims)
            return {'decrypted': decrypted, 'validated': validated}
        except Exception as err:
            syslog.syslog("Token validation error: " + err.message)
            return False
            