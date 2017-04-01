#!/usr/bin/env python
"""
Constantina installer script. The installer script by default will also run
a configuration script intended to set up reasonable defaults for an instance
of Constantina.
"""
import distutils
import distutils.cmd
import distutils.log
from distutils.core import setup
import os
import sys
from socket import gethostname
import subprocess
import setuptools.command.install

# Use same command line parsing for setup.py and configuration after the fact 
from bin.constantina_configure import ConstantinaConfig, read_arguments

Settings = ConstantinaConfig()
Package = None


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
        self.instance = Settings.instance
        self.config = Settings.config
        self.hostname = Settings.hostname
        self.root = Settings.root

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
        self.announce(
            'Running command: %s' % str(command),
            level=distutils.log.INFO)
        subprocess.check_call(command)


class InstallPyCommand(setuptools.command.install.install):
    """Custom installer process for reading values"""

    def pre_configure(self):
        """
        Configure values for installing configuration files and others
        """
        Package['data_files'].append(
            (Settings.config, ['config/constantina.ini',
                               'config/medusa.ini',
                               'config/zoo.ini',
                               'config/shadow.ini']))

    def run(self):
        """
        Grab command-line arguments, run normal install, and then do 
        post-install configuration.
        """
        global Settings 
        Settings = read_arguments()
        self.pre_configure()
        setuptools.command.install.install.run(self)
        self.run_command('config')


if __name__ == '__main__':
    # Install the files, and then run a configure script afterwards
    # if we used the "install" command.
    global Package
    try:
        Package = {
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
            ],
            'data_files': []
        }
        setup(**Package)

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

