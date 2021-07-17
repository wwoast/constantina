#!/usr/bin/python3

from getpass import getuser
import os
import sys
from random import randint
import argparse
import configparser
from socket import getfqdn
from pwd import getpwnam
from grp import getgrnam


HelpStrings = {
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
        self.instance = "default"
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
        self.settings = configparser.SafeConfigParser(allow_no_value=True)
        self.uwsgi = configparser.SafeConfigParser(allow_no_value=True)
        self.default = ConstantinaDefaults()
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

    def update_configs(self):
        """Make config changes once the config files are staged"""
        self.settings.read(self.config_root + "/constantina.ini", encoding='utf-8')
        self.configure(self.settings, "paths", "data_root", self.data_root)
        self.configure(self.settings, "paths", "config_root", self.config_root)
        self.configure(self.settings, "paths", "cgi_bin", self.cgi_bin)
        with open(self.config_root + "/constantina.ini", "w", encoding='utf-8') as cfh:
            self.settings.write(cfh)

        # Set UWSGI config file settings for this instance too
        self.uwsgi.read(self.config_root + "/uwsgi.ini", encoding='utf-8')
        self.configure(self.uwsgi, "uwsgi", "chdir", self.data_root)
        self.configure(self.uwsgi, "uwsgi", "env", "INSTANCE=" + self.instance)
        self.configure(self.uwsgi, "uwsgi", "procname", "constantina-" + self.instance)
        if self.hostname is not None:
            self.configure(self.uwsgi, "uwsgi", "socket", self.hostname + ":" + str(self.port))
        with open(self.config_root + "/uwsgi.ini", "w", encoding='utf-8') as ufh:
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
        for item in namespace.__dict__.items():
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
    parser.add_argument("-c", "--config-root", nargs='?', help=HelpStrings['config_root'], default=conf.default.config_root)
    parser.add_argument("-b", "--cgi-bin", nargs='?', help=HelpStrings['cgi_bin'], default=conf.default.cgi_bin)
    parser.add_argument("-i", "--instance", nargs='?', help=HelpStrings['instance'], default=conf.default.instance)
    parser.add_argument("-n", "--hostname", nargs='?', help=HelpStrings['hostname'], default=conf.default.hostname)
    parser.add_argument("-P", "--port", nargs='?', help=HelpStrings['port'], default=conf.default.port)
    parser.add_argument("-r", "--data-root", nargs='?', help=HelpStrings['data_root'], default=conf.default.data_root)
    parser.add_argument("-u", "--username", nargs='?', help=HelpStrings['username'], default=conf.default.username)
    parser.add_argument("-g", "--groupname", nargs='?', help=HelpStrings['groupname'], default=conf.default.groupname)
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
    parser.add_argument("-c", "--config-root", nargs='?', help=HelpStrings['config_root'], default=conf.default.config_root)
    parser.add_argument("-b", "--cgi-bin", nargs='?', help=HelpStrings['cgi_bin'])
    parser.add_argument("-i", "--instance", nargs='?', help=HelpStrings['instance'], default=conf.default.instance)
    parser.add_argument("-n", "--hostname", nargs='?', help=HelpStrings['hostname'])
    parser.add_argument("-P", "--port", nargs='?', help=HelpStrings['port'])
    parser.add_argument("-r", "--data-root", nargs='?', help=HelpStrings['data_root'])
    parser.add_argument("-u", "--username", nargs='?', help=HelpStrings['username'], default=conf.default.username)
    parser.add_argument("-g", "--groupname", nargs='?', help=HelpStrings['groupname'], default=conf.default.groupname)
    parser.parse_known_args(namespace=args)

    conf.import_parsed(args)
    return conf


if __name__ == '__main__':
    # Read the command-line settings into the conf object
    conf = configure_arguments()
    # Write the command-line settings to constantina.ini
    conf.update_configs()
    # Change the ownership of any files that were installed
    # TODO: only run in install mode?
    conf.chown_installed_files()
