import os
import time
from sys import stdin
import ConfigParser
import syslog
import json
from jwcrypto import jws, jwk
from jwcrypto.common import json_encode
from passlib.hash import argon2
from constantina_shared import GlobalConfig


syslog.openlog(ident='constantina_auth')


class ConstantinaAuth:
    """
    Constantina Authentication object. Manages passwords, authentication tokens
    and anything related to users.
    TODO: How to take inputs related to arbitrary auth parameters? **kwargs?
    """
    def __init__(self, username, password):
        self.config = ConfigParser.SafeConfigParser(allow_no_value=True)
        self.config.read('shadow.ini')
        self.user = ConstantinaAccount(username, password)
        self.token = None

        self.lifetime = None
        self.sunset = None
        self.time = None
        self.exp = None
        self.nbf = None
        self.sunset = None
        self.regen_jwk = []


    def __read_shadow_settings(self):
        """
        Read in settings from the shadow.ini config file so we can track what
        the token expiry settings we care about might be.
        """
        self.lifetime = self.config.getint("key_settings", "lifetime")
        self.sunset = self.config.getint("key_settings", "sunset")
        self.time = time.time()

        for keyname in ["key_last", "key_current"]:
            keydate = self.config.getint(keyname, "date")
            if self.time > (keydate + self.sunset):
                self.regen_jwk.append(keyname)


    def __regen_all_jwk(self):
        """
        Regenerate any expired JWK shared secret keys in the config file.
        """
        key_format = self.config.get("defaults", "key_format")
        key_size = self.config.getint("defaults", "key_size")
        for keyname in self.regen_jwk:
            keyname = jwk.JWK(generate=key_format, size=key_size)
            data = json.loads(keyname.export())
            for hash_key in data.keys:
                # Whatever key properties exist, set them here
                self.config.set(keyname, hash_key, data[hash_key])
            # TODO: Set the date that we did this


    def __create_jwt(self):
        """
        Create a signed JWT with the key_current
        """
        pass
        

    def check_token(self, token):
        """
        Process a JWE token. In Constantina these come from the users' cookie
        """
        pass


    def set_token(self, username):
        """
        If authentication succeeds, set a token for this user
        """
        if self.user.check_password() is True:
            self.__create_jwt():


class ConstantinaAccount:
    """
    Checks accounts, whether they come from password logins or from things like
    certificate values passed from an upstream Nginx client-cert verification.
    """
    def __init__(self, username, password):
        self.config = ConfigParser.SafeConfigParser(allow_no_value=True)
        self.config.read('shadow.ini')
        self.username = username
        self.password = password
        self.valid = self.__validate_user() and self.__validate_password()


    def __validate_user(self):
        """Valid new usernames are less than 24 characters"""
        return len(self.username) < self.config.getint('defaults', 'user_length')


    def __validate_password(self):
        """
        Validate that new passwords match a given password policy.
        What should that be? People want to type these on phones and
        things, so force 2FA or certificates for security.
        """
        return len(password) < self.config.getint('defaults', 'password_length')


    def set_password(self):
        """Given username and password, set a shadow entry"""
        if self.valid is True:
            pwd_hash = argon2.hash(self.password)
            self.config.set("passwords", self.username, pwd_hash)
            return True
        else:
            return False


    def check_password(self):
        """Given username and password, check that the login succeeded."""
        pwd_hash = self.config.get("users", self.username)
        return argon2.verify(self.password, pwd_hash)



def authentication_page(start_response, state):
    """
    If Constantina is in "forum" mode, you get the authentication
    page. You also get an authentication page when you search for
    a @username in the search bar in "combined" mode.
    """
    base = open(state.theme + '/authentication.html', 'r')
    html = base.read()
    start_response('200 OK', [('Content-Type', 'text/html')])
    return html


def authentication():
    """
    Super naive test authentication function just as a proof-of-concept
    for validating my use of environment variables and forms!
    """
    read_size = int(os.environ.get('CONTENT_LENGTH'))
    max_size = GlobalConfig.getint('miscellaneous', 'max_request_size_mb') * 1024 * 1024
    if read_size >= max_size:
        read_size = max_size

    post = {}
    with stdin as rfh:
        inbuf = rfh.read(read_size)
        for vals in inbuf.split('&'):
            [key, value] = vals.split('=')
            post[key] = value

    if (post['username'] == "justin") and (post['password'] == "justin"):
        return True
    else:
        return False
