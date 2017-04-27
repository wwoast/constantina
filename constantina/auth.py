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
        self.cookie_name = ("__Secure-" + 
                            GlobalConfig.get('server', 'hostname') + "-" + 
                            GlobalConfig.get('server', 'instance_id'))
        self.lifetime = self.config.getint("key_settings", "lifetime")
        self.sunset = self.config.getint("key_settings", "sunset")
        self.time = int(jwt.time.time())    # Don't leak multiple timestamps
        self.headers = []    # Auth headers we add later
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

        # Check if JWKs need to be regenerated before accepting any cookies
        # or signing any new tokens
        self.__regen_all_jwk()

        if mode == "password":
            # Check username and password, and if the login was valid, the
            # set_token logic will go through
            self.account.login_password(**kwargs)
            self.set_token()
        elif mode == "cookie":
            # Check if the token is valid, and if it was, the token and account
            # objects will be properly set. To start, read in any keys we need
            # to validate proper signing.
            for keyname in ["encrypt_last", "encrypt_current", "sign_last", "sign_current"]:
                self.__read_key(keyname)
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
            if self.config.get(keyname, "date") == '':
                 self.regen_jwk.append(keyname)
            else:
                keydate = self.config.getint(keyname, "date")
                if self.time > (keydate + self.sunset):
                    self.regen_jwk.append(keyname)
        # Make any keys necessary
        for keyname in self.regen_jwk:
            self.__write_key(keyname)
        # Write the settings to the shadow file once keys are generated
        if self.regen_jwk != []:
            with open(GlobalConfig.get('paths', 'config') + "/shadow.ini", "wb") as sfh:
                self.config.write(sfh)

    def __write_key(self, name):
        """
        Given a keyname, generate the key and write it to the config file.
        Persist the JWK key itself by "name" into the self.jwk{} dict
        """
        key_format = self.config.get("defaults", "key_format")
        key_size = self.config.getint("defaults", "key_size")
        self.jwk[name] = jwk.JWK.generate(kty=key_format, size=key_size)
        # Whatever key properties exist, set them in the config
        data = self.jwk[name].__dict__
        for hash_key in data['_key'].keys():
            self.config.set(name, hash_key, data['_key'][hash_key])
        for hash_key in data['_params'].keys():
            self.config.set(name, hash_key, data['_params'][hash_key])
        # When did we create this key? When the class was instant'ed
        self.jwk_iat[name] = self.time
        self.config.set(name, "date", str(self.jwk_iat[name]))

    def __read_key(self, name):
        """
        Read the desired key from the configuration file, and load it as
        a JWK for purpose of signing or encryption. This tries to load the
        exact parameters from the config file into their equivalent places
        in the JWK object. Namely, the k value goes in _key, and all the
        other ones of interest go in _params.
        Any objects that don't go into the JWK object get removed,
        including the date value we track separately.
        Persist the JWK key itself by "name" into the self.jwk{} dict
        """
        jwk_data = {}
        exclude = ["date"]
        for section, value in self.config.items(name):
            jwk_data[section] = value
        for section in exclude:
            del(jwk_data[section])
        self.jwk[name] = jwk.JWK(**jwk_data)
        self.jwk_iat[name] = self.config.get(name, "date")
        return self.jwk[name]   # Read into the object, but also return it

    def __create_jwt(self):
        """
        Create a signed JWT with the key_current, and define any of the
        signed claims that are of interest.
        """
        signing_algorithm = self.config.get("defaults", "signing_algorithm")
        subject_id = self.config.get("defaults", "subject_id")
        instance_id = GlobalConfig.get("server", "instance_id")
        signing_key = self.__read_key("sign_current")
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
        Create a JWE token whose "claims" set (payload) is a signed JWT.
        """
        self.jwt = self.__create_jwt()
        encryption_key = self.__read_key("encrypt_current")
        encryption_parameters = {
            "alg": self.config.get("defaults", "encryption_algorithm"),
            "enc": self.config.get("defaults", "encryption_mode")
        }
        payload = self.jwt.serialize()
        self.jwe = jwt.JWT(header=encryption_parameters, claims=payload)
        self.jwe.make_encrypted_token(encryption_key)

    def __decrypt_jwe(self, token, keyname):
        """
        Try decrpyting a JWE with a key. If successful, return true.
        """
        try:
            self.jwe = jwt.JWT(key=self.jwk[keyname], jwt=token)
            return True
        except:
            return False

    def __check_jwe(self, token):
        """
        Given a serialized blob, parse it as a JWE token. If it fails, return
        false. If it succeeds, return true, and set self.jwe to be the
        serialized JWT inside the JWE.
        """
        for keyname in ["encrypt_current", "encrypt_last"]:
            if self.__decrypt_jwe(token, keyname) is True:
                return True
        return False

    def __raw_cookie_to_token(self, raw_cookies):
        """
        Split out just the JWE part of the cookie. Since we split
        """
        syslog.syslog(str(raw_cookies))
        for raw_data in raw_cookies.split(';'):
            raw_cookie = raw_data.lstrip()
            cookie_name = raw_cookie.split('=')[0]
            token = raw_cookie.split('=')[1]
            if cookie_name == self.cookie_name:
                return token
        return None

    def __validate_jwt(self, serial, keyname):
        """
        Try validating the signature of a JWT and its claims.
        If successful, return true.
        """
        try:
            # TODO: How to check date prior to signing?
            syslog.syslog("serial: " + str(serial))
            syslog.syslog("key: " + str(self.jwk[keyname]))
            self.jwt = jwt.JWT(key=self.jwk[keyname], jwt=serial)
            return True
        except Exception as err:
            syslog.syslog("JWT validation error: " + err.message)
            return False

    def __check_jwt(self, serial):
        """
        Given a serialized blob, parse it as a JWT token. If it fails, return
        false. If it succeeds, return true, and set self.jwt to be the JWT.
        """
        for keyname in ["sign_current", "sign_last"]:
            if self.__validate_jwt(serial, keyname) is True:
                return True
            else:
                pass
        return False

    def check_token(self, cookie):
        """
        Process a JWE token. In Constantina these come from the users' cookie.
        If all the validation works, self.jwt becomes a valid JWT, read in the
        JWT's claims, and return True.
        If any part of this fails, do not set a cookie and return False.
        """
        token = self.__raw_cookie_to_token(cookie)
        if token is None:
            return False
        if self.__check_jwe(token) is True:
            syslog.syslog("jwe passed")
            if self.__check_jwt(self.jwe.claims) is True:
                self.serial = self.jwe.serialize()
                syslog.syslog("serial: " + self.serial)
                self.__read_jwt_claims()
                return True
        return False

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
        [key, value] = vals.split('=')
        post[key] = value

    auth = ConstantinaAuth("password", username=post["username"], password=post["password"])
    auth.set_token()
    return auth


def show_authentication(env):
    """
    TODO: Received a GET with a cookie.
    """
    if 'HTTP_COOKIE' in env:
        raw_cookie = env['HTTP_COOKIE']
        auth = ConstantinaAuth("cookie", cookie=raw_cookie)
        return auth
    else:
        auth = ConstantinaAuth("fail")
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