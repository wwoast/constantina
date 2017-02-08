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


    # TODO: figure out filtered counts or search behavior based on all cards'
    # response to the searches submitted into the text box


    def __import_page_count_state(self):
        """
        For all subsequent "infinite-scroll AJAX" content after the initial page
        load, we track the current page number of content.

        Output must be an integer.
        """
        self.page = BaseState._find_state_variable(self, 'xp')

        # If page was read in as a special state variable, use that (for search results)
        if (self.page is not None) and (self.search_mode() is True):
            self.page = BaseState._int_translate(self, self.page, 1, 0)
        # Otherwise, determine our page number from the news article index reported
        # TODO: Page count not just a function of MedusaState, so consider moving this
        #   into the Constantina state. Also, the news heuristic won't work anymore
        elif self.news.distance is not None:
            self.page = (int(self.news.distance) + 1) / self.config.getint('card_counts', 'news')
        else:
            self.page = 0


    def __import_random_seed(self):
        """
        Set the return seed based on a 14-digit string from the state variable.
        As an input to seed(), this has to be a float between zero and one.

        This seed is used to consistently seed the shuffle function, so that
        between page loads, we know the shuffled card functions give the same
        shuffle ordering.
        """
        self.seed = BaseState._find_state_variable(self, "seed")
        if self.seed is None:
            self.seed = round(random(), 14)
        else:
            self.seed = float(str("0." + self.seed))
        seed(self.seed)   # Now the RNG is seeded with our consistent value


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


    def __import_state(self):
        """TOWRITE: import states from all active sub-applications (medusa, zoo)"""
        pass


    def __export_page_count_state(self):
        """
        If we had search results and used a page number, write an incremented page
        number into the next search state for loading
        """
        page_string = None
        if self.search_mode() is True:
            export_page = int(self.page) + 1
            page_string = "xp" + str(export_page)
        return page_string


    def __export_random_seed(self):
        """Export the random seed for adding to the state variable"""
        return str(self.seed).replace("0.", "")


    def _export_theme_state(self):
        """If tracking an appearance or theme, include it in state links"""
        appearance_string = None
        if self.appearance is not None:
            appearance_string = "xa" + str(self.appearance)
        return appearance_string
 

    def export_state(self):
        """Export all medusa/other states, as well as appearance/page here"""
        pass


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
