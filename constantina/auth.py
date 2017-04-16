import os
from sys import stdin
from uuid import uuid4
import ConfigParser
import json
import syslog
from jwcrypto import jwk, jwt
from passlib.hash import argon2

from shared import GlobalConfig


syslog.openlog(ident='constantina.auth')


class ConstantinaAuth:
    """
    Constantina Authentication object. Manages passwords, authentication tokens
    and anything related to users.
    """
    def __init__(self, mode, **kwargs):
        self.config = ConfigParser.SafeConfigParser(allow_no_value=True)
        self.config.read(GlobalConfig.get('paths', 'config') + "/shadow.ini")
        self.account = ConstantinaAccount()
        self.lifetime = self.config.getint("key_settings", "lifetime")
        self.sunset = self.config.getint("key_settings", "sunset")
        self.time = int(jwt.time.time())    # Don't leak multiple timestamps
        self.headers = None  # Auth headers we add later
        self.regen_jwk = []  # List of JWKs to regenerate, if needed
        self.jwk = {}        # One of N keys for signing/encryption
        self.jwk_iat = {}    # Expiry dates for the JWKs
        self.jwe = None      # The encrypted token
        self.jwt = None      # The internal signed token
        self.serial = None   # Token serialized and read/written into cookies
        self.aud = None      # JWT audience (i.e. hostname)
        self.exp = None      # JWT expiration time
        self.iat = None      # JWT issued-at time
        self.nbf = None      # JWT not-before time
        self.sub = None      # JWT subject (subject_id/username)

        if mode == "password":
            # Check username and password, and if the login was valid, the
            # set_token logic will go through
            self.account.login_password(**kwargs)
            self.set_token()
        elif mode == "cookie":
            # Check if the token is valid, and if it was, the token and account
            # objects will be properly set.
            if self.check_token(**kwargs) is True:
                self.account.login_cookie(self.sub)
        else:
            # No token or valid account
            pass


    def __regen_all_jwk(self):
        """
        Regenerate any expired JWK shared secret keys in the config file. If a key
        doesn't exist, create it.
        """
        for keyname in ["encrypt_last", "encrypt_current", "sign_last", "sign_current"]:
            if isinstance(self.config.get(keyname, "date"), int) is False:
                 self.regen_jwk.append(keyname)
            else:
                keydate = self.config.getint(keyname, "date")
                if self.time > (keydate + self.sunset):
                    self.regen_jwk.append(keyname)

        for keyname in self.regen_jwk:
            self.__write_key(keyname)


    def __write_key(self, name):
        """
        Given a keyname, generate the key and write it to the config file.
        Persist the JWK key itself by "name" into the self.jwk{} dict
        """
        key_format = self.config.get("defaults", "key_format")
        key_size = self.config.getint("defaults", "key_size")
        self.jwk[name] = jwk.JWK(generate=key_format, size=key_size)
        # Whatever key properties exist, set them in the config
        data = self.jwk[name].__dict__
        for hash_key in data['_key'].keys():
            self.config.set(self.jwk[name], hash_key, data['_key'][hash_key])
        for hash_key in data['_params'].keys():
            self.config.set(self.jwk[name], hash_key, data['_params'][hash_key])
        # When did we create this key? When the class was instant'ed
        self.jwk_iat[name] = self.time
        self.config.set(name, "date", self.jwk_iat[name])


    def __read_key(self, name):
        """
        Read the desired key from the configuration file, and load it as
        a JWK for purpose of signing or encryption. This tries to load the
        exact parameters from the config file into their equivalent places
        in the JWK object. Namely, the k value goes in _key, and all the
        other ones of interest go in _params.
        Persist the JWK key itself by "name" into the self.jwk{} dict
        """
        jwk_data = {
            '_key': {},
            '_params': {},
        }
        for hash_key, value in self.config.items(name):
            if hash_key == 'k':
                jwk_data['_key'][hash_key] = value
            else:
                jwk_data['_params'][hash_key] = value
        self.jwk[name] = jwk_data   # Equivalent to the jwk.JWK call
        self.jwk_iat[name] = self.config.get(name, "date")


    def __create_jwt(self):
        """
        Create a signed JWT with the key_current, and define any of the
        signed claims that are of interest
        """
        signing_algorithm = self.config.get("defaults", "signing_algorithm")
        subject_id = self.config.get("defaults", "subject_id")
        signing_key = self.__read_key("sign_current")
        self.iat = self.time    # Don't leak how long operations take
        self.aud = GlobalConfig.get("server", "hostname")
        self.sub = subject_id + "/" + self.account.username
        self.nbf = self.iat - 60
        self.exp = self.iat + self.lifetime
        jti = uuid4().int
        claims = {
            "sub": self.sub,
            "nbf": self.nbf,
            "iat": self.iat,
            "jti": jti,
            "aud": self.aud,
            "exp": self.exp
        }
        header = {
            "alg": signing_algorithm
        }
        self.jwt = jwt.JWT(header=header, claims=claims)
        self.jwt.make_signed_token(signing_key)


    def __read_jwt_claims(self):
        """
        Once a JWE and JWT have been checked, read in all of their
        claims data into the auth object.
        """
        self.iat = self.jwt.claims["iat"]
        self.aud = self.jwt.claims["aud"]
        self.sub = self.jwt.claims["sub"]
        self.nbf = self.jwt.claims["nbf"]
        self.exp = self.jwt.claims["exp"]


    def __create_jwe(self):
        """
        Create a JWE token whose "claims" set (payload) is a signed JWT.
        """
        self.jwt = self.__create_jwt()
        encryption_key = self.__read_key("encryption_current")
        encryption_parameters = {
            "alg": self.config.get("defaults", "encryption_algorithm"),
            "enc": self.config.get("defaults", "encryption_mode")
        }
        payload = self.jwt.serialize()
        self.jwe = jwt.JWT(header=encryption_parameters, claims=payload)
        self.jwe.make_encrypted_token(encryption_key)


    def __decrypt_jwe(self, serial, keyname):
        """
        Try decrpyting a JWE with a key. If successful, return true.
        """
        try:
            self.jwe = jwt.JWT(key=self.jwk[keyname], jwt=serial)
            return True
        except:
            return False


    def __check_jwe(self, serial):
        """
        Given a serialized blob, parse it as a JWE token. If it fails, return
        false. If it succeeds, return true, and set self.jwe to be the
        serialized JWT inside the JWE.
        """
        for keyname in ["encrypt_current", "encrypt_last"]:
            if self.__decrypt_jwe(serial, keyname) is True:
                return True
        return False


    def __validate_jwt(self, serial, keyname):
        """
        Try validating the signature of a JWT and its claims.
        If successful, return true.
        """
        try:
            # TODO: How to check date prior to signing?
            self.jwt = jwt.JWT(key=self.jwk[keyname], jwt=serial)
            return True
        except:
            return False


    def __check_jwt(self, serial):
        """
        Given a serialized blob, parse it as a JWT token. If it fails, return
        false. If it succeeds, return true, and set self.jwt to be the JWT.
        """
        for keyname in ["sign_current", "sign_last"]:
            if self.__validate_jwt(serial, keyname) is True:
                return True
        return False


    def check_token(self, token):
        """
        Process a JWE token. In Constantina these come from the users' cookie.
        If all the validation works, self.jwt becomes a valid JWT, read in the
        JWT's claims, and return True.
        If any part of this fails, do not set a cookie and return False.
        """
        if self.__check_jwe(token) is True:
            if self.__check_jwt(self.jwe.claims) is True:
                self.serial = self.jwe.serialize()
                self.__read_jwt_claims()
                return True
        return False


    def set_token(self):
        """
        If authentication succeeds, set a token for this user. Regardless if
        the attempt succeeds or fails, use this as an opportunity to update any
        signing or encryption keys that might be used in the generation of
        actual JWE tokens.
        """
        self.__regen_all_jwk()
        if self.account.valid is True:
            self.__create_jwe()
            self.serial = self.jwe.serialize()
            cookie_values = [
                "s=" + self.serial,
                "Secure",
                "HttpOnly",
                "Max-Age=" + self.lifetime,
                "Same-Site=strict"
            ]
            self.headers += ("Set-Cookie", ' '.join(cookie_values))


class ConstantinaAccount:
    """
    Checks accounts, whether they come from password logins or from things like
    certificate values passed from an upstream Nginx client-cert verification.
    """
    def __init__(self):
        self.config = ConfigParser.SafeConfigParser(allow_no_value=True)
        self.config.read(GlobalConfig.get("paths", "config") + "/shadow.ini")
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
        self.valid = (self.__validate_user() and
                      self.__validate_subject_id())
        return self.valid


    def __validate_subject_id(self):
        """
        The subject_id comes from a token's subject in the form "subject_id/username".
        If the incoming subject_id matches the domain value in GlobalConfig, then we
        consider it valid.
        """
        (test_id, self.username) = self.subject.split("/")
        return test_id == GlobalConfig.get("server", "hostname")


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
        except:
            return False


    def set_password(self):
        """Given username and password, set a shadow entry"""
        if self.valid is True:
            pwd_hash = argon2.hash(self.password)
            self.config.set("passwords", self.username, pwd_hash)
            return True
        else:
            return False



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


def set_authentication(env):
    """
    Received a POST trying to set a username and password.
    """
    read_size = int(env.get('CONTENT_LENGTH'))
    max_size = GlobalConfig.getint('miscellaneous', 'max_request_size_mb') * 1024 * 1024
    if read_size >= max_size:
        read_size = max_size

    post = {}
    inbuf = env['wsgi.input'].read(read_size)
    # TODO: equals-sign in form will break this!
    for vals in inbuf.split('&'):
        syslog.syslog(vals)
        [key, value] = vals.split('=')
        post[key] = value
        syslog.syslog(value)

    auth = ConstantinaAuth("password", username=post["username"], password=post["password"])
    auth.set_token()
    return auth


def show_authentication(env):
    """
    TODO: Received a GET with a cookie.
    """
    auth = ConstantinaAuth("password", username="invalid", password="invalid")
    return auth


def authentication(env):
    """
    If a cookie is present, validate the JWE inside the cookie.
    If a POST comes in, check the given username and password before
    handing out a new cookie with a JWE value.
    """
    if env.get('REQUEST_METHOD') == 'POST':
        auth = set_authentication(env)
        return auth
    else:
        auth = show_authentication(env)
        return auth