#!/usr/bin/python

from getpass import getuser, getpass
import os
import sys
import argparse
import ConfigParser
from socket import gethostname
from passlib.hash import argon2


HelpStrings = {
    'add_user': "create a Constantina user account",
    'delete_user': "remove a Constantina user account",
    'password': "set password for a Constantina user account",
    'revoke_logins': "delete stored session keys, forcing users to re-login",
    'config': "path to the configuration directory",
    'instance': "config directory isolation: /etc/constantina/<instance>",
    'hostname': "hostname that Constantina will run on",
    'webroot': "where Constantina html resources are served from",
    'username': "the Unix username that Constantina data is owned by",
    'force': "force overwrite existing configurations"
}

class ConstantinaDefaults:
    def __init__(self):
        self.add_user = None
        self.delete_user = None
        self.password = None
        self.instance = "default"
        self.revoke_logins = False
        self.force = False
        self.hostname = gethostname()
        self.webroot = "/var/www/constantina"
        self.username = getuser()   # Unix user account the server runs in
        self.config = sys.prefix + "/etc/constantina"
        self.templates = sys.prefix, "/etc/constantina/templates"
        if sys.prefix == "/usr":
            # Default prefix? Just put config in /etc
            self.config = "/etc/constantina"
            self.templates = "/etc/constantina/templates"


class ConstantinaConfig:
    """
    Support writing the most basic types of Constantina config, such as the
    hostname, webserver user account, and config paths. This is run through
    the setup.py install script in addition to the configuration script itself.
    """
    def __init__(self):
        self.settings = ConfigParser.SafeConfigParser(allow_no_value=True)
        self.default = ConstantinaDefaults()
        self.add_user = self.default.add_user
        self.delete_user = self.default.delete_user
        self.password = self.default.password
        self.revoke_logins = self.default.revoke_logins
        self.instance = self.default.instance
        self.force = self.default.force
        self.hostname = self.default.hostname
        self.webroot = self.default.webroot
        self.username = self.default.username
        self.config = self.default.config
        self.templates = self.default.templates

    def configure(self, section, option, value):
        """
        Is a config value set already? If force=True, overwrite it with
        a new value. Otherwise, only replace config values that are not
        currently defined.
        """
        #test = self.settings.get(section, option)
        #if test == None or self.force==True:
        self.settings.set(section, option, value)

    def update_configs(self):
        """Make config changes once the config files are staged"""
        self.settings.read(self.config + "/constantina.ini")
        self.configure("server", "hostname", self.hostname)
        self.configure("server", "username", self.username)
        self.configure("paths", "webroot", self.webroot)
        self.configure("paths", "config", self.config)

        with open(self.config + "/constantina.ini", "wb") as cfh:
            self.settings.write(cfh)

    def update_instance_directory(self):
        """Add instance to the end of the config directory"""
        if self.config == self.default.config:
            self.config = self.config + "/" + self.instance
        #instance_config = self.config + "/constantina.ini"
        #TODO: Determine if install or configure mode
        #if not os.path.isfile(instance_config):
        #    raise Exception("File not found: \"%s\". Instance \"%s\" not installed?" 
        #        % (instance_config, self.instance))
        #    sys.exit(-1)

    def import_parsed(self, namespace):
        """
        Take the output of parse_known_args and set them in this class.
        Update the config directory to represent the instance being used.
        """
        for item in namespace.__dict__.iteritems():
            setattr(self, item[0], item[1])
        self.update_instance_directory()


class ShadowConfig:
    """
    Configure keys and user accounts through the command line. Pass the
    configuration directory so we know what instance we're dealing with.
    """
    def __init__(self, config, force=True):
        """Read in the shadow.ini config file and settings."""
        self.settings = ConfigParser.SafeConfigParser(allow_no_value=True)
        self.config = config
        self.force = force
        self.settings.read(self.config + "/shadow.ini")
        self.admin_exists = self.settings.has_option("passwords", "admin")
        self.argon2_setup()

    def argon2_setup(self):
        """
        Read argon2 algorithm and backend settings from the config file
        """
        # TODO: Make these apply regardless of backend?
        self.v = self.settings.get("argon2", "v")
        self.m = self.settings.get("argon2", "m")
        self.t = self.settings.get("argon2", "t")
        self.p = self.settings.get("argon2", "p")
        backend = self.settings.get("argon2", "backend")
        argon2.set_backend(backend)

    def add_user(self, username, password=None):
        """
        Add a user to the shadow file. If no password is given, prompt for one.
        """
        print "Adding new Constantina user %s" % (username)
        if password == None:
            prompt = "Password for %s: " % (username)
            password = getpass(prompt=prompt)
        pwhash = argon2.hash(password)
        self.settings.set("passwords", username, pwhash)
        with open(self.config + "/shadow.ini", "wb") as cfh:
            self.settings.write(cfh)
        # Update the detection for whether an admin exists, so we don't
        # get asked to add an admin account more than once
        self.admin_exists = self.settings.has_option("passwords", "admin")

    def delete_user(self, username):
        """Remove an account from the shadow file"""
        self.settings.remove_option("passwords", username)
        with open(self.config + "/shadow.ini", "wb") as cfh:
            self.settings.write(cfh)
        # Don't recreate an admin that we just deleted (no admin update here)

    def __delete_key(self, keyname):
        """Delete an arbitrary key from the shadow configuration"""
        for item in self.settings.items(keyname):
            self.settings.remove_option(item[0], item[1])

    def delete_keys(self):
        """
        Delete all sets of keys. This will guarantee that all usres will need
        to log back in with their current credentials.
        """
        self.__delete_key("encrypt_last")
        self.__delete_key("sign_last")
        self.__delete_key("encrypt_current")
        self.__delete_key("sign_current")


def read_arguments():
    """
    Take in command-line options, using preconfigured defaults if any are
    missing. Nargs=? means that if an argument is missing, use a default
    value instead.
    """
    conf = ConstantinaConfig()
    args = argparse.Namespace

    parser = argparse.ArgumentParser()
    parser.add_argument("-a", "--add_user", nargs='?', help=HelpStrings['add_user'])
    parser.add_argument("-d", "--delete_user", nargs='?', help=HelpStrings['delete_user'])
    parser.add_argument("-p", "--password", nargs='?', help=HelpStrings['password'])
    parser.add_argument("-c", "--config", nargs='?', help=HelpStrings['config'], default=conf.default.config)
    parser.add_argument("-i", "--instance", nargs='?', help=HelpStrings['instance'], default=conf.default.instance)
    parser.add_argument("-n", "--hostname", nargs='?', help=HelpStrings['hostname'], default=conf.default.hostname)
    parser.add_argument("-r", "--webroot", nargs='?', help=HelpStrings['webroot'], default=conf.default.webroot)
    parser.add_argument("-u", "--username", nargs='?', help=HelpStrings['username'], default=conf.default.username)
    parser.add_argument("-k", "--revoke_logins", help=HelpStrings['revoke_logins'], action='store_true')
    parser.add_argument("-f", "--force", help=HelpStrings['force'], action='store_true')
    parser.parse_known_args(namespace=args)

    conf.import_parsed(args)
    return conf


def user_management():
    accounts = ShadowConfig(conf.config, conf.force)
    if conf.add_user != None:
        accounts.add_user(conf.add_user, conf.password)
    if conf.delete_user != None:
        accounts.delete_user(conf.delete_user)
    if conf.revoke_logins is True:
        accounts.delete_keys()
    # If we didn't make the admin user on first blush, and no admin exists,
    # create an admin account now as well.
    if accounts.admin_exists is False:
        accounts.add_user("admin")


if __name__ == '__main__':
    # Read the command-line settings into the conf object
    conf = read_arguments()
    # Write the command-line settings to constantina.ini
    conf.update_configs()
    # If a username or password was provided, add an account to shadow.ini
    if (conf.add_user != None or
        conf.delete_user != None or
        conf.revoke_logins is True):
           user_management()
