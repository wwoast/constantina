#!/usr/bin/env python
"""
Constantina installer script. The installer script by default will also run
a configuration script intended to set up reasonable defaults for an instance
of Constantina.
"""
import distutils
import distutils.cmd
import distutils.log
import distutils.dir_util
from distutils.core import setup
import os
import sys
from socket import gethostname
import subprocess
from setuptools.command.install import install

# Use same command line parsing for setup.py and configuration after the fact 
from bin.constantina_configure import ConstantinaConfig, HelpStrings, read_arguments

# Globals, so all the Configure objects get configured from a consistent
# place prior to distutils running the setup commands
Settings = ConstantinaConfig()
Package = None


class ConfigurePyCommand(distutils.cmd.Command):
    """Custom command for doing configuration steps"""
    description = 'configure Constantina defaults for a site'
    user_options = [
        ('instance=', 'i', HelpStrings['instance']),
        ('config=', 'c', HelpStrings['config']),
        ('hostname=', 'h', HelpStrings['hostname']),
        ('webroot=', 'r', HelpStrings['webroot']),
        ('user=', 'u', HelpStrings['user']),
    ]

    def initialize_options(self):
        """Where default settings for each user_options value is set"""
        self.instance = Settings.default.instance
        self.config = Settings.default.config
        self.hostname = Settings.default.hostname
        self.webroot = Settings.default.webroot
        self.user = Settings.default.user

    def finalize_options(self):
        """Look for unacceptable inputs"""
        assert (isinstance(self.instance, str) and
                len(self.instance) > 0 and
                len(self.instance) < 32), 'Invalid instance name'
        assert isinstance(self.hostname, str), 'Invalid host name'
        assert isinstance(self.webroot, str)
        assert isinstance(self.user, str), 'Invalid user name'
        assert isinstance(self.config, str)  # Check if directory exists

    def run(self):
        """Run a configuration script post-install"""
        command = ['./bin/constantina_configure.py']
        if self.instance:
            command.append('--instance')
            command.append(self.instance)
        if self.hostname:
            command.append('--hostname')
            command.append(self.hostname)
        if self.webroot:
            command.append('--webroot')
            command.append(self.webroot)
        if self.user:
            command.append('--user')
            command.append(self.user)
        if self.config:
            command.append('--config')
            command.append(self.config)
        self.announce(
            'Running command: %s' % str(command),
            level=distutils.log.INFO)
        subprocess.check_call(command)


class InstallPyCommand(install):
    """Custom installer process for reading values"""
    description = 'install and configure Constantina at a site'
    install.user_options += [
        ('instance=', 'i', HelpStrings['instance']),
        ('config=', 'c', HelpStrings['config']),
        ('hostname=', 'h', HelpStrings['hostname']),
        ('webroot=', 'r', HelpStrings['webroot']),
        ('user=', 'u', HelpStrings['user']),
    ]

    def initialize_options(self):
        """Where default settings for each user_options value is set"""
        self.instance = Settings.default.instance
        self.config = Settings.default.config
        self.hostname = Settings.default.hostname
        self.webroot = Settings.default.webroot
        self.user = Settings.default.user
        install.initialize_options(self)

    def finalize_options(self):
        """Look for unacceptable inputs"""
        assert (isinstance(self.instance, str) and
                len(self.instance) > 0 and
                len(self.instance) < 32), 'Invalid instance name'
        assert isinstance(self.hostname, str), 'Invalid host name'
        assert isinstance(self.webroot, str), 'Invalid webroot path'
        assert isinstance(self.user, str), 'Invalid user name'
        assert isinstance(self.config, str)  # Check if directory exists
        install.finalize_options(self)

    def data_files(self):
        """
        Not in the Python package, but get installed at specific locations
        on your disk: config files.
        """
        # Template files for constantina_configure to work from later
        Package['data_files'].append(
            (Settings.templates,
                ['config/constantina.ini',
                 'config/medusa.ini',
                 'config/zoo.ini',
                 'config/shadow.ini']))
        # Initial config files for your chosen instance
        Package['data_files'].append(
            (Settings.config,
                ['config/constantina.ini',
                 'config/medusa.ini',
                 'config/zoo.ini',
                 'config/shadow.ini']))

    def create_webroot(self):
        """Copy the included html file into the target location"""
        distutils.dir_util.copy_tree('html', Settings.webroot, update=1)

    def run(self):
        """
        Grab command-line arguments, run normal install, and then do
        post-install configuration.
        """
        global Settings
        Settings = read_arguments()
        print Settings.config
        self.data_files()
        install.run(self)
        self.create_webroot()
        self.run_command('configure')


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
                'configure': ConfigurePyCommand,
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

