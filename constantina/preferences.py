import os
import ConfigParser
import json
import syslog
from jwcrypto import jwk, jwt

from shared import GlobalConfig


syslog.openlog(ident='constantina.preferences')


class ConstantinaPreferences:
    """
    Set preferences for an individual user.

    Constantina's strategy for this is to leave all settings off of the server,
    as well as avoiding any settings that could be used for tracking users
    by their real-world details. So none of these settings have any concept of
    a "user profile".

    Indeed, the settings are all stored in a user cookie, which is then signed
    and encrypted using per-account keys stored on the server. This way, the
    cookie's purpose may remain opaque on the client, and the settings cannot be
    changed or sniffed on the server without an active session from the user
    actively occuring.

    # [settings]
    # theme =
    # default_topic =
    # Expand threads, or do the last 10 posts (expand|last-N)
    # thread_expansion = 
    # revise_post_expiration =
    # cookie name: __Secure_hostname-cookieid

    theme/topic/grow-mode(0=all,n>0=last 10*n posts)
    thm:
    top:
    gro:int(0==all)
    rev:
    """
    def __init__(self):
        self.default_preferences()
        pass

    def default_preferences(self):
        """Set all the default preferences a user gets"""
        # self.thm = from GlobalConfig
        # self.top = general
        # self.gro = 0
        # self.rev = from MedusaConfig
        pass

    def read_preferences(self):
        """Given a cookie, read the preferences so the settings screen can be populated."""
        pass

    def write_preferences(self, cookie):
        """Set new preferences, and then write a new cookie."""
        pass