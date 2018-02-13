import syslog
import configparser

from constantina.shared import GlobalConfig, BaseFiles, BaseCardType, BaseState, opendir

syslog.openlog(ident='constantina.medusa.state')


class MedusaState(BaseState):
    """
    Constantina Page State Object.

    This is serialized and deserialized from a string embedded
    on the page itself that describes the following details:
        - The distance from the last-displayed item of this type to the end
          of the displayed page
        - The seed number that defines the displayed random order
        - Any search strings that might have been provided in previous views
        - Whether a permalink is being viewed (feature, news, or topic page)
    It also provides a clean interface to global modes and settings that
    influence what content and appearances a Constantina page can take.
    """
    def __init__(self, in_state=None):
        # Open the config file, and set card type defaults per state variable
        BaseState.__init__(self, in_state, 'medusa.ini')
        # Process all state variables listed in medusa.ini
        self.__import_state()

        # Now that we've imported, shuffle any card types we want to shuffle
        for ctype in self.config.get("card_properties", "randomize").replace(" ", "").split(","):
            getattr(self, ctype).shuffle()


    def __import_card_state(self):
        """
        News cards and other content cards' state is tracked here. Seed tracking
        between page loads means we don't need to log which content cards were
        shown on a previous page.

        However, to preserve card spacing rules, we do need to track the distance
        of each card type from the first element of the current page.

        Output is an integer or None.
        """
        # For each content card type, populate the state variables
        # as necessary.
        for state_var in [s[0] for s in self.config.options('card_counts')]:
            # NOTE: This ctype attribute naming requires each content card type to
            # begin with a unique alphanumeric character.
            ctype = [value for value in self.config.options("card_counts") if value[0] == state_var][0]
            distance = BaseState._find_state_variable(self, state_var)
            getattr(self, ctype).distance = distance


    def __import_permalink_state(self):
        """
        Any card type that can be displayed on its own is a permalink-type
        card, and will have state that describes which permalink page should
        be loaded.

        Output is either string (filename, as utime), or None.
        """
        permalink_states = [sv[0] for sv in self.config.items("special_states")
                            if sv[1].find("permalink") != -1]
        for state in permalink_states:
            value = BaseState._find_state_variable(self, state)
            if value != None:
                attrib = self.config.get("special_states", state)
                setattr(self, attrib, value)
                return   # Only one permalink state per page. First one takes precedence


    def __import_search_state(self):
        """
        Import the search terms that were used on previous page loads.
        Some of these terms may be prefixed with a #, which makes them either
        cardtypes or channel names.

        Output is either strings of search/filter terms, or None
        """
        self.search = BaseState._find_state_variable(self, 'xs')
        # TODO: Must check each application's search state before turning on shuffle mode.
        if self.search == '':
            self.reshuffle = True
        else:
            self.reshuffle = False

        # First, check if any of the search terms should be processed as a
        # cardtype and be added to the filter state instead.
        if self.search is not None:
            searchterms = self.search.split(' ')
            searchterms = filter(None, searchterms)   # remove nulls
            [ newfilters, removeterms ] = BaseState._process_search_strings(self, '#', searchterms)
            # Remove filter strings from the search state list if they exist
            [searchterms.remove(term) for term in removeterms]
            self.search = searchterms
            # Take off leading #-sigil for card type searches
            self.card_filter = map(lambda x: x[1:], newfilters)
            for ctype in self.card_filter:
                getattr(self, ctype).filtertype = True
            if self.card_filter == []:
                self.card_filter = None


    def __import_filter_state(self):
        """
        This must run after the import_search_state!

        If no filter strings were found during search, we may need to process a set
        of filter strings that were excised out on a previous page load.
        """
        if self.card_filter is None:
            self.card_filter = BaseState._find_state_variable(self, 'xo')

            if self.card_filter is not None:
                filterterms = self.card_filter.split(' ')
                # Add-filter-cardtypes expects strings that start with #
                hashtag_process = map(lambda x: "#" + x, filterterms)
                [ newfilters, removeterms ] = BaseState._process_search_strings(self, '#', hashtag_process)
                # Take off leading #-sigil for card type searches
                self.card_filter = map(lambda x: x[1:], newfilters)
                # Record filters being set
                for ctype in self.card_filter:
                    getattr(self, ctype).filtertype = True
                if self.card_filter == []:
                    self.card_filter = None


    def __import_filtered_card_count(self):
        """
        Filtered card count, tracked when we have a query type and a filter count
        and cards on previous pages were omitted from being displayed. Tracking
        this allows you to fix the page count to represent reality better.

        Output must be an integer.
        """
        self.filtered = BaseState._find_state_variable(self, 'xx')
        if ((self.filtered is not None) and
            (self.search is not None) and
            (self.card_filter is not None)):
            self.filtered = BaseState._int_translate(self, self.filtered, 1, 0)
        else:
            self.filtered = 0


    def __import_state(self):
        """
        Given a state variable string grabbed from the page, fill out the
        state object with properties relevant to the card list we'll be
        loading. The order that state components are loaded is significant,
        as is the output type of each state import function.
        """
        self.__import_card_state()           # Import the normal content cards
        self.__import_search_state()         # Search strings and processing out filter strings
        self.__import_filter_state()         # Any filter strings loaded from prior pages
        self.__import_filtered_card_count()  # Number of cards filtered out of prior pages
        self.__import_permalink_state()      # Permalink settings


    def __export_card_state(self):
        """
        Construct a string representing the cards that were loaded on this
        page, for the sake of informing the next page load.
        """
        state_tokens = []
        content_string = None

        for ctype in self.config.options("card_counts"):
            # If no cards for this state, do not track
            if ((getattr(self, ctype).clist == []) or
                (getattr(self, ctype).distance is None)):
                continue

            # Track the distance to the last-printed card in each state variable
            stype = ctype[0]
            cdist = getattr(self, ctype).distance
            state_tokens.append(stype + str(cdist))

        # Track page number for the next state variable by adding one to the current
        news_last = getattr(self, 'news').distance
        if news_last is None:
            news_last = 0

        if state_tokens != []:
            content_string = ":".join(state_tokens) + ":" + "n" + str(news_last)
        else:
            content_string = "n" + str(news_last)
        return content_string


    def __export_search_state(self, query_terms):
        """Export state related to searched cards"""
        query_string = None
        if query_terms != '':
            query_string = "xs" + query_terms
        return query_string


    def __export_filter_state(self, filter_terms):
        """Export state related to #ctype filtered cards"""
        filter_string = None
        if filter_terms != '':
            filter_string = "xo" + filter_terms
        return filter_string


    def __export_filtered_card_count(self, filtered_count):
        """
        If any cards were excluded by filtering, and a search is in progress,
        track the number of filtered cards in the state.
        """
        filtered_count_string = None
        if self.filter_processed_mode() is True:
            filtered_count_string = "xx" + str(filtered_count)
        return filtered_count_string


    def export_state(self, cards, query_terms, filter_terms, filtered_count):
        """
        Once all cards are read, calculate a new state variable to
        embed in the more-contents page link.
        """
        # Start by calculating the distance from the next page for each
        # card type. This updates the state.ctype.distance values
        BaseState._calculate_last_distance(self, cards, common="news")

        # Finally, construct the state string for the next page
        export_parts = [self.__export_card_state(),
                        self.__export_search_state(query_terms),
                        self.__export_filter_state(filter_terms),
                        self.__export_filtered_card_count(filtered_count)]

        export_parts = filter(None, export_parts)
        export_string = ':'.join(export_parts)
        return export_string


    def exclude_cardtype(self, ctype):
        """
        Is a card filter in place, and if so, is the given card type being filtered?
        If this returns true, it means the user either wants cards of this type, or
        that no card filtering is currently in place.
        """
        cstate = getattr(self, ctype)
        if cstate == None:   # No app or ctype, so no cards of this type
            return False

        if ((getattr(self, "card_filter") is not None) and
            (cstate.filtertype is False)):
            return True
        else:
            return False


    def filter_processed_mode(self):
        """
        Is it a search state, and did we already convert #hashtag strings
        into filter queries? In Medusa, #hashtags are always card type filters.
        """
        states = self.configured_states()
        if (('search' in states) or
            ('card_filter' in states)):
            return True
        else:
            return False


    def configured_states(self):
        """
        Check to see which special states are enabled. Return an array of
        either card types or special state types that are not set to None.
        """
        state_names = [val[1] for val in self.config.items('special_states')]
        state_names.remove('filtered')   # Filtered is set no matter what
        return [state for state in state_names
                      if ((getattr(self, state) != None) and
                          (getattr(self, state) != []))]
