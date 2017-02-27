import os
import time
from sys import stdin
import syslog
import passlib
import ConfigParser

syslog.openlog(ident='constantina_auth')


class ConstantinaAuth:
    """
    Constantina Authentication object. Manages passwords, authentication tokens
    and anything related to users.
    """
    def __init__():
        self.config = ConfigParser.SafeConfigParser
        self.config.open('shadow.ini')
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
            if self.time > (self.keydate + self.sunset):
                self.regen_cek.append(keyname)


    def __regen_cek(self):
        """
        Regenerate content encryption keys as necessary
        """
        for keyname in self.regen_cek:
            # self.config.set(stuff)
            pass


    def check_user(self, username, password):
        """
        Given a username, see if there is an account that exists, and then
        validate the provided password value
        """
        pass


    def set_user(self, username, password, existing=True):
        """
        Given a username and a password, set a new account password. By default
        the existing flag makes this only work for accounts that already have a
        shadow record of some kind.
        """
        pass


    def check_token(self, token)
        """
        Process a JWE token. In Constantina these come from the users' cookie
        """
        pass



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
    with stdin as fh:
        # TODO: max content length, check for EOF
        inbuf = fh.read(size)
        for vals in inbuf.split('&'):
            [key, value] = vals.split('=')
            post[key] = value

    if (post['username'] == "justin") and (post['password'] == "justin"):
        return True
    else:
        return False
