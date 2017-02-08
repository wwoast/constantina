from math import floor
from random import random, randint, seed, shuffle
from mad import MadFile
from datetime import datetime
import os
import magic
from urllib import unquote_plus
import syslog
import ConfigParser

from constantina_shared import BaseFiles, BaseCardType, BaseState, opendir

syslog.openlog(ident='medusa_cards')


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
        BaseState.__init__(self, 'medusa.ini', in_state)
        # Process all state variables listed in medusa.ini
        self.__import_state()

        # Now that we've imported, shuffle any card types we want to shuffle
        for ctype in self.config.get("card_properties", "randomize").replace(" ", "").split(","):
            getattr(self, ctype).shuffle()

        # syslog.syslog("Random seed: " + str(self.seed))


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


    def __import_medusa_card_state(self):
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
        if self.search == '':
            self.reshuffle = True
        else:
            self.reshuffle = False

        # First, check if any of the search terms should be processed as a
        # cardtype and be added to the filter state instead.
        if self.search is not None:
            searchterms = self.search.split(' ')
            searchterms = filter(None, searchterms)   # remove nulls
            [ newfilters, removeterms ] = BaseState._process_search_strings('#', searchterms)
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
                [ newfilters, removeterms ] = BaseState._process_search_strings('#', hashtag_process)
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
        self.__import_random_seed()          # Import the random seed first. TODO: move to constantina state
        self.__import_medusa_card_state()    # Then import the normal content cards
        BaseState._import_theme_state(self)  # Theme settings. TODO: move to constantina state
        self.__import_search_state()         # Search strings and processing out filter strings
        self.__import_filter_state()         # Any filter strings loaded from prior pages
        self.__import_filtered_card_count()  # Number of cards filtered out of prior pages
        self.__import_permalink_state()      # Permalink settings
        self.__import_page_count_state()     # Figure out what page we're on


    def __calculate_last_distance(self, cards):
        """
        The main part about state tracking in Constantina is tracking how far
        the closest card to the beginning of a page load is.

        Prior to exporting a page state, loop over your list of cards, tracking
        news cards and heading cards separately, and determine how far each ctype
        card is from the beginning of the next page that will be loaded.
        """
        # TODO: migrate to BaseState and make more generic
        all_ctypes = self.config.options("card_counts")

        # Populate the state object, which we'll later build the
        # state_string from. Don't deal with news items yet
        for card in cards:
            # Do not proces news items in the state variable
            if (card.ctype == 'news') or (card.ctype == 'heading'):
                continue
            # For adding into a string later, make card.num a string too
            getattr(self, card.ctype).clist.append(str(card.num))
            if card.ctype not in all_ctypes:
                all_ctypes.append(card.ctype)

        # Add distance values to the end of each state_hash
        # array, as is the standard for these state tokens.
        done_distance = []
        all_ctypes.sort()

        # Terminate the loop if we either get to the bottom of the
        # array, or whether we've calculated distances for all
        # possible state types
        hidden_cards = 0    # Account for each hidden card in the distance
                            # between here and the end of the page
        news_seen = False   # Have we processed a news card yet?
        # Traversing backwards from the end, find the last of each cardtype shown
        for i in xrange(len(cards) - 1, -1, -1):
            card = cards[i]
            if card.ctype == 'news':
                if news_seen is False:
                    self.news.distance = card.num
                    news_seen = True
                continue
            if card.ctype == 'heading':
                # Either a tombstone card or a "now loading" card
                # Subtract one from the distance of "shown cards"
                hidden_cards = hidden_cards + 1
                continue
            if card.ctype in done_distance:
                continue

            # We've now tracked this card type
            done_distance.append(card.ctype)
            done_distance.sort()

            dist = len(cards) - hidden_cards - i
            # syslog.syslog("=> %s dist: %d i: %d card-len: %d  eff-len: %d" %
            #              (card.ctype, dist, i, len(cards), len(cards) - hidden_cards))
            getattr(self, card.ctype).distance = str(dist)
            # Early break once we've seen all the card types
            if done_distance == all_ctypes:
                break


    def __export_random_seed(self):
        """Export the random seed for adding to the state variable"""
        return str(self.seed).replace("0.", "")


    def __export_medusa_card_state(self):
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
        self.__calculate_last_distance(cards)

        # Finally, construct the state string for the next page
        export_parts = [self.__export_random_seed(),
                        self.__export_medusa_card_state(),
                        self.__export_search_state(query_terms),
                        self.__export_filter_state(filter_terms),
                        self.__export_filtered_card_count(filtered_count),
                        self.__export_page_count_state(),
                        BaseState._export_theme_state(self)]

        export_parts = filter(None, export_parts)
        export_string = ':'.join(export_parts)
        return export_string


    def export_display_state(self):
        """Just export enough state for links in textcards that preserve theme"""
        return self.__export_theme_state()


    def configured_states(self):
        """
        Check to see which special states are enabled. Return an array of
        either card types or special state types that are not set to None.
        """
        state_names = [val[1] for val in self.config.items('special_states')]
        state_names.remove('page')       # These two are set no matter what
        state_names.remove('filtered')
        return [state for state in state_names
                      if ((getattr(self, state) != None) and
                          (getattr(self, state) != []))]


    def fresh_mode(self):
        """Either an empty state, or just an empty state and a theme is set"""
        if (((self.in_state is None) or (self.configured_states() == ['appearance'])) and
             (self.page == 0) and
             (self.reshuffle is False)):
            return True
        else:
            return False


    def reshuffle_mode(self):
        """An empty search was given, so reshuffle the page"""
        if ((self.search is not None) and
            (self.reshuffle is True) and
            (self.card_filter is None)):
            return True
        else:
            return False


    def permalink_mode(self):
        """Is one of the permalink modes on?"""
        if ((self.news_permalink is not None) or
            (self.features_permalink is not None) or
            (self.topics_permalink is not None)):
            return True
        else:
            return False


    def exclude_cardtype(self, ctype):
        """
        Is a card filter in place, and if so, is the given card type being filtered?
        If this returns true, it means the user either wants cards of this type, or
        that no card filtering is currently in place.
        """
        if ((self.card_filter is not None) and
            (getattr(self, ctype).filtertype is False)):
            return True
        else:
            return False


    def filter_processed_mode(self):
        """
        Is it a search state, and did we already convert #hashtag strings
        into filter queries?
        """
        states = self.configured_states()
        if (('search' in states) or
            ('card_filter' in states)):
            return True
        else:
            return False


    def filter_only_mode(self):
        """All search queries converted into card filters"""
        if self.configured_states() == ['card_filter']:
            return True
        else:
            return False


    def search_only_mode(self):
        """There is a search query, but no terms converted into card filters"""
        if self.configured_states() == ['search']:
            return True
        else:
            return False


    def search_mode(self):
        """Any valid state from a search mode will trigger this mode"""
        if ((self.search is not None) or
            (self.card_filter is not None) or
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
        for ctype in self.config.get("card_properties", "pagecount").replace(" ", "").split(","):
            card_limit = card_limit + getattr(self, ctype).file_count
        # syslog.syslog("card_limit: " + str(card_limit) + "   card_count: " + str(card_count))
        if card_count >= card_limit:
            return True
        else:
            return False



class MedusaCard:
    """
    Constantina is a single-page layout consisting of cards. For now
    it is also a single-column layout. A card may contain a news item,
    an image, a feature, a header/footer, an ad, or an embedded media
    link. We track whether the image or link may be duplicated within
    the card, as well as what its page index and type are.
    """

    def __init__(self, ctype, num, state=False, grab_body=True, permalink=False, search_result=False):
        self.config = ConfigParser.SimpleConfigParser()
        self.config.read('medusa.ini')

        self.title = self.config.get("card_defaults", "title")
        self.topics = []
        self.body = self.config.get("card_defaults", "body")
        self.ctype = ctype
        # Request either the Nth entry of this type, or a specific utime/date
        self.num = num
        # If we need to access data from the state object, for card shuffling
        self.state = state
        self.songs = []
        self.cfile = self.config.get("card_defaults", "file")
        self.cdate = self.config.get("card_defaults", "date")
        self.permalink = permalink
        self.search_result = search_result
        self.hidden = False
        # Don't hit the filesystem if we're just tracking which cards have
        # been previously opened (MedusaPage.__get_previous_cards)
        if grab_body is True:
            self.cfile = self.__openfile()


    def __openfile(self):
        """
        Open a file in a folder by "number", and populate the MedusaCard object.

        For most files, this will be an integer (card number) that represents
        the Nth file in a directory.
        For news files, the filename itself is a Unix timestamp number, and
        can be specified directly.
        """
        type_files = opendir(self.ctype, self.hidden)

        # Find the utime value in the array if the number given isn't an array index.
        # If we're inserting cards into an active page, the state variable will be
        # given, and should be represented by a shuffled value.
        random_types = self.config.get("card_properties", "randomize").replace(" ", "").split(",")

        # Even if we have cards of a type, don't run this logic if cards array is []
        if ((self.ctype in random_types) and
            (self.state is not False) and
            (self.search_result is False) and
            (self.hidden is False) and
            (getattr(self.state, self.ctype).clist != [])):
            card_count = len(getattr(self.state, self.ctype).clist)
            which_file = getattr(self.state, self.ctype).clist[self.num % card_count]

            # Logic for hidden files, which only works because it's inside the
            # random_types check
            if which_file == 'x':
                self.hidden = True
                type_files = opendir(self.ctype, self.hidden)
                # syslog.syslog(str(BaseFiles.keys()))
                hidden_cards = xrange(0, len(BaseFiles[self.ctype + "/hidden"]))
                self.num = hidden_cards[randint(0, len(hidden_cards)-1)]
                # syslog.syslog("open hidden file: " + str(self.num) + "/" + str(hidden_cards))
                which_file = self.num
            else:
                pass

        else:
            which_file = self.num

        # News files: convert utime filename to the "Nth" item in the folder
        if which_file >= len(type_files):
            if self.num in type_files:
                which_file = type_files.index(self.num)
                self.num = which_file
            else:
                return "nofile"

        return self.__interpretfile(type_files[which_file])


    def __songfiles(self):
        """Create an array of song objects for this card"""
        for songpath in self.body.splitlines():
            songpath = self.config.get("paths", "songs") + "/" + songpath
            self.songs.append(MedusaSong(songpath))


    def __interpretfile(self, thisfile):
        """File opening heuristics.

        First, assume that files in each folder are indicative of their
        relative type. Images are in the image folder, for instance.

        Secondly, assume that non-media folders follow the "news entity"
        format of title-line, keywords-line, and then body.

        Prove these heuristics with a Python file-type check. Anything
        that doesn't pass muster returns "wrongtype".
        """
        magi = magic.Magic(mime=True)

        base_path = self.config.get("paths", self.ctype)
        if self.hidden is True:
            fpath = base_path + "/hidden/" + thisfile
        else:
            fpath = base_path + "/" + thisfile

        try:
            with open(fpath, 'r') as cfile:
                ftype = magi.from_file(fpath)
                # News entries or features are processed the same way
                if (("text" in ftype) and
                    ((self.config.get("paths", "news") in cfile.name) or
                     (self.config.get("paths", "heading") in cfile.name) or
                     (self.config.get("paths", "quotes") in cfile.name) or
                     (self.config.get("paths", "topics") in cfile.name) or
                     (self.config.get("paths", "features") in cfile.name))):
                    self.title = cfile.readline().replace("\n", "")
                    rawtopics = cfile.readline().replace("\n", "")
                    for item in rawtopics.split(', '):
                        self.topics.append(item)
                    self.body = cfile.read()

                # Multiple-song playlists
                if (("text" in ftype) and
                    (self.config.get("paths", "songs") in cfile.name)):
                    self.title = fpath
                    self.topics.append("Song Playlist")
                    self.body = cfile.read()
                    self.__songfiles()   # Read song metadata

                # Single-image cards
                if ((("jpeg" in ftype) or ("png" in ftype)) and
                     (self.config.get("paths", "images") in cfile.name)):
                    # TODO: alt/img metadata
                    self.title = fpath
                    self.topics.append("Images")
                    self.body = fpath

                # Single-song orphan cards
                if ((("mpeg" in ftype) and ("layer iii" in ftype)) and
                     (self.config.get("paths", "songs") in cfile.name)):
                    self.title = fpath            # TODO: filename from title
                    self.topics.append("Songs")   # TODO: include the album
                    self.body = fpath
                    self.__songfiles()   # Read song metadata

            # If the filename is in unix-time format, track the creation date
            if thisfile.isdigit():
                if int(thisfile) > 1141161200:
                    self.cdate = datetime.fromtimestamp(int(thisfile)).strftime("%B %-d, %Y")
            else:
                fnmtime = os.path.getmtime(fpath)
                self.cdate = datetime.fromtimestamp(int(fnmtime)).strftime("%B %-d, %Y")

            file.close(cfile)

        except:   # File got moved in between dirlist caching and us reading it
            return self.config.get("card_defaults", "file")

        if self.hidden is True:
            return self.config.get("paths", self.ctype) + "/hidden/" + thisfile
        else:
            return self.config.get("paths", self.ctype) + "/" + thisfile



class MedusaSong:
    """
    Basic grouping of song-related properties with a filename.
    Use pymad to determine the length of each song that appears
    in the page itself.
    """
    def __init__(self, filename):
        self.songfile = filename
        self.songtitle = filename.split("/")[-1].replace(".mp3", "")
        time = MadFile(filename).total_time() / 1000
        minutes = time / 60
        seconds = time % 60
        self.songlength = str(minutes) + ":" + str(seconds)
        songmb = os.path.getsize(filename) / 1048576.0
        self.songsize = "%.2f MB" % songmb
