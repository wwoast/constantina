from datetime import datetime
import os
import syslog
import ConfigParser
from math import floor
from random import shuffle
from urllib import unquote_plus

syslog.openlog(ident='constantina_shared')


# Only do opendir once per directory, and store results here
# The other Constantina modules need access to this "globally".
BaseFiles = {}

global_config = ConfigParser.SafeConfigParser()
global_config.read('constantina.ini')


class BaseCardType:
    """
    Constantina Card Type State Tracking.

    In the MedusaState class, we track the following properties per-card-type:
        - How many of each item was displayed
        - Which news or image items were displayed
            - This is condensed into a start and end range of file indices
              in each card-type data directory
        - The distance from the last-displayed item of this type to the end
          of the displayed page
        - The spacing per page of news cards
        - Whether the page state is asking to filter cards of a specific type

    Through checking the configured card_counts, we create one of these
    objects named for each card type (ctype).
    """
    def __init__(self, config, ctype, count, distance, filtertype, spacing):
        self.config = config
        self.ctype = ctype
        self.count = count
        self.distance = distance
        self.filtertype = filtertype
        self.spacing = spacing

        self.clist = []      # List of card indexes that appeared of this type
        # Number of files of this type
        self.file_count = len(opendir(self.config, self.ctype))
        # Files per page of this type
        self.per_page = config.getint("card_counts", self.ctype)
        # How many ctype cards should we see before the same card
        # appears again in the randomized view? This is a function
        # of the number of available cards
        if self.per_page == 0:
            self.page_distance = 0
        else:
            self.page_distance = self.file_count*2 / self.per_page


    def shuffle(self):
        """
        Once a fixed seed is set in the state object, run the shuffle method
        to get the shuffled file listing for this ctype created.
        """
        self.__shuffle_files()
        # syslog.syslog("Shuffled list of " + self.ctype + ": " + str(self.clist))
        self.__mark_uneven_distribution()
        # syslog.syslog("Marked list of " + self.ctype + ": " + str(self.clist))
        self.__replace_marked()
        # syslog.syslog("Final list of " + self.ctype + ": " + str(self.clist))


    def __shuffle_files(self):
        """
        Take a card type, and create a shuffle array where we can preserve
        normal page-state numbering, using those page-state values as indexes
        into a shuffled list of files. The shuffled array is extended, but
        adjusted so that repeat rules across pages will be respected
        """
        # TODO: news doesn't generalize anymore. Needs to come from page_state.
        total_pages = int(floor(len(opendir(self.config, "news")) / self.config.getint("card_counts", "news")))
        total_ctype = total_pages * self.per_page

        # Guarantee enough cards to choose from
        self.clist = range(0, self.file_count) * total_ctype
        self.clist = self.clist[0:total_ctype]
        shuffle(self.clist)


    def __mark_uneven_distribution(self):
        """
        Look across a clist and remove any cards that would appear on the next
        Nth page, which duplicate a card you've seen on this page. The array is made
        large enough that just outright removing items should be ok. The N distance
        between pages is a function of the number of possible elements.
        """
        for i in range(0, len(self.clist)):
            if self.clist[i] == 'x':
                continue

            part_end = i + self.page_distance
            if i + part_end > len(self.clist):
                part_end = len(self.clist)

            # Mark array items for removal
            for j in range(i+1, part_end):
                if self.clist[i] == self.clist[j]:
                    self.clist[j] = 'x'


    def __replace_marked(self):
        """
        Given 'x' marked indexes from __mark_even_distribution, determine good
        replacement values.
        """
        for i in range(0, len(self.clist)):
            if self.clist[i] != 'x':
                continue

            part_start = i - self.page_distance
            if i - part_start < 0:
                part_start = 0
            part_end = i + self.page_distance
            if i + part_end > len(self.clist):
                part_end = len(self.clist)

            choices = range(0, self.file_count)
            shuffle(choices)
            for k in choices:
                if k not in self.clist[part_start:part_end]:
                    self.clist[i] = k
                    break


class BaseState:
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
    def __init__(self, config_file, in_state=None):
        # self.config_file = global_config.get('paths', 'config') + "/" + config_file
        self.config = ConfigParser.SafeConfigParser()
        self.config.read("/var/www-cgi/staging/medusa.ini")

        self.in_state = in_state      # Track the original state string
        self.__set_state_defaults()

        # Was there an initial state string? Process it if there was.
        if self.in_state is not None:
            self.state_vars = self.in_state.split(':')
        else:
            self.state_vars = []


    def __int_translate(self, checkval, width, default):
        """Take a string of digits and convert width chars into an integer"""
        if checkval.isdigit():
            checkval = int(checkval[0:width])
        else:   # Invalid input gets a chosen default
            checkval = default
        return checkval


    def __set_state_defaults(self):
        """
        Set basic default values for special_state properties and normal
        content-card properties, as well as upper limits on how many cards can
        exist on a single Constantina page.
        """
        self.max_items = 0             # Max items per page, based on
                                       # counts from all card types
        for ctype, cpp in self.config.items('card_counts'):
            self.max_items = self.max_items + int(cpp)

        # For the card types in the card_counts config, create variables, i.e.
        #   state.news.distance, state.topics.spacing
        for ctype, card_count in self.config.items('card_counts'):
            setattr(self, ctype, BaseCardType(
                config=self.config,
                ctype=ctype,
                count=int(card_count),
                distance=None,
                filtertype=False,
                spacing=self.config.getint('card_spacing', ctype)))

        for spctype, spcfield in self.config.items("special_states"):
            setattr(self, spcfield, None)       # All state vals are expected to exist


    def __find_state_variable(self, search):
        """
        Leveraged by all the other state functions. Find the given state
        variable, either by state variable name, or "number" to find the
        random seed. Once a state variable is consumed, remove it from
        the state_vars.
        """
        if self.state_vars == []:
            return None
        hits = []
        output = None

        # Random seed is the one all-numeric state variable
        if search == "seed":
            hits = [token for token in self.state_vars if token.isdigit()]
            if len(hits) > 0:
                output = hits[0]
        # Special state variables are singleton values. Typically a
        # two-letter value starting with "x" as the first letter.
        elif self.config.has_option("special_states", search):
            hits = [token for token in self.state_vars if token.find(search) == 0]
            if len(hits) > 0:
                output = unquote_plus(hits[0][2:])
        # Individual content card state variables. Each one is a distance
        # from the current page.
        elif search in [s[0] for s in self.config.options("card_counts")]:
            hits = [token for token in self.state_vars if token.find(search) == 0]
            if len(hits) > 0:
                output = int(hits[0][1:])

        # Remove any matches for state variables, including extraneous duplicates
        [self.state_vars.remove(x) for x in hits]
        return output


    def __import_theme_state(self):
        """
        In the state object, we track an appearance variable, which corresponds
        to the exact state variable imported (and exported) for the appearance.

        The appearance value lets us look up which theme we display for the user.
        This theme value is a path fragment to a theme's images and stylesheets.
        """
        appearance_state = self.__find_state_variable('xa')

        if appearance_state is not None:
            # Read in single char of theme state value
            self.appearance = self.__int_translate(appearance_state, 1, 0)

        global_config = ConfigParser.SimpleConfigParser()
        global_config.read('constantina.ini')

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


    def __export_theme_state(self):
        """If tracking an appearance or theme, include it in state links"""
        appearance_string = None
        if self.appearance is not None:
            appearance_string = "xa" + str(self.appearance)
        return appearance_string



def remove_future(dirlisting):
    """For any files named after a Unix timestamp, don't include the
    files in a directory listing if the timestamp-name is in the future.
    Assumes the dirlisting is already sorted in reverse order!"""
    for testpath in dirlisting:
        date = datetime.fromtimestamp(int(testpath)).strftime("%s")
        current = datetime.strftime(datetime.now(), "%s")
        if date > current:
            dirlisting.remove(testpath)
        else:
            break

    return dirlisting


def opendir(config, ctype, hidden=False):
    """
    Return either cached directory information or open a dir and
    list all the files therein. Used for both searching and for the
    card reading functions, so it's part of the shared module.
    """
    directory = config.get("paths", ctype)
    if hidden is True:
        directory += "/hidden"
        ctype += "/hidden"

    # If the directory wasn't previously cached
    if ctype not in BaseFiles.keys():
        # Default value. If no files, keep the empty array
        BaseFiles[ctype] = []

        dirlisting = os.listdir(directory)
        if dirlisting == []:
            return BaseFiles[ctype]

        # Any newly-generated list of paths should be weeded out
        # so that subdirectories don't get fopen'ed later
        for testpath in dirlisting:
            if os.path.isfile(os.path.join(directory, testpath)):
                BaseFiles[ctype].append(testpath)

        # Sort the output. Most directories should use
        # utimes for their filenames, which sort nicely. Use
        # reversed array for newest-first utime files
        BaseFiles[ctype].sort()
        BaseFiles[ctype].reverse()

        # For news items, remove any items newer than the current time
        if ctype == "news":
            BaseFiles[ctype] = remove_future(BaseFiles[ctype])

    return BaseFiles[ctype]
