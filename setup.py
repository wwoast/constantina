#!/usr/bin/env python

import distutils
import distutils.cmd
import distutils.log
from distutils.core import setup
import os
import sys
from socket import gethostname
import subprocess
import setuptools.command.install


"""
Constantina installer script. The installer script by default will also run
a configuration script intended to set up reasonable defaults for an instance
of Constantina.
"""
ConfigureCommand = None

class ConfigurePyCommand(distutils.cmd.Command):
    """Custom command for doing configuration steps"""
    description = 'configure Constantina defaults for a site'
    user_options = [
        ('instance=', 'i', 'config directory isolation: /etc/constantina/<instance>'),
        ('config=', 'c', 'path to the configuration directory'),
        ('hostname=', 'h', 'hostname that Constantina will run on'),
        ('root=', 'r', 'where Constantina publichtml resources are served from'),
    ]

    def initialize_options(self):
        """Where default settings for each user_options value is set"""
        self.instance = "default"
        self.config = sys.prefix + "/etc/constantina/" + self.instance
        if sys.prefix == "/usr":
            self.config = "/etc/constantina/" + self.instance
        self.hostname = gethostname()
        self.root = "/var/www/constantina"

    def finalize_options(self):
        """Look for unacceptable inputs"""
        assert (isinstance(self.instance, str) and
                len(self.instance) > 0 and
                len(self.instance) < 32), 'Invalid instance name'
        assert isinstance(self.hostname, str), 'Invalid host name'
        assert isinstance(self.root, str)
        assert isinstance(self.config, str)

    def run(self):
        """Run a configuration script post-install"""
        command = ['./bin/constantina_configure.py']
        if self.instance:
            command.append('--instance')
            command.append(self.instance)
        if self.hostname:
            command.append('--hostname')
            command.append(self.hostname)
        if self.root:
            command.append('--root')
            command.append(self.root)
        if self.config:
            command.append('--config')
            command.append(self.config)
        ConfigureCommand = command


class InstallPyCommand(setuptools.command.install.install):
    """Custom installer process for reading values"""

    def run(self):
        """Run normal install, and then do post-install configuration"""
        self.run_command('config')
        setuptools.command.install.install.run(self)
        self.announce(
            'Running command: %s' % str(ConfigureCommand),
            level=distutils.log.INFO)
        subprocess.check_call(ConfigureCommand)


if __name__ == '__main__':
    # Install the files, and then run a configure script afterwards
    # if we used the "install" command.
    try:
        constantina = {
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
            },
            'scripts': [
                'bin/constantina_configure.py'
            ]
        }
        setup(**constantina)

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

