from math import floor
from random import random, randint, seed, shuffle
from mad import MadFile
from datetime import datetime
import os
import magic
from urllib import unquote_plus
import syslog
import ConfigParser

from constantina_shared import GlobalConfig, BaseFiles, BaseState
from medusa_cards import MedusaState

syslog.openlog(ident='constantina_state')


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
        BaseState.__init__(self, in_state, None)
        self.config = GlobalConfig

        # Getting defaults from the other states requires us to first import
        # any random seed value. Then, we can finish setting the imported state
        self.__import_random_seed()			
        self.__set_state_defaults()
        self.__import_state()


    def __set_state_defaults(self):
        """
        Set default values for special_state properties and normal content-card
        properties, as well as upper limits on how many cards can exist on a 
        single Constantina page for this type of application. Doing so means we
        must import all of the sub-application states here, rather than in the
        import function like you'd do intuitively :(
        """
        self.max_items = 0   # Aggregate max items per page
        self.filtered = 0    # Aggregate filtered card count

        # For the values in the special_states config, create variables, i.e.
        #   state.appearance, state.page
        for spctype, spcfield in self.config.items("special_states"):
            setattr(self, spcfield, None)       # All state vals are expected to exist

        # Subapplication states are held in this object too
        self.medusa = None
        self.zoo = None
        # self.dracula = None

        # Based on modes, enable Medusa/Zoo/other states
        if self.config.get("authentication", "mode") == "blog": 
            self.medusa = MedusaState(self.in_state)
            self.max_items += self.medusa.max_items
            self.filtered += self.medusa.filtered

        if self.config.get("authentication", "mode") == "zoo":
            self.zoo = ZooState(self.in_state)
            self.max_items += self.zoo.max_items
            self.filtered += self.zoo.filtered

        if self.config.get("authentication", "mode") == "combined":
            self.medusa = MedusaState(self.in_state)
            self.max_items += self.medusa.max_items
            self.filtered += self.medusa.filtered
            self.zoo = ZooState(self.in_state)
            self.max_items += self.zoo.max_items
            self.filtered += self.zoo.filtered


    def get(self, application, value, args=None):
        """
        Allow retrieving a medusa/zoo state value or function, or returning a 
        default None value.
        """
        app_state = getattr(self, application, None)
        if app_state == None:
            return None

        item = getattr(app_state, value)
        if callable(item) and args is not None:
            return item(*args)   # Unroll the array of args
        elif callable(item):
            return item()
        else:
            return item


    def all(self, value, mode="append", args=None):
        """
        For all available applications, get the value or function asked for.
        The mode can be a sum of available values, or logic like 'and' or 'or'
        """
        items = []
        for application in self.config.get("applications", "enabled").replace(" ","").split(","):
            items.append(self.get(application, value, args))
        if mode == "append":
            items = filter(None, items)
            if items == []:
                return None
            return [item for sublist in items for item in sublist]   # Flatten
        elif mode == "sum":
            return sum(items)
        elif mode == "or":
            return any(items)   # Logical OR across the list
        elif mode == "and":
            return all(items)   # Logical AND across the list
        else:
            return None


    def __import_page_count_state(self):
        """
        For all subsequent "infinite-scroll AJAX" content after the initial page
        load, we track the current page number of content.

        Output must be an integer.
        """
        self.page = BaseState._find_state_variable(self, 'xp')

        # If page was read in as a special state variable, use that (for search results)
        if self.page is not None:
            self.page = BaseState._int_translate(self, self.page, 1, 0)
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


    def __import_theme_state(self):
        """
        In the top-level state object, we track an appearance variable, which 
        corresponds to the exact state variable imported (and exported) for the
        appearance of the entire Constantina site.

        The appearance value lets us look up which theme we display for the user.
        This theme value is a path fragment to a theme's images and stylesheets.
        """
        appearance_state = BaseState._find_state_variable(self, 'xa')

        if appearance_state is not None:
            # Read in single char of theme state value
            self.appearance = BaseState._int_translate(self, appearance_state, 1, 0)

        theme_count = len(self.config.items("themes")) - 1
        self.theme = None
        if self.appearance is None:
            self.theme = self.config.get("themes", "default")
        elif self.appearance >= theme_count:
            self.theme = self.config.get("themes", str(self.appearance % theme_count))
        else:
            self.theme = self.config.get("themes", str(self.appearance))

        # If the configuration supports a random theme, and we didn't have a
        # theme provided in the initial state, let's choose one randomly
        if (appearance_state is None) and (self.theme == "random"):
            seed()   # Enable non-seeded choice
            choice = randint(0, theme_count - 1)
            self.theme = self.config.get("themes", str(choice))
            if self.seed:   # Re-enable seeded nonrandom choice
                seed(self.seed)


    def __import_state(self):
        """
        When setting defaults, we imported the sub application states. But now
        we need to import the relevant states for the entire application, like
        the page state and the chosen theme.
        """
        self.__import_page_count_state()
        self.__import_theme_state()


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


    def export_theme_state(self):
        """If tracking an appearance or theme, include it in state links"""
        appearance_string = None
        if self.appearance is not None:
            appearance_string = "xa" + str(self.appearance)
        return appearance_string
 

    def export_state(self, cards, query_terms, filter_terms, filtered_count):
        """Export all medusa/other states, as well as appearance/page here"""
        args = [cards, query_terms, filter_terms, filtered_count]
        export_parts = [ self.__export_random_seed(),
                         self.__export_page_count_state(),
                         self.export_theme_state(),
                         self.get("medusa", "export_state", args),
                         self.get("zoo", "export_state", args) ]

        export_parts = filter(None, export_parts)
        export_string = ':'.join(export_parts)
        return export_string


    def fresh_mode(self):
        """Either an empty state, or just an empty state and a theme is set"""
        if (((self.in_state is None) or (self.all("configured_states") == ['appearance'])) and
             (self.page == 0) and
             (self.all("reshuffle", "or") is False)):
            return True
        else:
            return False


    def reshuffle_mode(self):
        """An empty search was given, so reshuffle the page"""
        if ((self.all("search") is not None) and
            (self.all("reshuffle", "or") is True) and
            (self.all("card_filter") is None)):
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


    def filter_processed_mode(self):
        """
        Is it a search state, and did we already convert #hashtag strings
        into filter queries?
        """
        states = self.all("configured_states")
        if (('search' in states) or
            ('card_filter' in states)):
            return True
        else:
            return False


    def filter_only_mode(self):
        """All search queries converted into card filters"""
        if self.all("configured_states") == ['card_filter']:
            return True
        else:
            return False


    def search_only_mode(self):
        """There is a search query, but no terms converted into card filters"""
        if self.all("configured_states") == ['search']:
            return True
        else:
            return False


    def search_mode(self):
        """Any valid state from a search mode will trigger this mode"""
        if ((self.all("search") is not None) or
            (self.all("card_filter") is not None) or
            (self.filtered != 0)):
            return True
        else:
            return False


    def out_of_content(self, card_count):
        """
        Count the number of cards that are part of our page counting. If we've
        already displayed this number of cards, we are out of content.
        """
        card_limit = 0
        for application in self.config.get("applications", "enabled").replace(" ", "").split(","):
            app_state = getattr(self, application)
            for ctype in app_state.config.get("card_properties", "pagecount").replace(" ", "").split(","):
                card_limit = card_limit + getattr(app_state, ctype).file_count
        # syslog.syslog("card_limit: " + str(card_limit) + "   card_count: " + str(card_count))
        if card_count >= card_limit:
            return True
        else:
            return False
