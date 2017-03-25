from math import floor
from random import random, randint, seed, shuffle
from mad import MadFile
from datetime import datetime
import os
import magic
from urllib import unquote_plus
import syslog
import ConfigParser

from Constantina.zoo.state import ZooState
from Constantina.zoo.cards import ZooCard
from Constantina.shared import BaseFiles, BaseCardType, opendir

syslog.openlog(ident='Constantina.zoo.cards')


class ZooState(BaseState):
    """
    Constantina Forum Page State Object.

    ZooState needs the following details from a MedusaState object:
        - Card Filters (which share syntax with #channels)
        - Search terms (which may include forum searches, i.e. @username)
        - in_state (which may leave items unprocessed)
    This works exactly like the MedusaState object, but all state values here
    specifically refer to forum cards and cardtypes. 

    When exported, zoo state should concatenate with MedusaState's export_state
    output, so that both blog and forum state is represented.
    """
    def __init__(self):
        BaseState.__init__(self, in_state, 'zoo.ini')



    def __import_zoo_search_state(self):
        """
        Import the search terms that were used on previous page loads.
        Some of these terms may be prefixed with a #, which makes them either
        channel names, and some may be prefixed with a @, which makes them
        usernames.

        Output is either strings of search/filter terms, or None
        """
        self.search = self.__find_state_variable('xs')        # Read from in_state!!
        self.card_filter = self.__find_state_variable('xo')   # Read from in_state!!
        # Channel and topic can overlap. This is ok -- we don't care what was filtered
        # by cardtype for returning forum channel cards.

        # TODO: just look for #channels or @users


    def __import_state(self):
        """
        Given a state variable string grabbed from the page, fill out the
        Zoo state object with properties relevant to the card list we'll be
        loading. The order that state components are loaded is significant,
        as is the output type of each state import function.
        """
        # TOWRITE: Zoo specific stuff


    def __export_zoo_search_state(self, query_terms):
        """Export state related to Zoo searched cards"""
        # TODO: channel state import and user state import functions too?
        query_string = None
        if query_terms != '':
            query_string = "xs" + query_terms
        return query_string


    def export_state(self, cards, query_terms, filter_terms, filtered_count):
        """
        Once all cards are read, calculate a new state variable to
        embed in the more-contents page link.
        """
        # TOWRITE: Zoo specific stuff


    def exclude_cardtype(self, application, ctype):
        """
        Is a card filter in place, and if so, is the given card type being filtered?
        If this returns true, it means the user either wants cards of this type, or
        that no card filtering is currently in place.
        """
        ctype = getattr(self, ctype)
        if ctype == None:   # No app or ctype, so no cards of this type
            return False

        if ((getattr(self, "card_filter") is not None) and
            (self.ctype.filtertype is False)):
            return True
        else:
            return False


    # TOWRITE: modes related to forum cards and checks
