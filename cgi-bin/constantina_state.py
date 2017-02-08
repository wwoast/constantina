from math import floor
from random import random, randint, seed, shuffle
from mad import MadFile
from datetime import datetime
import os
import magic
from urllib import unquote_plus
import syslog
import ConfigParser

from constantina_shared import BaseFiles, BaseState
from medusa_cards import MedusaState


class ConstantinaState(BaseState):
    """
    Constantina State Object, an aggregate of the following:
       MedusaState: blog cards. images, quotes, news, songs
       ZooState: forum cards. threads, images, songs
       DraculaState: mail cards. ??

    Aggregate all other states here, and do counting for things like total
    cards, the number of pages, etc. Lots of helper functions for deciding
    things about the Constantina page are tracked here, since these conditions
    depend on properties of the various states
    """
    def __init__(self, in_state=None):
        self.global_config = ConfigParser.SafeConfigParser()
        self.global_config.read('constantina.ini')


        # Based on modes, enable Medusa/other states
        pass


    def _import_theme_state(self):
        """
        In the top-level state object, we track an appearance variable, which 
        corresponds to the exact state variable imported (and exported) for the
        appearance of the entire Constantina site.

        The appearance value lets us look up which theme we display for the user.
        This theme value is a path fragment to a theme's images and stylesheets.
        """
        appearance_state = BaseState._find_state_variable('xa')

        if appearance_state is not None:
            # Read in single char of theme state value
            self.appearance = BaseState._int_translate(appearance_state, 1, 0)

        theme_count = len(global_config.items("themes")) - 1
        self.theme = None
        if self.appearance is None:
            self.theme = global_config.get("themes", "default")
        elif self.appearance >= theme_count:
            self.theme = global_config.get("themes", str(self.appearance % theme_count))
        else:
            self.theme = global_config.get("themes", str(self.appearance))

        # If the configuration supports a random theme, and we didn't have a
        # theme provided in the initial state, let's choose one randomly
        if (appearance_state is None) and (self.theme == "random"):
            seed()   # Enable non-seeded choice
            choice = randint(0, theme_count - 1)
            self.theme = global_config.get("themes", str(choice))
            if self.seed:   # Re-enable seeded nonrandom choice
                seed(self.seed)


    


    def fresh_mode(self):
        """Either an empty state, or just an empty state and a theme is set"""
        # TODO: check other states! Reshuffle logic in ConstantinaState
        if (((self.in_state is None) or (self.configured_states() == ['appearance'])) and
             (self.page == 0) and
             (self.medusa.reshuffle is False)):
            return True
        else:
            return False


    def reshuffle_mode(self):
        """An empty search was given, so reshuffle the page"""
        # TODO: check other states! Reshuffle logic in ConstantinaState
        if ((self.medusa.search is not None) and
            (self.medusa.reshuffle is True) and
            (self.medusa.card_filter is None)):
            return True
        else:
            return False


    def permalink_mode(self):
        """Is one of the permalink modes on?"""
	# TODO: check other states for active permalinks!
        if ((self.medusa.news_permalink is not None) or
            (self.medusa.features_permalink is not None) or
            (self.medusa.topics_permalink is not None)):
            return True
        else:
            return False


    def exclude_cardtype(self, ctype):
        """
        Is a card filter in place, and if so, is the given card type being filtered?
        If this returns true, it means the user either wants cards of this type, or
        that no card filtering is currently in place.
        """
        # TODO: check other state!
        if ((self.medusa.card_filter is not None) and
            (getattr(self, ctype).filtertype is False)):
            return True
        else:
            return False


    def filter_processed_mode(self):
        """
        Is it a search state, and did we already convert #hashtag strings
        into filter queries?
        """
        # TODO: check other state!
        states = self.medusa.configured_states()
        if (('search' in states) or
            ('card_filter' in states)):
            return True
        else:
            return False


    def filter_only_mode(self):
        """All search queries converted into card filters"""
        # TODO: check other state!
        if self.medusa.configured_states() == ['card_filter']:
            return True
        else:
            return False


    def search_only_mode(self):
        """There is a search query, but no terms converted into card filters"""
        # TODO: check other state!
        if self.medusa.configured_states() == ['search']:
            return True
        else:
            return False


    def search_mode(self):
        """Any valid state from a search mode will trigger this mode"""
        # TODO: check other state
        if ((self.medusa.search is not None) or
            (self.medusa.card_filter is not None) or
            (self.medusa.filtered != 0)):
            return True
        else:
            return False


    def out_of_content(self, card_count):
        """
        Count the number of cards that are part of our page counting. If we've
        already displayed this number of cards, we are out of content.
        """
        card_limit = 0
        for ctype in self.config.get("card_properties", "pagecount").replace(" ", "").split(","):
            card_limit = card_limit + getattr(self, ctype).file_count
        # syslog.syslog("card_limit: " + str(card_limit) + "   card_count: " + str(card_count))
        if card_count >= card_limit:
            return True
        else:
            return False
