#!/usr/bin/env python

import distutils
from distutils.core import setup
import sys
import ConfigParser

"""
constantina installer script. Based on the configuration settings in
constantina.ini, generate initial jws/jwk values, an initial admin
password, and move all relevant files into their final directories.
"""

class SetupConfig:
    def __init__(self):
        self.instance_name = "default"
        self.config_path = ""
        self.domain = ""
        self.web_root = ""

        self.distutils_args = {
            'name': "constantina",
            'version': "0.5.0-alpha",
            'description': "a dynamic-content blog platform for \"grazing\"",
            'author': "Justin Cassidy",
            'author_email': 'boil.afraid@gmail.com',
            'url': 'https://github.com/wwoast/constantina',
            'classifiers':"""Programming Language :: Python
Programming Language :: Python :: 2
Programming Language :: Python :: 2.7""".splitlines(),
        
            'packages': [
                'constantina',
                'constantina.medusa',
                'constantina.zoo',
                # 'constantina.dracula',
            ],
        }


    def accept_input(self, prompt, default):
        """Wrapper to raw_input that accepts a default value."""
        value = raw_input(prompt + " <" + default + ">: ")
        if value == '':
            value = default
        return value


    def data_files(self):
        """
        Install the html data in the directory of your choosing, by default
        /var/www/<hostname>/constantina. TOWRITE

        Install config files for Constantina in /etc/constantina unless we're 
        using a special config prefix like /usr/local, in which case we put
        configs in /usr/local/etc/constantina.
        """
        self.config_path = sys.prefix + "/etc/constantina/" + self.instance_name
        if sys.prefix == "/usr":
            self.config_path = "/etc/constantina/" + self.instance_name

        self.distutils_args['data_files'] = [
            (self.config_path, ["config/constantina.ini", 
                                "config/medusa.ini", 
                                "config/zoo.ini"])
        ]


    def site_specifics(self):
        """
        Read in values for setting up Constantina, including:
        - Name of the Constantina instance [test/staging/prod/<name>]
        - The domain this instance will be listening on
        - The webroot that Constantina's HTML will copy into
        """
        self.instance_name = self.accept_input("Instance name", "default")
        self.domain = self.accept_input("FQDN that Constantina will run on", "example.com")
        self.web_root = self.accept_input("Web root path where Constantina instance HTML is found\n", "/var/www/constantina")


    def update_configs(self):
        """Make config changes once the config files are staged"""
        config = ConfigParser.SafeConfigParser()
        config.read(self.config_path + "/constantina.ini")
        config.set("domain", "hostname", self.domain)
        config.set("paths", "root", self.web_root)
        config.set("paths", "config", self.config_path)

        with open(self.config_path + "/constantina.ini", "wb") as cfh:
            config.write(cfh)



if __name__ == '__main__':
    config_object = SetupConfig()
    try:
        config_object.site_specifics()		# Define site-specific settings for a Constantina instance
        config_object.data_files()		# Where do files and configs go?
        setup(**config_object.distutils_args)	# Run disttools setup
        config_object.update_configs()		# Update configs once they've been copied
    except distutils.errors.DistutilsPlatformError, ex:
        print
        print str(ex)

        print """
POSSIBLE CAUSE

"distutils" often needs developer support installed to work
correctly, which is usually located in a separate package
called "python%d.%d-dev(el)".

Please contact the system administrator to have it installed.
""" % sys.version_info[:2]
        sys.exit(1)

