import os
import time
from sys import stdin
import ConfigParser
import syslog
from passlib.hash import argon2


syslog.openlog(ident='constantina_auth')


class ConstantinaAuth:
    """
    Constantina Authentication object. Manages passwords, authentication tokens
    and anything related to users.
    """
    def __init__(self):
        self.config = ConfigParser.SafeConfigParser()
        self.config.read('shadow.ini')
        self.user = None
        self.token = None

        self.lifetime = None
        self.sunset = None
        self.time = None
        self.exp = None
        self.nbf = None
        self.sunset = None
        self.regen_cek = []


    def __read_shadow_settings(self):
        """
        Read in settings from the shadow.ini config file so we can track what
        the token expiry settings we care about might be.
        """
        self.lifetime = self.config.getint("key_settings", "lifetime")
        self.sunset = self.config.getint("key_settings", "sunset")
        self.time = time.time()

        for keyname in ["key1", "key2"]:
            keydate = self.config.getint(keyname, "date")
            if self.time > (keydate + self.sunset):
                self.regen_cek.append(keyname)


    def __regen_cek(self):
        """
        Regenerate content encryption keys as necessary.
        TODO: Don't implement until basic tokens are tested
        """
        for keyname in self.regen_cek:
            # self.config.set(stuff)
            pass


    def check_token(self, token):
        """
        Process a JWE token. In Constantina these come from the users' cookie
        """
        pass



class ConstantinaAccount:
    """
    Checks accounts, whether they come from password logins or from things like
    certificate values passed from an upstream Nginx client-cert verification.
    """
    def __init__(self):
        self.config = ConfigParser.SafeConfigParser()
        self.config.read('shadow.ini')


    def __validate_user(self, username):
        """Valid new usernames are less than 50 characters"""
        return len(username) < self.config.getint('defaults', 'user_length')


    def __validate_password(self, password):
        """
        Validate that new passwords match a given password policy.
        What should that be? People want to type these on phones and
        things, so force 2FA or certificates for security.
        """
        return len(password) < self.config.getint('defaults', 'password_length')


    def set_password(self, username, password):
        """Given username and password, set a shadow entry"""
        valid = self.__validate_user(username) and self.__validate_password(password)
        if valid is True:
            pwd_hash = argon2.hash(password)
            self.config.set("passwords", username, pwd_hash)


    def check_password(self, username, password):
        """Given username and password, check that the login succeeded."""
        pwd_hash = self.config.get("users", username)
        return argon2.verify(password, pwd_hash)



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
    for validating my use of environment variabls and forms!
    """
    size = int(os.environ.get('CONTENT_LENGTH'))
    post = {}
    with stdin as rfh:
        # TODO: max content length, check for EOF (max_request_size_mb)
        inbuf = rfh.read(size)
        for vals in inbuf.split('&'):
            [key, value] = vals.split('=')
            post[key] = value

    if (post['username'] == "justin") and (post['password'] == "justin"):
        return True
    else:
        return False
