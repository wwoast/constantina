#!/usr/bin/env python

import distutils
from distutils.core import setup
import sys

"""
constantina installer script. Based on the configuration settings in
constantina.ini, generate initial jws/jwk values, an initial admin
password, and move all relevant files into their final directories.
"""


setup_args = {
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


def interactive_setup():
    """
    Read in values for setting up Constantina, including:
    - Name of the domain we're using 
    - ...
    """ 
    pass


def setup_paths():
    """
    Install the html data in the directory of your choosing, by default
    /var/www/<hostname>/constantina. TOWRITE

    Install config files for Constantina in /etc/constantina unless we're 
    using a special config prefix like /usr/local, in which case we put
    configs in /usr/local/etc/constantina.
    """
    config_path = sys.prefix + "/etc/constantina"
    if sys.prefix == "/usr":
        config_path = "/etc/constantina"

    setup_args['data_files'] = [
        (config_path, ["config/constantina.ini", 
                       "config/medusa.ini", 
                       "config/zoo.ini"])
    ]    


if __name__ == '__main__':
    try:
        setup_paths()
        setup(**setup_args)
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


