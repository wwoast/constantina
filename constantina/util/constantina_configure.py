#!/usr/bin/python

from getpass import getuser, getpass
import os
import sys
from random import randint
import argparse
import ConfigParser
from socket import getfqdn
from passlib.hash import argon2
from pwd import getpwnam
from grp import getgrnam


HelpStrings = {
    'add_user': "create a Constantina user account",
    'delete_user': "remove a Constantina user account",
    'password': "set password for a Constantina user account",
    'revoke_logins': "delete stored session keys, forcing users to re-login",
    'config_root': "path to the configuration and private data root directory",
    'cgi_bin': "path to the directory containing CGI scripts",
    'instance': "config directory isolation: /etc/constantina/<instance>",
    'hostname': "hostname that Constantina will run on",
    'port': "localhost-bound port that Constantina runs on (and Apache/Nginx proxies to)",
    'data_root': "where Constantina html resources are served from",
    'username': "the Unix username that Constantina data is owned by",
    'groupname': "the Unix groupname that Constantina data is owned by",
    'upgrade': "install just the Python and HTML code, not any sample cards or config",
    'scriptonly': "install just the Python scripts, not any HTML or sample cards or config"
}

class ConstantinaDefaults:
    def __init__(self):
        self.add_user = None
        self.delete_user = None
        self.password = None
        self.instance = "default"
        self.revoke_logins = False
        self.hostname = getfqdn()
        self.port = str(randint(44000, 44500))   # Random local listener port
        self.username = getuser()   # Unix user account the server runs in
        self.groupname = getuser()   # Unix group account the server runs in
        self.config_root = sys.prefix + "/etc/constantina"
        self.data_root = sys.prefix + "/var/www/constantina"
        self.cgi_bin = sys.prefix + "/var/cgi-bin/constantina"
        self.templates = sys.prefix + "/etc/constantina/templates"
        if sys.prefix == "/usr":
            # Default prefix? Unprefix the target directories
            self.data_root = "/var/www/constantina"
            self.config_root = "/etc/constantina"
            self.cgi_bin = "/var/cgi-bin/constantina"
            self.templates = "/etc/constantina/templates"


class ConstantinaConfig:
    """
    Support writing the most basic types of Constantina config, such as the
    hostname, webserver user account, and config paths. This is run through
    the setup.py install script in addition to the configuration script itself.
    """
    def __init__(self):
        self.settings = ConfigParser.SafeConfigParser(allow_no_value=True)
        self.uwsgi = ConfigParser.SafeConfigParser(allow_no_value=True)
        self.default = ConstantinaDefaults()
        self.add_user = self.default.add_user
        self.delete_user = self.default.delete_user
        self.password = self.default.password
        self.revoke_logins = self.default.revoke_logins
        self.instance = self.default.instance
        self.hostname = self.default.hostname
        self.port = self.default.port
        self.data_root = self.default.data_root
        self.username = self.default.username
        self.groupname = self.default.groupname
        self.config_root = self.default.config_root
        self.cgi_bin = self.default.cgi_bin
        self.templates = self.default.templates

    def configure(self, config, section, option, value):
        """
        Don't overwrite config values with None.
        TODO: if value to be set is just a default value, and there's already
        a value in place, do not replace the existing value unless it was
        specifically given at the command line!
        """
        if value is not None:
            config.set(section, option, value)

    def opaque_instance(self):
        """
        Create an opaque instance ID, so that cookies for multiple Constantina
        instances on the same domain name, don't squash each other. It's a random
        number, converted to a BASE62 minus similar characters list.
        """
        random_id = randint(0, 2**32-1)
        base = '23456789abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ'
        length = len(base)
        opaque = ''
        while random_id != 0:
            opaque = base[random_id % length] + opaque
            random_id /= length
        return opaque

    def update_configs(self):
        """Make config changes once the config files are staged"""
        self.settings.read(self.config_root + "/constantina.ini")
        self.configure(self.settings, "server", "hostname", self.hostname)
        self.configure(self.settings, "server", "port", self.port)
        self.configure(self.settings, "server", "username", self.username)
        self.configure(self.settings, "server", "groupname", self.username)
        self.configure(self.settings, "paths", "data_root", self.data_root)
        self.configure(self.settings, "paths", "config_root", self.config_root)
        self.configure(self.settings, "paths", "cgi_bin", self.cgi_bin)
        self.configure(self.settings, "server", "instance_id", self.opaque_instance())
        with open(self.config_root + "/constantina.ini", "wb") as cfh:
            self.settings.write(cfh)

        # Set UWSGI config file settings for this instance too
        self.uwsgi.read(self.config_root + "/uwsgi.ini")
        self.configure(self.uwsgi, "uwsgi", "chdir", self.data_root)
        self.configure(self.uwsgi, "uwsgi", "env", "INSTANCE=" + self.instance)
        self.configure(self.uwsgi, "uwsgi", "procname", "constantina-" + self.instance)
        if self.hostname is not None:
            self.configure(self.uwsgi, "uwsgi", "socket", self.hostname + ":" + str(self.port))
        with open(self.config_root + "/uwsgi.ini", "wb") as ufh:
            self.uwsgi.write(ufh)

    def update_instance_directory(self, directory, suffix=''):
        """Add instance to the end of the chosen directory"""
        to_update = getattr(self, directory)
        default = getattr(self.default, directory)
        if to_update == default and default is not None:
            setattr(self, directory, to_update + "/" + self.instance + suffix)

    def import_parsed(self, namespace):
        """
        Take the output of parse_known_args and set them in this class.
        Update the config directory to represent the instance being used.
        """
        for item in namespace.__dict__.iteritems():
            setattr(self, item[0], item[1])
        self.update_instance_directory("config_root")
        self.update_instance_directory("cgi_bin")
        self.update_instance_directory("data_root")

    def chown_installed_files(self):
        """
        Recurse through the root/config/cgi directories and make sure that
        files in there are owned by the configured user and group.
        """
        uid = getpwnam(self.username)[2]
        gid = getgrnam(self.groupname)[2]
        for path in [self.data_root, self.config_root, self.cgi_bin]:
            if path is None:
                continue
            for root, dirs, files in os.walk(path, topdown=False):
                for entry in files:
                    os.chown(os.path.join(root, entry), uid, gid)
                for entry in dirs:
                    os.chown(os.path.join(root, entry), uid, gid)
            os.chown(path, uid, gid)


class ShadowConfig:
    """
    Configure keys and user accounts through the command line. Pass the
    configuration directory so we know what instance we're dealing with.
    """
    def __init__(self, config_root):
        """Read in the shadow.ini config file and settings."""
        self.settings = ConfigParser.SafeConfigParser(allow_no_value=True)
        self.config_root = config_root
        self.settings.read(self.config_root + "/shadow.ini")
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
        with open(self.config_root + "/shadow.ini", "wb") as cfh:
            self.settings.write(cfh)
        # Update the detection for whether an admin exists, so we don't
        # get asked to add an admin account more than once
        self.admin_exists = self.settings.has_option("passwords", "admin")

    def delete_user(self, username):
        """Remove an account from the shadow file"""
        self.settings.remove_option("passwords", username)
        with open(self.config_root + "/shadow.ini", "wb") as cfh:
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


def install_arguments():
    """
    When installing Constantina, aggressively replace values where-ever possible with
    default values, when not-specified on the commandline.

    Take in CLI options, using preconfigured defaults if any are missing.
    Nargs=? means that if an argument is missing, use a default value instead.
    """
    conf = ConstantinaConfig()
    args = argparse.Namespace

    parser = argparse.ArgumentParser()
    parser.add_argument("-a", "--add-user", nargs='?', help=HelpStrings['add_user'])
    parser.add_argument("-d", "--delete-user", nargs='?', help=HelpStrings['delete_user'])
    parser.add_argument("-p", "--password", nargs='?', help=HelpStrings['password'])
    parser.add_argument("-c", "--config-root", nargs='?', help=HelpStrings['config_root'], default=conf.default.config_root)
    parser.add_argument("-b", "--cgi-bin", nargs='?', help=HelpStrings['cgi_bin'], default=conf.default.cgi_bin)
    parser.add_argument("-i", "--instance", nargs='?', help=HelpStrings['instance'], default=conf.default.instance)
    parser.add_argument("-n", "--hostname", nargs='?', help=HelpStrings['hostname'], default=conf.default.hostname)
    parser.add_argument("-P", "--port", nargs='?', help=HelpStrings['port'], default=conf.default.port)
    parser.add_argument("-r", "--data-root", nargs='?', help=HelpStrings['data_root'], default=conf.default.data_root)
    parser.add_argument("-u", "--username", nargs='?', help=HelpStrings['username'], default=conf.default.username)
    parser.add_argument("-g", "--groupname", nargs='?', help=HelpStrings['groupname'], default=conf.default.groupname)
    parser.add_argument("-k", "--revoke-logins", help=HelpStrings['revoke_logins'], action='store_true')
    parser.parse_known_args(namespace=args)

    conf.import_parsed(args)
    return conf


def configure_arguments():
    """
    Take in command-line options, using preconfigured defaults only if necessary
    for variables that are needed to run the script. If a value doesn't exist on
    the commandline, but is in the configuration, keep that value.

    Nargs=? means that if an argument is missing, use a default value instead.
    """
    conf = ConstantinaConfig()
    args = argparse.Namespace

    parser = argparse.ArgumentParser()
    parser.add_argument("-a", "--add-user", nargs='?', help=HelpStrings['add_user'])
    parser.add_argument("-d", "--delete-user", nargs='?', help=HelpStrings['delete_user'])
    parser.add_argument("-p", "--password", nargs='?', help=HelpStrings['password'])
    parser.add_argument("-c", "--config-root", nargs='?', help=HelpStrings['config_root'], default=conf.default.config_root)
    parser.add_argument("-b", "--cgi-bin", nargs='?', help=HelpStrings['cgi_bin'])
    parser.add_argument("-i", "--instance", nargs='?', help=HelpStrings['instance'], default=conf.default.instance)
    parser.add_argument("-n", "--hostname", nargs='?', help=HelpStrings['hostname'])
    parser.add_argument("-P", "--port", nargs='?', help=HelpStrings['port'])
    parser.add_argument("-r", "--data-root", nargs='?', help=HelpStrings['data_root'])
    parser.add_argument("-u", "--username", nargs='?', help=HelpStrings['username'], default=conf.default.username)
    parser.add_argument("-g", "--groupname", nargs='?', help=HelpStrings['groupname'], default=conf.default.groupname)
    parser.add_argument("-k", "--revoke-logins", help=HelpStrings['revoke_logins'], action='store_true')
    parser.parse_known_args(namespace=args)

    conf.import_parsed(args)
    return conf


def user_management():
    accounts = ShadowConfig(conf.config_root)
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
    conf = configure_arguments()
    # Write the command-line settings to constantina.ini
    conf.update_configs()
    # Change the ownership of any files that were installed
    # TODO: only run in install mode?
    conf.chown_installed_files()
    # If a username or password was provided, add an account to shadow.ini
    if (conf.add_user is not None or
        conf.delete_user is not None or
        conf.revoke_logins is True):
           user_management()
