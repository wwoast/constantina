#!/usr/bin/env python

from distutils.core import setup
import sys

"""
Constantina installer script. Based on the configuration settings in
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
        'Constantina',
        'Constantina.auth',
        'Constantina.shared',
        'Constantina.state',
        'Constantina.medusa.cards',
        'Constantina.medusa.search',
        'Constantina.medusa.state',
        'Constantina.zoo.cards',
        'Constantina.zoo.search',
        'Constantina.zoo.state',
    ],
}


if __name__ == '__main__':
    try:
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


