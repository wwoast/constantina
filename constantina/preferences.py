import os
import ConfigParser
import json
import syslog
from jwcrypto import jwk, jwt

from shared import GlobalConfig, GlobalTime, opaque_identifier, opaque_integer, opaque_mix, specific_cookie
from keypair import ConstantinaKeypair

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

    Eventually settings verification per Constantina Application should happen
    in their own classes where preferences are checked and validated, but for
    now there aren't enough preferences to justify this approach.
    """
    def __init__(self, username, mode, **kwargs):
        self.username = username
        self.__read_config()
        self.__default_preferences()

        if mode == "set":
            # TODO: read the form as kwargs
            pass
        if mode == "cookie":
            # Read in an existing preferences cookie
            self.read_preferences(**kwargs)

    def __read_config(self):
        """Necessary config files for setting preferences."""
        self.config_file = "preferences.ini"
        self.config_root = GlobalConfig.get('paths', 'config_root')
        self.config_path = self.config_root + "/" + self.config_file
        self.zoo = ConfigParser.SafeConfigParser()
        self.zoo.read(self.config_root + "/zoo.ini")
        self.preferences = ConfigParser.SafeConfigParser()
        self.preferences.read(self.config_path)
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

        self.instance_id = GlobalConfig.get("server", "instance_id")
        self.preference_id = self.preferences.get(self.username, "preference_id")
        self.cookie_id = self.create_cookie_id(self.instance_id, self.preference_id)
        self.cookie_name = ("__Secure-" +
                            GlobalConfig.get('server', 'hostname') + "-" +
                            self.cookie_id)

        # Given a preference_id, create/load the keypair
        self.key = ConstantinaKeypair(self.config_file, self.preference_id)
        self.jwe = None
        self.jwt = None
        self.serial = None

    def __validate_claims(self):
        """
        Check the domain of values for each claim, and pin to a sensible default
        if wacky inputs are received. TODO
        """
        # Is theme a number, and not outside the range of configured themes?
        theme_count = len(GlobalConfig.items("themes")) - 1
        if int(self.thm) > theme_count:
            self.thm = '0'
        # Is topic a string? Just check #general for now
        self.top = "general"
        # Is the expand setting a positive integer less than MAX_PAGING?
        max_paging = GlobalConfig.getint("miscellaneous", "max_items_per_page")
        if self.gro * 10 > max_paging:
            self.gro = max_paging/10
        # Is revision timer a positive integer smaller than the max_edit_window?
        max_edit_window = self.zoo.getint("zoo", "max_edit_window")
        default_edit_window = self.zoo.getint("zoo", "edit_window")
        if self.rev > max_edit_window:
            self.rev = max_edit_window
        if self.rev < 0:
            self.rev = default_edit_window

    def __read_claims(self):
        """
        Given a settings token was read correctly, sanity check its settings here.
        """
        claims = json.loads(self.jwt.claims)
        self.iat = int(claims["iat"])
        self.nbf = int(claims["nbf"])
        self.exp = int(claims["exp"])
        self.thm = claims["thm"]
        self.top = claims["top"]
        self.gro = int(claims["gro"])
        self.rev = int(claims["rev"])
        self.__validate_claims()

    def __write_claims(self, thm, top, gro, rev):
        """
        Given a form input for preferences, validate the incoming settings
        """
        self.thm = thm
        self.top = top
        self.gro = gro
        self.rev = rev
        self.__validate_claims()

    def set_user_preference(self, username, preference_id):
        """
        Create new keys and preference ID for this user, regardless of what
        already exists in the preferences file. Don't track when settings keys
        were made or regenerated, as this info isn't as crucial as session keys.

        The preference ID is generated by constantina_configure when an
        account is made, but it calls here to set it.
        """
        self.preferences.set(username, "preference_id", preference_id)

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

    def read_preferences(self, cookie):
        """
        Given a cookie, read the preferences so the settings screen can be populated.
        If the cookie doesn't exist, return False.
        """
        token = specific_cookie(self.cookie_name, cookie)
        valid = self.key.check_token(token)
        if valid is not False:
            self.jwe = valid['decrypted']
            self.jwt = valid['validated']
            self.__read_claims()
            return True
        else:
            return False

    def write_preferences(self, cookie_id):
        """
        Set new preferences, and then write a new cookie.
        """
        signing_algorithm = self.shadow.get("defaults", "signing_algorithm")
        instance_id = GlobalConfig.get("server", "instance_id")
        self.iat = GlobalTime    # Don't leak how long operations take
        self.nbf = self.iat - 60
        jti = uuid4().int
        jwt_claims = {
            "nbf": self.nbf,
            "iat": self.iat,
            "jti": str(jti),
            "thm": self.thm,
            "top": self.top,
            "gro": self.gro,
            "rev": self.rev
        }
        jwt_header = {
            "alg": signing_algorithm
        }
        self.jwt = jwt.JWT(header=jwt_header, claims=jwt_claims)
        self.jwt.make_signed_token(self.key.sign)

        encryption_parameters = {
            "alg": self.shadow.get("defaults", "encryption_algorithm"),
            "enc": self.shadow.get("defaults", "encryption_mode")
        }
        payload = self.jwt.serialize()
        self.jwe = jwt.JWT(header=encryption_parameters, claims=payload)
        self.jwe.make_encrypted_token(self.key.encrypt)
