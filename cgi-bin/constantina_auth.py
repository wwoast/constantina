import os
from sys import stdin
from uuid import uuid4
import ConfigParser
import syslog
import json
from jwcrypto import jws, jwk, jwt
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
        self.lifetime = self.config.getint("key_settings", "lifetime")
        self.sunset = self.config.getint("key_settings", "sunset")
        self.regen_jwk = []
        self.jwk = {}       # One of N keys for signing/encryption
        self.jwk_iat = {}   # Expiry dates for the JWKs
        self.token = None
        self.aud = None     # JWT audience (i.e. hostname)
        self.exp = None     # JWT expiration time
        self.iat = None     # JWT issued-at time
        self.nbf = None     # JWT not-before time
        self.sub = None     # JWT subject (subject_id/uesrname)
        

    def __read_shadow_settings(self):
        """
        Read in settings from the shadow.ini config file so we can track what
        the token expiry settings we care about might be.
        """
        self.lifetime = self.config.getint("key_settings", "lifetime")
        self.sunset = self.config.getint("key_settings", "sunset")
        self.time = jwt.time.time()

        for keyname in ["key_last", "key_current"]:
            keydate = self.config.getint(keyname, "date")
            if self.time > (keydate + self.sunset):
                self.regen_jwk.append(keyname)


    def __regen_all_jwk(self):
        """
        Regenerate any expired JWK shared secret keys in the config file.
        """
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
        data = json.loads(self.jwk[name].export())
        for hash_key in data.keys:
            self.config.set(self.jwk[name], hash_key, data[hash_key])
        # When did we create this key? Record this detail
        self.jwk_iat[name] = int(jwt.time.time())
        self.config.set(name, "date", self.jwk_iat[name])


    def __read_key(self, name):
        """
        Read the desired key from the configuration file, and load it as
        a JWK for purpose of signing or encryption. Parameters here that are
        not part of the JWK structure are stored in metadata{} instead.
        Persist the JWK key itself by "name" into the self.jwk{} dict
        """
        jwk_data = {}
        metadata = {}
        exclude = ["date"]
        for hash_key, value in self.config.items(name):
            jwk_data[hash_key] = value
        for field in exclude:
            metadata[field] = jwk_data[field]
            del jwk_data[field]
        self.jwk[name] = json.dumps(jwk_data)   # Equivalent to the jwk.JWK call
        self.jwk_iat[name] = metadata["date"]


    def __create_jwt(self):
        """
        Create a signed JWT with the key_current, and define any of the
        signed claims that are of interest
        """
        signing_algorithm = self.config.get("defaults", "signing_algorithm")
        subject_id = self.config.get("defaults", "subject_id")
        signing_key = self.__read_key("key_current")
        self.iat = int(jwt.time.time())
        self.aud = GlobalConfig.get("domain", "hostname")
        self.sub = subject_id + "/" + self.user.username
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
        self.token = jwt.JWT(header=header, claims=claims)
        self.token.make_signed_token(signing_key)


    def __create_jwe(self):
        """
        Create a JWE token.
        """
        self.token = self.__create_jwt()
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
            self.__create_jwt()


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
        return len(self.password) < self.config.getint('defaults', 'password_length')


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
