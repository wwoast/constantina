#!/usr/bin/python

from getpass import getuser, getpass
import sys
import argparse
import ConfigParser
from socket import gethostname
from passlib.hash import argon2


HelpStrings = {
       'add_user': "create a Constantina user account",
    'delete_user': "remove a Constantina user account",
       'password': "set password for a Constantina user account",
         'config': "path to the configuration directory",
       'instance': "config directory isolation: /etc/constantina/<instance>",
       'hostname': "hostname that Constantina will run on",
           'root': "where Constantina html resources are served from",
           'user': "the Unix username that Constantina data is owned by",
          'force': "force overwrite existing configurations"
}

class ConstantinaDefaults:
    def __init__(self):
        self.add_user = None
        self.delete_user = None
        self.password = None
        self.instance = "default"
        self.force = False
        self.hostname = gethostname()
        self.root = "/var/www/constantina"
        self.user = getuser()   # Unix user account the server runs in
        self.config = sys.prefix + "/etc/constantina/" + self.instance
        self.templates = sys.prefix, "/etc/constantina/templates"
        if sys.prefix == "/usr":
            # Default prefix? Just put config in /etc
            self.config = "/etc/constantina/" + self.instance
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
        # WTF, why is initializing to None for subvalues breaking things here?

    def configure(self, section, option, value):
        """
        Is a config value set already? If force=True, overwrite it with
        a new value. Otherwise, only replace config values that are not
        currently defined.
        """
        test = self.settings.get(section, option)
        # if test == None or self.force==True:
        self.settings.set(section, option, value)

    def update_configs(self):
        """Make config changes once the config files are staged"""
        self.settings.read(self.config + "/constantina.ini")
        self.configure("server", "hostname", self.hostname)
        self.configure("server", "user", self.user)
        self.configure("paths", "root", self.root)
        self.configure("paths", "config", self.config)

        with open(self.config + "/constantina.ini", "wb") as cfh:
            self.settings.write(cfh)

    def accept_input(self, prompt, default):
        """Wrapper to raw_input that accepts a default value."""
        value = raw_input(prompt + " <" + default + ">: ")
        if value == '':
            value = default
        return value

    def read_inputs(self, prompt):
        """Any values that still need to be set should be processed here."""
        pass


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
        self.admin_exists = (self.settings.get("passwords", "admin") == None)
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

    def configure(self, section, option, value):
        """
        Is a config value set already? If force=True, overwrite it with
        a new value. Otherwise, only replace config values that are not
        currently defined.
        """
        test = self.settings.get(section, option)
        # if test == None or self.force==True:
        self.settings.set(section, option, value)

    def add_user(self, username, password=None):
        """
        Add a user to the shadow file. If no password is given, prompt for one.
        """
        print "Adding new Constantina user %s" % (username)
        if password == None:
            prompt = "Password for %s: " % (username)
            password = getpass(prompt=prompt)
        pwhash = argon2.hash(password)
        self.configure("passwords", username, pwhash)
        with open(self.config + "/shadow.ini", "wb") as cfh:
            self.settings.write(cfh)

    def remove_user(self, username):
        """Remove an account from the shadow file"""
        self.settings.remove_option("passwords", username)

    def update_key(self, keyname):
        """Use existing functions to do this"""
        pass


def read_arguments():
    """
    Take in command-line options, using preconfigured defaults if any are
    missing. Nargs=? means that if an argument is missing, use a default
    value instead.
    """
    c = ConstantinaConfig()

    parser = argparse.ArgumentParser()
    parser.add_argument("-a", "--add_user", nargs='?', help=HelpStrings['add_user'])
    parser.add_argument("-d", "--delete_user", nargs='?', help=HelpStrings['delete_user'])
    parser.add_argument("-p", "--password", nargs='?', help=HelpStrings['password'])
    parser.add_argument("-c", "--config", nargs='?', help=HelpStrings['config'], default=c.default.config)
    parser.add_argument("-i", "--instance", nargs='?', help=HelpStrings['instance'], default=c.default.instance)
    parser.add_argument("-n", "--hostname", nargs='?', help=HelpStrings['hostname'], default=c.default.hostname)
    parser.add_argument("-r", "--root", nargs='?', help=HelpStrings['root'], default=c.default.root)
    parser.add_argument("-u", "--user", nargs='?', help=HelpStrings['user'], default=c.default.user)
    parser.add_argument("--force", help=HelpStrings['force'], action='store_true', default=c.default.force)
    parser.parse_known_args(namespace=c)
    return c


if __name__ == '__main__':
    # Read the command-line settings into the conf object
    conf = read_arguments()
    # Write the command-line settings to constantina.ini
    conf.update_configs()
    # If a username or password was provided, add an account to shadow.ini
    accounts = ShadowConfig(conf.config, conf.force)
    if conf.add_user != None:
        accounts.add_user(conf.add_user, conf.password)
    # If we didn't make the admin user on first blush, and no admin exists,
    # create an admin account now as well.
    if accounts.admin_exists == False:
        accounts.add_user("admin")

    # TODO: won't work if config dir doesn't exist. Have something to copy templates
