#!/usr/bin/env python

import distutils
import distutils.cmd
import distutils.log
from distutils.core import setup
import os
import sys
import ConfigParser
import setuptools.command.install
from random import choice, randint
from socket import gethostname
import subprocess

"""
constantina installer script. Based on the configuration settings in
constantina.ini, generate initial jws/jwk values, an initial admin
password, and move all relevant files into their final directories.
"""

class ConfigurePyCommand(distutils.cmd.Command):
    """Custom command for doing configuration steps"""
    description = 'configure Constantina defaults for a site'
    user_options = [
        ('instance', 'i', 'config directory isolation: /etc/constantina/<instance>'),
        ('hostname', 'h', 'hostname that Constantina will run on'),
        ('config', 'c', 'path to the configuration directory')
    ]

    def initialize_options(self):
        """Where default settings for each user_options value is set"""
        self.instance = "default"
        self.hostname = gethostname()
        self.root = "/var/www/constantina"
        self.config = sys.prefix + "/etc/constantina/" + self.instance
        if sys.prefix == "/usr":
            # Default prefix? Just put config in /etc
            self.config_path = "/etc/constantina/" + self.instance

    def finalize_options(self):
        """Look for unacceptable inputs"""
        if len(self.instance) == 0:
            self.instance = "default"
        if len(self.hostname) == 0:
            self.hostname = gethostname()

    def run(self):
        """Run a configuration script post-install"""
        command = [sys.prefix + '/constantina_configure.py']
        if self.instance:
            command.append('--instance=%s' % self.instance)
        if self.hostname:
            command.append('--hostname=%s' % self.hostname)
        if self.root:
            command.append('--root=%s' % self.root)
        if self.config:
            command.append('--config=%s' % self.config)
        command.append(os.getcwd())
        self.announce(
            'Running command: %s' % str(command),
            level=distutils.log.INFO)
        subprocess.check_call(command)


class InstallPyCommand(setuptools.command.install.install):
    """Custom installer process for reading values"""

    def run(self):
        """Run normal install, and then do post-install configuration"""
        setuptools.command.install.install.run(self)
        self.run_command('config')


if __name__ == '__main__':
    # Install the files, and then run a configure script afterwards
    # if we used the "install" command.
    try:
        distutils_config = {
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
            ],
            'cmdclass': {
                'config': ConfigurePyCommand,
                'install': InstallPyCommand
            }
        }
        setup(**distutils_config)

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

