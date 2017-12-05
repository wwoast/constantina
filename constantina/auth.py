from uuid import uuid4
import ConfigParser
import json
import syslog
from jwcrypto import jwt
from passlib.hash import argon2

from shared import GlobalConfig, GlobalTime, specific_cookie
from keypair import ConstantinaKeypair
from preferences import ConstantinaPreferences

syslog.openlog(ident='constantina.auth')


class ConstantinaAuth:
    """
    Constantina Authentication object. Manages passwords, authentication tokens
    and anything related to users.

    # TODO: Username sanitiation, once usernames can be enrolled!
    """
    def __init__(self, process, **kwargs):
        self.mode = GlobalConfig.get("authentication", "mode")
        if self.__auth_cancel() is True:
            return

        self.config = ConfigParser.SafeConfigParser(allow_no_value=True)
        self.config.read(GlobalConfig.get('paths', 'config_root') + "/shadow.ini")
        self.account = ConstantinaAccount()
        self.cookie_name = ("__Secure-" +
                            GlobalConfig.get('server', 'hostname') + "-" +
                            GlobalConfig.get('server', 'instance_id'))
        self.logout = False
        self.lifetime = self.config.getint("key_settings", "lifetime")
        self.sunset = self.config.getint("key_settings", "sunset")
        self.time = GlobalTime.time    # Don't leak multiple timestamps
        self.headers = []    # Auth headers we add later
        self.keypair = {}    # One of N keys for signing/encryption
        self.jwe = None      # The encrypted token
        self.jwt = None      # The internal signed token
        self.serial = None   # Token serialized and read/written into cookies
        self.aud = None      # JWT audience (i.e. hostname)
        self.exp = None      # JWT expiration time
        self.iat = None      # JWT issued-at time
        self.nbf = None      # JWT not-before time
        self.sub = None      # JWT subject (subject_id/username)

        # Read in the authorization signing/encryption keys, and regenerate them
        # if either one is expired.
        self.__read_auth_keypair()

        if process == "password":
            # Check username and password, and if the login was valid, the
            # set_token logic will go through
            self.account.login_password(**kwargs)
            self.set_token()
        elif process == "cookie":
            # Check if the auth cookie is valid
            if self.check_token(**kwargs) is True:
                self.account.login_cookie(self.sub)
        else:
            # No token or valid account
            pass

    def __auth_cancel(self):
        """
        If we're in blog mode, or if something about the inbound cookie is goofy,
        cancel the authentication flow.
        """


    def __read_auth_keypair(self):
        """
        Read and regenerate the signing and encyption keys that manage
        Constantina's auth cookies as necessary. If the last keypair is too old,
        regenerate a new one. If the current keypair has hit its sunset period,
        migrate it to the last slot.

        The 'last' and 'current' logic is currently hard-coded in the
        ConstantinaKeypair object, until I think of what a sensible convention
        for specifying source and dest slots is.
        """
        self.keypair['current'] = ConstantinaKeypair(
            'shadow.ini', 'current', stamp='current', mode='age',
            source="current", dest="last")
        self.keypair['last'] = ConstantinaKeypair(
            'shadow.ini', 'last', stamp='backdate', mode='regen')

    def __create_jwt(self):
        """
        Create a signed JWT with the key_current, and define any of the
        signed claims that are of interest.
        """
        signing_algorithm = self.config.get("defaults", "signing_algorithm")
        subject_id = self.config.get("defaults", "subject_id")
        instance_id = GlobalConfig.get("server", "instance_id")
        signing_key = self.keypair["current"].sign
        self.iat = self.time    # Don't leak how long operations take
        self.aud = GlobalConfig.get("server", "hostname")
        self.sub = subject_id + "-"  + instance_id + "/" + self.account.username
        self.nbf = self.iat - 60
        self.exp = self.iat + self.lifetime
        jti = uuid4().int
        jwt_claims = {
            "sub": self.sub,
            "nbf": self.nbf,
            "iat": self.iat,
            "jti": str(jti),
            "aud": self.aud,
            "exp": self.exp
        }
        jwt_header = {
            "alg": signing_algorithm
        }
        self.jwt = jwt.JWT(header=jwt_header, claims=jwt_claims)
        self.jwt.make_signed_token(signing_key)
        return self.jwt

    def __read_jwt_claims(self):
        """
        Once a JWE and JWT have been validated, read in all of their
        claims data into the auth object.
        """
        claims = json.loads(self.jwt.claims)
        self.iat = int(claims["iat"])
        self.aud = claims["aud"]
        self.sub = claims["sub"]
        self.nbf = int(claims["nbf"])
        self.exp = int(claims["exp"])

    def __create_jwe(self):
        """
        Create a JWE auth token whose "claims" set (payload) is a signed JWT.
        """
        self.jwt = self.__create_jwt()
        encryption_key = self.keypair["current"].encrypt
        encryption_parameters = {
            "alg": self.config.get("defaults", "encryption_algorithm"),
            "enc": self.config.get("defaults", "encryption_mode")
        }
        payload = self.jwt.serialize()
        self.jwe = jwt.JWT(header=encryption_parameters, claims=payload)
        self.jwe.make_encrypted_token(encryption_key)

    def check_token(self, cookie):
        """
        Process a JWE token. In Constantina these come from the users' cookie.
        If all the validation works, self.jwt becomes a valid JWT, read in the
        JWT's claims, and return True.
        If any part of this fails, do not set a cookie and return False.
        """
        token = specific_cookie(self.cookie_name, cookie)
        if token is None:
            return False
        for key_id in ["current", "last"]:
            valid = self.keypair[key_id].check_token(token)
            if valid is not False:
                self.jwe = valid['decrypted']
                self.jwt = valid['validated']
                self.serial = self.jwe.serialize()
                self.__read_jwt_claims()
                return True
        return False

    def expire_token(self):
        """
        If a user logs out, expire their authentication token immediately.
        This is not guaranteed to delete an existing authentication cookie, but
        backdating the cookie is apparently the best we can do.
        """
        self.logout = True
        cookie_values = [
            self.cookie_name + "=" + "deleted",
            "Secure",
            "HttpOnly",
            "Max-Age=0",
            "SameSite=strict"
        ]
        self.headers.append(("Set-Cookie", '; '.join(cookie_values).encode('utf-8')))

    def set_token(self):
        """
        If authentication succeeds, set a token for this user.
        """
        if self.account.valid is True:
            self.__create_jwe()
            self.serial = self.jwe.serialize()
            cookie_values = [
                self.cookie_name + "=" + self.serial,
                "Secure",
                "HttpOnly",
                "Max-Age=" + str(self.lifetime),
                "SameSite=strict"
            ]
            # Cookies must be Python byte-string types -- encode "fixes" this
            self.headers.append(("Set-Cookie", '; '.join(cookie_values).encode('utf-8')))


class ConstantinaAccount:
    """
    Checks accounts, whether they come from password logins or from things like
    certificate values passed from an upstream Nginx client-cert verification.
    """
    def __init__(self):
        self.config = ConfigParser.SafeConfigParser(allow_no_value=True)
        self.config.read(GlobalConfig.get("paths", "config_root") + "/shadow.ini")
        self.valid = False
        self.username = None
        self.password = None
        self.subject = None

    def login_password(self, username, password):
        """
        Given a username and password, check against entries in the shadow file
        and if the login is valid, and username/passwords meet the given policy,
        return True.
        """
        self.username = username
        self.password = password
        self.valid = (self.__validate_user() and
                      self.__validate_password() and
                      self.__check_password())
        return self.valid

    def login_cookie(self, sub):
        """
        Obtained values from an encrypted JWE cookie. Set these and be done.
        """
        self.subject = sub
        self.username = self.subject.split("/")[1]
        self.valid = (self.__validate_user() and
                      self.__validate_subject_id())
        return self.valid

    def __validate_subject_id(self):
        """
        The subject_id comes from a token's subject in the form:
            subject_id-instance_id/username
        If the incoming subject_id matches the domain value in both shadow
        and GlobalConfigs, then we consider it valid.
        """
        instance_id = GlobalConfig.get("server", "instance_id")
        subject_id = self.config.get("defaults", "subject_id")
        subject = subject_id + "-" + instance_id
        (test_id, self.username) = self.subject.split("/")
        return test_id == subject

    def __validate_user(self):
        """Valid new usernames are less than 24 characters"""
        return len(self.username) < self.config.getint('defaults', 'user_length')

    def __validate_password(self):
        """
        Validate that new passwords match a given password policy.
        What should that be? People want to type these on phones and
        things, so force 2FA or certificates for security.
        """
        return len(self.password) < self.config.getint('defaults', 'password_length')

    def __check_password(self):
        """
        Given username and password, check that the login succeeded.
        If the username doesn't exist, just return False.
        """
        try:
            pwd_hash = self.config.get("passwords", self.username)
            return argon2.verify(self.password, pwd_hash)
        except ConfigParser.Error:
            return False

    def set_password(self):
        """Given username and password, set a shadow entry"""
        if self.valid is True:
            pwd_hash = argon2.hash(self.password)
            self.config.set("passwords", self.username, pwd_hash)
            return True
        else:
            return False


def check_authorization():
    """
    TODO TODO TODO
    When multiple accounts are created, and files can be walled off between
    users, we should have a authorization module that does file checks based
    on user accounts.

    The file list will have individual files in it, as well as a list of users
    or * that are allowed to see the file. If a file isn't in the list, a folder
    can be specified instead that sets permissions valid for all files in the
    sub-folders.

    The details of authorization will likely be different for each subapp in
    Constantina, so maybe this lives elsewhere eventually.
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


def logout_page(start_response, state):
    """
    If Constantina is in "forum" mode, you can get a logout
    page by clicking the logout button in the settings menu.
    """
    base = open(state.theme + '/logout.html', 'r')
    html = base.read()
    start_response('200 OK', state.headers)
    return html


def set_authentication(post):
    """
    Received a POST trying to set a username and password. There must be a
    hidden form field "action" with value "login" for this to be processed
    as a POST login.
    """
    auth = ConstantinaAuth("password", username=post["username"], password=post["password"])
    auth.set_token()
    return auth


def show_authentication(env):
    """
    Received a GET with a cookie. See if there's an auth cookie in there.
    """
    if 'HTTP_COOKIE' in env:
        raw_cookie = env.get('HTTP_COOKIE')
        auth = ConstantinaAuth("cookie", cookie=raw_cookie)
        return auth
    else:
        auth = ConstantinaAuth("fail")
        return auth


def authentication(env, post):
    """
    If a cookie is present, validate the JWE inside the cookie.
    If a POST comes in, check the given username and password before
    handing out a new cookie with a JWE value.
    """
    if post.get('action') == "login":
        auth = set_authentication(post)
        return auth
    elif post.get('action') == "logout":
        auth = show_authentication(env)
        auth.expire_token()
        return auth
    else:
        auth = show_authentication(env)
        return auth