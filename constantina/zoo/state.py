import syslog
import configparser

from constantina.shared import GlobalConfig, BaseFiles, BaseCardType, BaseState, opendir

syslog.openlog(ident='constantina.zoo.cards')


class ZooState(BaseState):
    """
    Constantina Forum Page State Object.

    ZooState needs the following details from a GlobalState object:
        - Card Filters (which share syntax with #channels)
        - Search terms (which may include forum searches, i.e. @username)
        - in_state (which may leave items unprocessed)
    This works exactly like the MedusaState object, but all state values here
    specifically refer to forum cards and cardtypes.

    When exported, zoo state should concatenate with MedusaState's export_state
    output, so that both blog and forum state is represented.
    """
    def __init__(self, in_state=None):
        BaseState.__init__(self, in_state, 'zoo.ini')
        # Process all state variables listed in zoo.ini
        self.__import_state()

        # Now that we've imported, shuffle any card types we want to shuffle
        for ctype in self.config.get("card_properties", "randomize").replace(" ", "").split(","):
            getattr(self, ctype).shuffle()


    def __import_card_state(self):
        """
        Zoo images, Zoo songs, and Thread card state is tracked here. Seed tracking
        between page loads means we don't need to log which content cards were
        shown on a previous page.

        However, to preserve card spacing rules, we do need to track the distance
        of each card type from the first element of the current page.

        Output is an integer or None.
        """
        # For each content card type, populate the state variables
        # as necessary.
        for state_var in ["z" + s[0] for s in self.config.options('card_counts')]:
            # NOTE: This ctype attribute naming requires each content card type to
            # begin with a unique alphanumeric character.
            ctype = [value for value in self.config.options("card_counts") if value[0] == state_var][0]
            distance = BaseState._find_state_variable(self, state_var)
            getattr(self, ctype).distance = distance


    def __import_permalink_state(self):
        """ :zp, :zt
        Import the specified zoo post thread data. This is used for permalink-style
        single-thread views. This should specify the equivalent of a single
        post or a single thread.
        """
        # TODO: Migrate to shared or BaseSate.
        permalink_states = [sv[0] for sv in self.config.items("special_states")
                            if sv[1].find("permalink") != -1]
        for state in permalink_states:
            value = BaseState._find_state_variable(self, state)
            if value != None:
                attrib = self.config.get("special_states", state)
                setattr(self, attrib, value)
                return   # Only one permalink state per page. First one takes precedence


    def __import_filtered_card_count(self):
        """
        Filtered card count, tracked when we have a query type and a filter count
        and cards on previous pages were omitted from being displayed. Tracking
        this allows you to fix the page count to represent reality better.

        Output must be an integer.
        """
        self.filtered = BaseState._find_state_variable(self, 'zx')
        if ((self.filtered is not None) and
            (self.search is not None) and
            (self.channel_filter is not None) and
            (self.user_filter is not None)):
            self.filtered = BaseState._int_translate(self, self.filtered, 1, 0)
        else:
            self.filtered = 0


    def __import_search_state(self):
        """
        Import the search terms that were used on previous page loads.
        Some of these terms may be prefixed with a #, which makes them either
        channel names, and some may be prefixed with a @, which makes them
        usernames.

        Output is either strings of search/filter terms, or None
        """
        # TODO: tie to a global search that can call the application-specific ones
        self.search = BaseState._find_state_variable(self, 'zs')
        self.channel_filter = BaseState._find_state_variable(self, 'zc')
        self.user_filter = BaseState._find_state_variable(self, 'zu')
        # Channel and topic can overlap. This is ok -- we don't care what was filtered
        # by cardtype for returning forum channel cards.
        # TODO: just look for #channels or @users
        pass


    def __import_state(self):
        """
        Given a state variable string grabbed from the page, fill out the
        Zoo state object with properties relevant to the card list we'll be
        loading. The order that state components are loaded is significant,
        as is the output type of each state import function.
        """
        self.__import_permalink_state()      # Post and thread permalinks
        self.__import_search_state()         # Search strings and processing out filter strings


    def __export_search_state(self, query_terms):
        """Export state related to Zoo searched cards"""
        query_string = None
        if query_terms != '':
            query_string = "zs" + query_terms
        return query_string


    def __export_channel_filter_state(self, channel_terms):
        """Export state related to Zoo #channel-filtered cards"""
        channel_string = None
        if channel_terms != '':
            channel_string = "zc" + channel_terms
        return channel_string

    
    def __export_user_filter_state(self, user_terms):
        """Export state related to Zoo @user-filtered cards"""
        user_string = None
        if user_terms != '':
            user_string = "zu" + user_terms
        return user_string


    def __export_filtered_card_count(self, filtered_count):
        """
        If any cards were excluded by filtering, and a search is in progress,
        track the number of filtered cards in the state.
        """
        filtered_count_string = None
        if self.filter_processed_mode() is True:
            filtered_count_string = "zx" + str(filtered_count)
        return filtered_count_string


    def export_state(self, cards, query_terms, channel_terms, user_terms, filtered_count):
        """
        Once all cards are read, calculate a new state variable to
        embed in the more-contents page link.
        """
        export_parts = [self.__export_card_state(),
                        self.__export_search_state(query_terms),
                        self.__export_channel_filter_state(channel_terms),
                        self.__export_user_filter_state(user_terms),
                        self.__export_filtered_card_count(filtered_count)]

        export_parts = filter(None, export_parts)
        export_string = ':'.join(export_parts)
        return export_string


    def exclude_cardtype(self, application, ctype):
        """
        Is a card filter in place, and if so, is the given card type being filtered?
        If this returns true, it means the user either wants cards of this type, or
        that no card filtering is currently in place.
        """
        # TODO: rewrite for user or channel filtering
        pass
