import os
import ConfigParser
import json
import syslog
from jwcrypto import jwk, jwt

from shared import GlobalConfig, opaque_identifier, opaque_integer, opaque_mix, specific_cookie


syslog.openlog(ident='constantina.preferences')


class ConstantinaPreferences:
    """
    Set preferences for an individual user.

    Constantina's strategy for this is to leave all settings off of the server,
    as well as avoiding any settings that could be used for tracking users
    by their real-world details. So none of these settings have any concept of
    a "user profile".

    Indeed, the settings are all stored in a user cookie, which is then signed
    and encrypted using per-account keys stored on the server. This way, the
    cookie's purpose may remain opaque on the client, and the settings cannot be
    changed or sniffed on the server without an active session from the user
    actively occuring.
    """
    def __init__(self, username, mode, **kwargs):
        self.__read_config()
        self.__default_preferences()
        
        if mode == "set":
            pass
        if mode == "cookie":
            # Cookie name things go here
            pass

    def __read_config(self):
        """Necessary config files for setting preferences."""
        self.config_root = GlobalConfig.get('paths', 'config_root')
        self.zoo = ConfigParser.SafeConfigParser()
        self.zoo.read(self.config_root + "/zoo.ini")
        self.preferences = ConfigParser.SafeConfigParser()
        self.preferences.read(self.config_root + "/preferences.ini")
        self.shadow = ConfigParser.SafeConfigParser()
        self.shadow.read(self.config_root + "/shadow.ini")

    def __default_preferences(self):
        """
        Set all the default preference claims a user gets:
            thm: the user's chosen theme
            top: the default forum topic for this user, if none else chosen
            gro: thread expansion strategy for the Zoo forum
                0=expand all threads
                N>0: expand last N*10 threads
            rev: user's configured time for editing a thread.
        Initialize the available signing and encryption keys to "None".
        Based on the username, set the expected cookie name and id.
        TODO: refactor auth settings to use similar default strategy.
        """
        self.thm = GlobalConfig.get("themes", "default")
        self.top = "general"
        self.gro = 0
        self.rev = self.zoo.get('zoo', 'edit_window')

        self.encrypt = None
        self.sign = None

        self.instance_id = GlobalConfig.get("server", "instance_id")
        self.preference_id = self.preferences.get(username, "preference_id")
        self.cookie_id = create_cookie_id(self.instance_id, self.preference_id)
        self.cookie_name = ("__Secure-" +
                            GlobalConfig.get('server', 'hostname') + "-" +
                            self.cookie_id)

    def set_preference_claims(self, pref_dict):
        """
        Given a settings token was read correctly, sanity check its settings here.
        TODO: value-domain checks etc.
        """
        self.thm = pref_dict['thm']
        self.top = pref_dict['top']
        self.gro = pref_dict['gro']
        self.rev = pref_dict['rev']
    
    def set_user_preference(self, username, preference_id):
        """
        Create new keys and preference ID for this user, regardless of what
        already exists in the preferences file. Don't track when settings keys
        were made or regenerated, as this info isn't as crucial as session keys.

        The preference ID is generated by constantina_configure when an
        account is made, but it calls here to set it.
        """
        self.preferences.set(username, "preference_id", preference_id)
        key_format = self.shadow.get("defaults", "key_format")
        key_size = self.shadow.getint("defaults", "key_size")
        self.sign = jwk.JWK.generate(kty=key_format, size=key_size)
        self.encrypt = jwk.JWK.generate(kty=key_format, size=key_size)

        # Whatever key properties exist, set them in the config
        for keytype in ["sign", "encrypt"]:
            data = getattr(self, keytype).__dict__
            for hash_key in data['_key'].keys():
                self.preferences.set(username, keytype + "_" + hash_key, data['_key'][hash_key])
            for hash_key in data['_params'].keys():
                self.preferences.set(username, keytype + "_" + hash_key, data['_params'][hash_key])
        # Write the settings to the preferences file
        with open(self.config_root + "/preferences.ini", "wb") as cfh:
            self.preferences.write(cfh)

    def get_cookie_preference_id(self, instance_id, cookie_id):
        """
        Whichever preference-id XORs the cookie-id into the instance-id, that
        is the correct key for dealing with this cookie.
        """
        instance_int = opaque_integer(instance_id)
        cookie_int = opaque_integer(cookie_id)
        return opaque_identifier(instance_int ^ cookie_int)

    def create_cookie_id(self, instance_id, preference_id):
        """
        XOR the instance_id and preference_id binary representations together, and
        and then output the BASE62 minus similar characters result, for use as the
        cookie identifier. This ties setting cookies to a specific site instance.
        """
        return opaque_mix(instance_id, preference_id)

    def read_cookie_preferences(self, cookie):
        """
        Given a cookie, read the preferences so the settings screen can be populated.
        If the cookie doesn't exist, return False.
        """
        preference_id = self.get_cookie_preference_id(self.instance_id, self.cookie_id)
        # TODO: factor out specific JWE/JWT/JWK processing into a single module
        # Then have both auth and preferences use the same read_key / write_key stuff
        # TODO: use keys to decrypt cookie and read deets from preferences.

    def write_cookie_preferences(self, cookie_id):
        """Set new preferences, and then write a new cookie."""
        pass

