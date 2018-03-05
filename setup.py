#!/usr/bin/env python3
"""
Constantina installer script. The installer script by default will also run
a configuration script intended to set up reasonable defaults for an instance
of Constantina.
"""
import os
import distutils
import distutils.log
import sys
from pwd import getpwnam
from grp import getgrnam
import subprocess
from setuptools import setup, Command
from setuptools.command.install import install

# Use same command line parsing for setup.py and configuration after the fact
from constantina.util.constantina_configure import ConstantinaConfig, HelpStrings, install_arguments

# Globals, so all the Configure objects get configured from a consistent
# place prior to distutils running the setup commands
Settings = ConstantinaConfig()
Package = None


class ConfigurePyCommand(Command):
    """Custom command for doing configuration steps"""
    description = 'configure Constantina defaults for a site'
    user_options = [
        ('instance=', 'i', HelpStrings['instance']),
        ('config-root=', 'c', HelpStrings['config_root']),
        ('cgi-bin=', 'b', HelpStrings['cgi_bin']),
        ('hostname=', 'n', HelpStrings['hostname']),
        ('port=', 'P', HelpStrings['port']),
        ('data-root=', 'r', HelpStrings['data_root']),
        ('username=', 'u', HelpStrings['username']),
        ('groupname=', 'g', HelpStrings['groupname']),
    ]

    def initialize_options(self):
        """Where default settings for each user_options value is set"""
        self.instance = Settings.instance
        self.config_root = Settings.config_root
        self.cgi_bin = Settings.cgi_bin
        self.hostname = Settings.hostname
        self.port = Settings.port
        self.data_root = Settings.data_root
        self.username = Settings.username
        self.groupname = Settings.groupname

    def finalize_options(self):
        """Look for unacceptable inputs"""
        assert (isinstance(self.instance, str) and
                len(self.instance) > 0 and
                len(self.instance) < 32), 'Invalid instance name'
        assert getpwnam(self.username), 'User name not found'
        assert getgrnam(self.groupname), 'Group name not found'
        assert isinstance(self.hostname, str), 'Invalid hostname'
        assert (int(self.port) < 65536) and (int(self.port) > 1024), 'Invalid or privileged port given'
        assert isinstance(self.data_root, str), 'Invalid data_root directory'
        assert isinstance(self.config_root, str), 'Invalid config directory'
        assert isinstance(self.cgi_bin, str), 'Invalid cgi-bin directory'

    def run(self):
        """Run a configuration script post-install"""
        command = ['./constantina/util/constantina_configure.py']
        if self.instance:
            command.append('--instance')
            command.append(self.instance)
        if self.hostname:
            command.append('--hostname')
            command.append(self.hostname)
        if self.port:
            command.append('--port')
            command.append(self.port)
        if self.data_root:
            command.append('--data-root')
            command.append(self.data_root)
        if self.username:
            command.append('--username')
            command.append(self.username)
        if self.groupname:
            command.append('--groupname')
            command.append(self.groupname)
        if self.cgi_bin:
            command.append('--cgi-bin')
            command.append(self.cgi_bin)
        if self.config_root:
            command.append('--config-root')
            command.append(self.config_root)
        self.announce(
            'Running command: %s' % str(command),
            level=distutils.log.INFO)
        subprocess.check_call(command)


class InstallPyCommand(install):
    """Custom installer process for reading values"""
    description = 'install and configure Constantina at a site'
    install.user_options += [
        ('instance=', 'i', HelpStrings['instance']),
        ('config-root=', None, HelpStrings['config_root']),
        ('cgi-bin=', 'b', HelpStrings['cgi_bin']),
        ('hostname=', None, HelpStrings['hostname']),
        ('port=', 'P', HelpStrings['port']),
        ('data-root=', 'r', HelpStrings['data_root']),
        ('username=', 'u', HelpStrings['username']),
        ('groupname=', 'g', HelpStrings['groupname']),
        ('upgrade', None, HelpStrings['upgrade']),
        ('scriptonly', None, HelpStrings['scriptonly']),
    ]

    def initialize_options(self):
        """Where default settings for each user_options value is set"""
        self.instance = Settings.default.instance
        self.config_root = Settings.default.config_root
        self.cgi_bin = Settings.cgi_bin
        self.hostname = Settings.default.hostname
        self.port = Settings.default.port
        self.data_root = Settings.default.data_root
        self.username = Settings.default.username
        self.groupname = Settings.default.groupname
        self.upgrade = False
        self.scriptonly = False
        install.initialize_options(self)

    def finalize_options(self):
        """
        Look for unacceptable inputs, and where they exist, default
        to reasonable standard values. Assume that no configuration
        exists prior to your running this command.
        """
        assert (isinstance(self.instance, str) and
                len(self.instance) > 0 and
                len(self.instance) < 32), 'Invalid instance name'
        assert getpwnam(self.username), 'User name not found'
        assert getgrnam(self.groupname), 'Group name not found'
        assert isinstance(self.hostname, str), 'Invalid hostname'
        assert (int(self.port) < 65536) and (int(self.port) > 1024), 'Invalid or privileged port given'
        assert isinstance(self.data_root, str), 'Invalid data_root directory'
        assert isinstance(self.config_root, str), 'Invalid config directory'
        assert isinstance(self.cgi_bin, str), 'Invalid cgi-bin directory'
        install.finalize_options(self)

    def data_files(self):
        """
        Not in the Python package, but get installed at specific locations
        on your disk: config files, cgi-script, etc.
        """
        # Template files for constantina_configure to work from later
        Package['data_files'].append(
            (Settings.templates,
             ['config/constantina.ini',
              'config/keys.ini',
              'config/medusa.ini',
              'config/preferences.ini',
              'config/sensitive.ini',
              'config/shadow.ini',
              'config/uwsgi.ini',
              'config/zoo.ini']))
        # Initial config files for your chosen instance
        if self.upgrade is False and self.scriptonly is False:
            Package['data_files'].append(
                (Settings.config_root,
                 ['config/constantina.ini',
                  'config/keys.ini',
                  'config/medusa.ini',
                  'config/preferences.ini',
                  'config/sensitive.ini',
                  'config/shadow.ini',
                  'config/uwsgi.ini',
                  'config/zoo.ini']))
        # The CGI script
        Package['data_files'].append(
            (Settings.cgi_bin,
             ['cgi-bin/constantina.cgi']))
        # The HTML data_root folder. Add these recursively to data_files
        # so they can be both part of the install and the sdist.
        if self.scriptonly is False:
            for (path, directories, files) in os.walk("html"):
                subdir = '/'.join(path.split("/")[1:])
                if self.upgrade is not False:   # 1 if true
                    if path.find("private") != -1:
                        continue   # If upgrading, don't install cards
                Package['data_files'].append(
                    (Settings.data_root + '/' + subdir,
                     [os.path.join(path, filename) for filename in files]))

    def run(self):
        """
        Grab command-line arguments, run normal install, and then do
        post-install configuration.
        """
        global Settings
        Settings = install_arguments()
        self.data_files()
        install.run(self)
        if self.scriptonly is False and self.upgrade is False:
            self.run_command('configure')


if __name__ == '__main__':
    # Install the files, and then run a configure script afterwards
    # if we used the "install" command.
    global Package
    try:
        Package = {
            'name': "constantina",
            'version': "0.6.0",
            'description': "a dynamic-content blog platform for \"grazing\"",
            'author': "Justin Cassidy",
            'author_email': 'boil.afraid@gmail.com',
            'url': 'https://github.com/wwoast/constantina',
            'classifiers':"""Programming Language :: Python
Programming Language :: Python :: 3 :: Only""".splitlines(),
            'packages': [
                'constantina',
                'constantina.medusa',
                'constantina.zoo',
                'constantina.util'
            ],
            'cmdclass': {
                'configure': ConfigurePyCommand,
                'install': InstallPyCommand
            },
            'scripts': [
                'constantina/util/constantina_configure.py',
                'constantina/util/constantina_index.py',
            ],
            'setup_requires': [
                'passlib'
            ],
            'install_requires': [
                'argon2',
                'argon2pure',
                'jwcrypto',
                'lxml',
                'mutagen',
                'python-magic',
                'Pillow',
                'whoosh'
            ],
            'data_files': []
        }
        setup(**Package)

    except distutils.errors.DistutilsPlatformError as ex:
        print()
        print(str(ex))

        print("""
POSSIBLE CAUSE

"distutils" often needs developer support installed to work
correctly, which is usually located in a separate package
called "python%d.%d-dev(el)".

Please contact the system administrator to have it installed.
""" % sys.version_info[:2])
        sys.exit(1)

