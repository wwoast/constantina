from math import floor
from random import random, randint, seed, shuffle
from mad import MadFile
from datetime import datetime
import os
import magic
from urllib import unquote_plus
import syslog
import ConfigParser

from constantina.zoo.cards import ZooCard
from constantina.zoo.state import ZooState
from constantina.shared import BaseFiles, BaseCardType, opendir

syslog.openlog(ident='constantina.zoo.cards')


class ZooCard:
    """
    Since forum cards must track updatable state in each item, we don't load
    these as HTML fragments anymore, but as raw JSON documents.
    """
    def __interpretfile(self, thisfile):
        """Make this support JSON as an additional type?"""
        # TOWRITE
