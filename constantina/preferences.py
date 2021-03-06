from uuid import uuid4
from os import rename
import configparser
import json
from io import BytesIO
from PIL import Image
import syslog
from jwcrypto import jwk, jwt
from random import randint

from constantina.keypair import ConstantinaKeypair
from constantina.shared import GlobalConfig, GlobalTime, opaque_identifier, opaque_integer, opaque_mix, specific_cookie
from constantina.themes import GlobalTheme

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
    def __init__(self):
        self.__read_config()
        self.__default_preferences()

    def generate(self, auth):
        """
        If there's a new auth session and no preferences cookie, create a new one.
        """
        self.__auth_preferences(auth)
        self.__write_preferences()
        self.valid = True  

    def post(self, auth, **raw_post):
        """
        Given a POST form with new preferences data, write a fresh preferences
        cookie and return it.
        """
        self.__auth_preferences(auth)
        self.__write_claims(**raw_post)
        self.__write_preferences()
        self.__upload_avatar(auth, raw_post['updateAvatar'])
        self.valid = True
        
    def cookie(self, auth, raw_cookie):
        """
        If the existing preferences cookie is valid, read its preferences in.
        """
        self.__auth_preferences(auth)
        self.valid = self.__read_preferences(raw_cookie)

    def get_cookie_preference_id(self, instance_id, cookie_id):
        """
        Whichever preference-id XORs the cookie-id into the instance-id, that
        is the correct key for dealing with this cookie. TODO: make this private
        if we can.
        """
        instance_int = opaque_integer(instance_id)
        cookie_int = opaque_integer(cookie_id)
        return opaque_identifier(instance_int ^ cookie_int)

    def __read_config(self):
        """Necessary config files for setting preferences."""
        self.config_file = "preferences.ini"
        self.config_root = GlobalConfig.get('paths', 'config_root')
        self.config_path = self.config_root + "/" + self.config_file
        self.zoo = configparser.SafeConfigParser()
        self.zoo.read(self.config_root + "/zoo.ini", encoding='utf-8')
        self.preferences = configparser.SafeConfigParser()
        self.preferences.read(self.config_path, encoding='utf-8')
        self.sensitive_config = configparser.SafeConfigParser()
        self.sensitive_config.read(self.config_root + "/sensitive.ini", encoding='utf-8')

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
        self.valid = False
        self.cookie_name = None
        self.theme = GlobalTheme.theme    # Existing theme settings from state
        self.thm = GlobalTheme.index
        self.top = "general"
        self.gro = '0'
        self.rev = self.zoo.get('zoo', 'edit_window')
        self.instance_id = GlobalConfig.get("server", "instance_id")

    def __auth_preferences(self, auth):
        """
        Preferences that relate to whether a valid authorization session is
        in effect. Without these settings, the Preferences cookie is just a
        set of default values and won't be valid.
        """
        self.username = auth.account.username
        self.avatar = '../private/images/avatars/%s.png' % self.username
        if not self.preferences.has_option(self.username, "preference_id"):
            self.__set_user_preference(self.username, opaque_identifier())
        self.preference_id = self.preferences.get(self.username, "preference_id")
        self.cookie_id = self.__create_cookie_id(self.instance_id, self.preference_id)
        self.cookie_name = ("__Secure-" +
                            GlobalConfig.get('server', 'hostname') + "-" +
                            self.cookie_id)
        self.headers = []
        # syslog.syslog("config: %s   preference_id: %s" % (self.config_file, self.preference_id))
        # Given a preference_id, create/load the keypair (regen mode)
        self.key = ConstantinaKeypair(self.config_file, self.preference_id)
        self.jwe = None
        self.jwt = None
        self.serial = None

    def __validate_claims(self):
        """
        Check the domain of values for each claim, and pin to a sensible default
        if wacky inputs are received. TODO: throw error, delete bad prefs cookie, and return
        normal preferences cookie, if we're authenticated.
        """
        # Is theme a number, and not outside the range of configured themes?
        # syslog.syslog("validate theme settings: " + str(self.theme) + " = " + str(self.thm))
        GlobalTheme.set(self.thm)
        self.theme = GlobalTheme.theme
        # Is topic a string? Just check #general for now
        self.top = "general"
        # Is the expand setting a positive integer less than MAX_PAGING?
        max_paging = GlobalConfig.getint("miscellaneous", "max_items_per_page")
        if self.gro * 10 > max_paging:
            self.gro = max_paging/10
        # Is revision timer a positive integer smaller than the max_edit_window?
        max_edit_window = self.zoo.getint("zoo", "max_edit_window")
        default_edit_window = self.zoo.getint("zoo", "edit_window")
        if self.rev == '':
            self.rev = default_edit_window
        elif int(self.rev) > max_edit_window:
            self.rev = max_edit_window
        elif int(self.rev) < 0:
            self.rev = default_edit_window
        else:
            self.rev = self.rev

    def __read_claims(self):
        """
        Given a settings token was read correctly, sanity check its settings here.
        """
        claims = json.loads(self.jwt.claims)
        self.iat = int(claims["iat"])
        self.nbf = int(claims["nbf"])
        self.thm = int(claims["thm"])
        self.top = claims["top"]
        self.gro = int(claims["gro"])
        self.rev = int(claims["rev"])
        self.__validate_claims()

    def __write_claims(self, **kwargs):
        """
        Given a form input for preferences, validate the incoming settings. If the
        form wasn't filled out and this is a default preferences cookie, just set the
        default settings and call it a day.
        """
        self.thm = int(kwargs.get('thm'))
        self.top = kwargs.get('top')
        self.gro = int(kwargs.get('gro'))
        self.rev = kwargs.get('rev')   # input field, wait to parse
        self.__validate_claims()
        # TODO: if claims are valid, it's time to write a new preferences keypair
        #       for the current browser ID (can't erase others)
        # TODO: in writing new keypair, we need to delete old ones and expire their cookies

    def __set_user_preference(self, username, preference_id):
        """
        Create new keys and preference ID for this user, regardless of what
        already exists in the preferences file. Don't track when settings keys
        were made or regenerated, as this info isn't as crucial as session keys.
        """
        # Create section if it doesn't exist
        if not self.preferences.has_section(username):
            self.preferences.add_section(username)
        self.preferences.set(username, "preference_id", preference_id)
        with open(self.config_path, 'w', encoding='utf-8') as pfh:
            self.preferences.write(pfh)

    def __upload_avatar(self, auth, upload):
        """
        If a valid token for a user is presented, upload a new avatar to:
           private/images/avatars/{username.png}
        Since the path is fixed per username, this is a detail managed in the
        preferences form, but isn't tracked in the preferences token.
        """
        pixel_width = 80
        # 32 bits rgba per pixel, times number of pixels. File shouldn't be bigger
        max_image_size = pixel_width * pixel_width * 4

        if upload == '' or upload == None or auth.account.valid == False:
            return
        # If file is too large for its bytes-size, return.
        if len(upload) > max_image_size:
            return

        try:
            # Check if it's an 80x80 PNG
                # If not, return an error response
            # If it is a decent image, write to the image path.tmp
            # Then atomic overwrite the existing image
            tmp = self.avatar + "." + self.cookie_id
            iotmp = BytesIO(upload)
            src = Image.open(iotmp)
            if src.size[0] == 80 and src.size[1] == 80:
                dst = src.convert('RGB').convert('P', palette=Image.ADAPTIVE, colors=128)
                dst.save(tmp, "PNG")
                rename(tmp, self.avatar)
        except OSError:
            syslog.syslog("oserror when dealing with image upload")
            return
        except IOError:
            syslog.syslog("ioerror, likely from the image failing to open")
            return

    def __create_cookie_id(self, instance_id, preference_id):
        """
        XOR the instance_id and preference_id binary representations together, and
        and then output the BASE62 minus similar characters result, for use as the
        cookie identifier. This ties setting cookies to a specific site instance.
        """
        return opaque_mix(instance_id, preference_id)

    def __expire_old_preferences(self):
        """
        When the preferences id changes / a new keypair is made, we need to reap
        the old ones for this user, as well as issue a kill-cookie that removes
        any stray cookies that might be in the user's browser.
        """
        cookie_values = [
            self.cookie_name + "=" + "deleted",
            "Secure",
            "HttpOnly",
            "Max-Age=0",
            "SameSite=strict"
        ]
        self.headers.append(("Set-Cookie", '; '.join(cookie_values)))

    def __read_preferences(self, raw_cookie):
        """
        Given a cookie, read the preferences so the settings screen can be populated.
        If the cookie (or cookie name to username mapping) doesn't exist, return False.
        """
        if self.cookie_name is None:
            return False

        token = specific_cookie(self.cookie_name, raw_cookie)
        if token is None:
            return False

        valid = self.key.check_token(token)
        if valid is not False:
            self.jwe = valid['decrypted']
            self.jwt = valid['validated']
            self.__read_claims()
            return True
        else:
            return False

    def __write_preferences(self):
        """
        Set new preferences, and then write a new cookie.
        """
        signing_algorithm = self.sensitive_config.get("key_defaults", "signing_algorithm")
        self.iat = GlobalTime.time    # Don't leak how long operations take
        self.nbf = self.iat - 60
        jti = uuid4().int
        jwt_claims = {
            "nbf": self.nbf,
            "iat": self.iat,
            "jti": str(jti),
            "thm": str(self.thm),
            "top": self.top,
            "gro": str(self.gro),
            "rev": self.rev
        }
        # syslog.syslog("write_prefs: " + str(jwt_claims))
        jwt_header = {
            "alg": signing_algorithm
        }
        self.jwt = jwt.JWT(header=jwt_header, claims=jwt_claims)
        self.jwt.make_signed_token(self.key.sign)

        encryption_parameters = {
            "alg": self.sensitive_config.get("key_defaults", "encryption_algorithm"),
            "enc": self.sensitive_config.get("key_defaults", "encryption_mode")
        }
        payload = self.jwt.serialize()
        self.jwe = jwt.JWT(header=encryption_parameters, claims=payload)
        self.jwe.make_encrypted_token(self.key.encrypt)
        self.serial = self.jwe.serialize()
        cookie_values = [
            self.cookie_name + "=" + self.serial,
            "Secure",
            "HttpOnly",
            "Max-Age=" + str(GlobalTime.time // 10),
            "SameSite=strict"
        ]
        self.headers.append(("Set-Cookie", '; '.join(cookie_values)))


def preferences(env, post, auth):
    """
    Determine what the valid preferences action should be. Options include:
    - Valid auth, POST, form values: write a cookie with the given preferences
    - Valid auth, valid preferences cookie: read cookie in, don't create a new one
    - Valid auth, no preferences cookie: create a cookie with default preferences
    - Invalid auth: Just a stock preferences object
    """
    prefs = ConstantinaPreferences()

    if post.get('action') == "preferences":
        # Form data appears, so write a new preferences cookie.
        del post['action']
        # syslog.syslog("setting cookie. revision timer: " + str(post['rev']))
        prefs.post(auth, **post)

    elif auth.account.valid is True:
        raw_cookie = env.get('HTTP_COOKIE')
        # Assume a cookie is there if an authentication succeeded. 
        # If it wasn't we'll generate a new one.
        prefs.cookie(auth, raw_cookie)
        if prefs.valid is False:
            syslog.syslog("brand new prefs cookie")
            prefs.generate(auth)

    else:
        pass

    return prefs