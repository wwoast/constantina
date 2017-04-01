#!/usr/bin/python

import sys
import argparse
import ConfigParser
from socket import gethostname


class ConstantinaDefaults:
    def __init__(self):
        self.instance = "default"
        self.config = sys.prefix + "/etc/constantina/" + self.instance
        self.force = False
        self.hostname = gethostname()
        self.root = "/var/www/constantina"
        if sys.prefix == "/usr":
            # Default prefix? Just put config in /etc
            self.config = "/etc/constantina/" + self.instance


class ConstantinaConfig:
    """
    Data in this object is written to a config file. Defaults are
    defined using the argparse library.
    """
    def __init__(self):
        self.settings = ConfigParser.SafeConfigParser(allow_no_value=True)
        self.exception_exists = Exception("value already set: %s %s %s")
        self.default = ConstantinaDefaults()

    def configure(self, section, option, value, force=False):
        """
        Is a config value set already? If force=True, overwrite it with
        a new value. Otherwise, only replace config values that are not
        currently defined.
        """
        test = self.settings.get(section, option)
        if test == None or force==True:
            self.settings.set(section, option, value)
        else:
            raise self.exception_exists % (section, option, test)

    def update_configs(self):
        """Make config changes once the config files are staged"""
        self.settings.read(self.config + "/constantina.ini")
        self.configure("domain", "hostname", self.hostname, self.force)
        self.configure("paths", "root", self.root, self.force)
        self.configure("paths", "config", self.config, self.force)
    
        with open(self.config + "/constantina.ini", "wb") as cfh:
            self.config.write(cfh)

    def accept_input(self, prompt, default):
        """Wrapper to raw_input that accepts a default value."""
        value = raw_input(prompt + " <" + default + ">: ")
        if value == '':
            value = default
        return value

    def read_inputs(self, prompt):
        """Any values that still need to be set should be processed here."""
        pass



def main():
    """
    Take in command-line options, using preconfigured defaults if any are
    missing. Nargs=? means that if an argument is missing, use a default
    value instead.
    """
    c = ConstantinaConfig()

    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--instance", nargs='?', help="config directory isolation: /etc/constantina/<instance>", default=c.default.instance)
    parser.add_argument("-n", "--hostname", nargs='?', help="hostname that Constantina will run on", default=c.default.hostname)
    parser.add_argument("-c", "--config", nargs='?', help="path to the configuraiton directory", default=c.default.config)
    parser.add_argument("-r", "--root", nargs='?', help="where Constantina publichtml resources are served from", default=c.default.root)
    parser.add_argument("--force", help="force overwrite existing configurations", action='store_true', default=c.default.force)
    parser.parse_args(namespace=c)


if __name__ == '__main__':
    main()    
