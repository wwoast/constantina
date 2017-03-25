from jwcrypto import jws, jwk
from jwcrypto.common import json_encode

"""
Constantina installer script. Based on the configuration settings in
constantina.ini, generate initial jws/jwk values, an initial admin
password, and move all relevant files into their final directories.
"""

