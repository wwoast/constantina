#!/usr/bin/python

import ConfigParser

def accept_input(self, prompt, default):
    """Wrapper to raw_input that accepts a default value."""
    value = raw_input(prompt + " <" + default + ">: ")
    if value == '':
        value = default
    return value


def update_configs(self):
    """Make config changes once the config files are staged"""
    config = ConfigParser.SafeConfigParser()
    config.read(self.config_path + "/constantina.ini")
    config.set("domain", "hostname", self.domain)
    config.set("paths", "root", self.web_root)
    config.set("paths", "config", self.config_path)

    with open(self.config_path + "/constantina.ini", "wb") as cfh:
        config.write(cfh)

