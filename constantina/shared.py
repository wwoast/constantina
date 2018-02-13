from datetime import datetime
import os
import sys
import time
from urllib import unquote_plus
import syslog
import configparser
from math import floor
from random import randint, shuffle


syslog.openlog(ident='constantina.shared')

Instance = os.environ.get("INSTANCE") or "default"
GlobalConfig = configparser.SafeConfigParser()
# Configuration setup must find the Global Config file in one of these paths.
# Once you have GlobalConfig, the other config files can then be enumerated.
ConfigOptions = [
    sys.prefix + "/etc/constantina/" + Instance + "/constantina.ini",
    "/etc/constantina/" + Instance + "/constantina.ini",
    os.path.expanduser("~") + "/constantina/etc/constantina/default/constantina.ini"
]
GlobalConfig.read(ConfigOptions)

# An alphabet used for opaque instance IDs that is BASE62 minus homomorph
# characters that could easily be mistaken for each other.
OpaqueBase = '23456789abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ'

# Only do opendir once per directory, and store results here
# The other Constantina modules need access to this "globally".
BaseFiles = {}


class GlobalClock:
    """
    Global clock that can be updated. Designed to help Constantina use
    consistent timestamps through a single request, and not leak data about
    how long components of Constantina take.
    """
    def __init__(self):
        self.time = int(time.time())

    def update(self):
        """Set new time based on the current system time."""
        self.time = int(time.time())


GlobalTime = GlobalClock()


class BaseCardType:
    """
    Constantina Card Type State Tracking.

    In the SubApplicationState class, we track the following properties per-card-type:
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
    Constantina Page State Object, base methods.
    Constantina consists of three sub-applications (forum, blog, mail) and
    each one has its own config file and tracks its own state, extended from
    this utility class.

    Constantina state values are serialized and deserialized from a string
    embedded into the page itself that describes the following details:
        - The distance from the last-displayed item of this type to the end
          of the displayed page
        - The seed number that defines the displayed random order
        - Any search strings that might have been provided in previous views
        - Whether a permalink is being viewed (feature, news, or topic page)
    It also provides a clean interface to global modes and settings that
    influence what content and appearances a Constantina page can take.
    """
    def __init__(self, in_state=None, config_file=None):
        self.in_state = in_state   # Track the original state string
        self.ctypes = []           # Card types in this application
        self.searchtypes = []      # Cards that are indexed/searchable
        self.specials = []         # Special states associated with an app
 
        if config_file is not None:
            self.__read_config(config_file)
            self.__set_state_defaults()

        # Was there an initial state string? Process it if there was.
        if self.in_state is not None:
            self.state_vars = self.in_state.split(':')
        else:
            self.state_vars = []


    def __read_config(self, config_file):
        """Read the configuration file that will populate the sub-application"""
        self.config_path = GlobalConfig.get('paths', 'config_root') + "/" + config_file
        self.config = configparser.SafeConfigParser()
        self.config.read(self.config_path)


    def __set_state_defaults(self):
        """
        Set default values for special_state properties and normal content-card
        properties, as well as upper limits on how many cards can exist on a
        single Constantina page for this type of application.
        """
        self.max_items = 0             # Max items per page, based on
                                       # counts from all card types
        for ctype, cpp in self.config.items('card_counts'):
            self.max_items = self.max_items + int(cpp)

        # For the card types in the card_counts config, create variables, i.e.
        #   state.news.distance, state.topics.spacing
        for ctype, card_count in self.config.items('card_counts'):
            self.ctypes.append(ctype)
            setattr(self, ctype, BaseCardType(
                config=self.config,
                ctype=ctype,
                count=int(card_count),
                distance=None,
                filtertype=False,
                spacing=self.config.getint('card_spacing', ctype)))

        for spctype, spcfield in self.config.items("special_states"):
            self.specials.append(spcfield)      # List of spc state names
            setattr(self, spcfield, None)       # All state vals are expected to exist

        # Track which card types should be searchable, randomized, countable
        for section in ["search", "randomize", "pagecount"]:
            setattr(self, section, [])
        search_types = self.config.get("card_properties", "search").replace(" ", "").split(",")
        for ctype in search_types: 
            self.searchtypes.append(ctype)
        randomize_types = self.config.get("card_properties", "randomize").replace(" ", "").split(",")
        for ctype in randomize_types: 
            self.randomize.append(ctype)
        pagecount_types = self.config.get("card_properties", "pagecount").replace(" ", "").split(",")
        for ctype in pagecount_types: 
            self.pagecount.append(ctype)


    def _int_translate(self, checkval, width, default):
        """Take a string of digits and convert width chars into an integer"""
        # TODO: need adjustable number of digits!?
        if checkval.isdigit():
            checkval = int(checkval[0:width])
        else:   # Invalid input gets a chosen default
            checkval = default
        return checkval


    def _find_state_variable(self, query):
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
        if query == "seed":
            hits = [token for token in self.state_vars if token.isdigit()]
            if len(hits) > 0:
                output = hits[0]
        # Special state variables are singleton values. Typically a
        # two-letter value starting with "x" as the first letter.
        elif self.config.has_option("special_states", query):
            hits = [token for token in self.state_vars if token.find(query) == 0]
            if len(hits) > 0:
                output = unquote_plus(hits[0][2:])
        # Individual content card state variables. Each one is a distance
        # from the current page.
        elif query in [s[0] for s in self.config.options("card_counts")]:
            hits = [token for token in self.state_vars if token.find(query) == 0]
            # syslog.syslog("query: %s  hits: %s" % (query, hits))
            if len(hits) > 0:
                output = int(hits[0][1:])

        # Remove any matches for state variables, including extraneous duplicates
        [self.state_vars.remove(x) for x in hits]
        return output


    def _process_search_strings(self, sigil, searchterms):
        """
        If you type a hashtag string like #news into the search box, Constantina
        will do a filter based on the cardtype you want. It uses this function
        to isolate out any special sigil-prefixed strings from a search,
        including #cardtypes, @usernames, and $subjects.

        Returns an array of arrays, first being the terms to migrate to the
        destination state var, and the second the list of strings to remove
        from the search string list.
        """
        filtertypes = []
        removeterms = []

        for term in searchterms:
            # syslog.syslog("searchterm: " + term + " ; allterms: " + str(searchterms))
            if term[0] == '#':
                for ctype, filterlist in self.config.items("card_filters"):
                    filternames = filterlist.replace(" ", "").split(',')
                    for filtername in filternames:
                        if (term == sigil + filtername):
                            # Add to the list of filterterms, and prepare to
                            # remove any filter tags from the search state.
                            filtertypes.append("#" + ctype)
                            removeterms.append(term)

        return [ filtertypes, removeterms ]


    def _calculate_last_distance(self, cards, common="news"):
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
            # TODO: define "body" cards that don't get processed here per ini file
            # (in the zoo, threads work the same as medusa news cards)
            if (card.ctype == common) or (card.ctype == 'heading'):
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
        common_seen = False # Have we processed a news card yet?
        # Traversing backwards from the end, find the last of each cardtype shown
        for i in xrange(len(cards) - 1, -1, -1):
            card = cards[i]
            if card.ctype == common:
                if common_seen is False:
                    getattr(self, common).distance = card.num
                    common_seen = True
                    syslog.syslog("last_dist: %s dist: %d i: %d card-len: %d  eff-len: %d" %
                                 (card.ctype, card.num, i, len(cards), len(cards) - hidden_cards))
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
            syslog.syslog("=> %s dist: %d i: %d card-len: %d  eff-len: %d" %
                         (card.ctype, dist, i, len(cards), len(cards) - hidden_cards))
            getattr(self, card.ctype).distance = str(dist)
            # Early break once we've seen all the card types
            if done_distance == all_ctypes:
                break


def count_ptags(processed_lines):
    """
    Count all the <p> tags. If there's less than three paragraphs, the
    create_card logic may opt to disable the card's "Read More" link.
    """
    ptags = 0
    for line in processed_lines:
        if line.find('<p>') >= 0:
            ptags = ptags + 1
    return ptags


def unroll_newlines(body_lines):
    """
    Given lines of text, remove all newlines that occur within an
    HTML element. Anything that we parse with ElementTree will inevitably
    start trying to use this utility function.
    """
    processed_lines = []
    pro_line = ""
    i = 0

    # For processing purposes, if no p tag at the beginning of a line, combine
    # it with the next line. This guarantees one HTML tag per line for the
    # later per-element processing
    while i < len(body_lines):
        # Add a space back to the end of each line so
        # they don't clump together when reconstructed
        this_line = body_lines[i].strip() + " "
        # Don't parse empty or whitespace lines
        if (this_line.isspace()) or (this_line == ''):
            i = i + 1
            continue

        # Break a line out whenever you see one of these elements.
        # In other words, Constantina page processing looks at each
        # of these elements on a single line.
        if this_line.find('<p>') == 0:
            if not ((pro_line.isspace()) or (pro_line == '')):
                processed_lines.append(pro_line)
            pro_line = this_line
        elif (this_line.find('<img') != -1):
            if not ((pro_line.isspace()) or (pro_line == '')):
                processed_lines.append(pro_line)
            pro_line = this_line
        elif (this_line.find('<div') != -1):
            if not ((pro_line.isspace()) or (pro_line == '')):
                processed_lines.append(pro_line)
            pro_line = this_line
        elif (this_line.find('<ul') != -1):
            if not ((pro_line.isspace()) or (pro_line == '')):
                processed_lines.append(pro_line)
            pro_line = this_line
        elif (this_line.find('<ol') != -1):
            if not ((pro_line.isspace()) or (pro_line == '')):
                processed_lines.append(pro_line)
            pro_line = this_line
        elif (this_line.find('<h5') != -1):
            if not ((pro_line.isspace()) or (pro_line == '')):
                processed_lines.append(pro_line)
            pro_line = this_line
        else:
            pro_line += this_line
        i = i + 1

    processed_lines.append(pro_line)
    return processed_lines


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


def opendir(config, ctype, hidden=False, page=0):
    """
    Return either cached directory information or open a dir and
    list all the files therein. Used for both searching and for the
    card reading functions, so it's part of the shared module.
    """
    card_root = GlobalConfig.get("paths", "data_root") + "/private"

    # Support paging on card types that we do have counts for.
    card_count = 0
    previous_items = 0
    if ctype in [c[0] for c in config.items("card_counts")]:
        card_count = config.getint("card_counts", ctype)
        previous_items = card_count * page

    directory = card_root + "/" + config.get("paths", ctype)
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
        # so that subdirectories don't get fopen'ed later. Also
        # don't include any placeholder files that keep the dir
        # structure for packaging purposes.
        for idx, testpath in enumerate(dirlisting):
            if os.path.isfile(os.path.join(directory, testpath)):
                if testpath.find("placeholder") == -1:
                    if page == 0:
                        BaseFiles[ctype].append(testpath)
                    elif ((page > 0) and 
                          (idx > previous_items) and
                          (idx <= previous_items + card_count)):
                        BaseFiles[ctype].append(testpath)
                    else:
                        pass

        # Sort the output. Most directories should use
        # utimes for their filenames, which sort nicely. Use
        # reversed array for newest-first utime files
        BaseFiles[ctype].sort()
        BaseFiles[ctype].reverse()

        # For news items, remove any items newer than the current time
        if ctype == "news":
            BaseFiles[ctype] = remove_future(BaseFiles[ctype])

        # syslog.syslog("ctype: %s   basefiles: %s" % (ctype, BaseFiles[ctype]))

    return BaseFiles[ctype]


def opaque_identifier(random_id=randint(0, 2**32-1)):
    """
    Create an opaque instance ID. This is used for a couple things:
    1) So that cookies for multiple Constantina instances on the same domain name,
       don't squash each other. (instance_id)
    2) So that each user preference key has a unique identifier that can be merged
       with the above instance_id.
    It's a random number, converted to a BASE62 minus similar characters list.
    """
    base = OpaqueBase
    length = len(base)
    opaque = ''
    while random_id != 0:
        opaque = base[random_id % length] + opaque
        random_id /= length
    return opaque


def opaque_integer(given_id):
    """
    Convert an opaque identifier back into the random number it came from.
    """
    base = OpaqueBase
    length = len(base)
    strlen = len(given_id)
    num = 0
    idx = 0
    for char in given_id:
        power = (strlen - (idx + 1))
        num += base.index(char) * (length ** power)
        idx += 1
    return num


def opaque_mix(id1, id2):
    """
    Given two opaque identifiers, convert them back to integers, XOR the results,
    and then create a new opaque identifier from the result.
    """
    rand1 = opaque_integer(id1)
    rand2 = opaque_integer(id2)
    return opaque_identifier(rand1 ^ rand2)


def specific_cookie(check_name, raw_cookies):
    """
    Split out just the JWE part of the cookie. Since we split by semicolon,
    we also need to take off leading spaces (lstrip) that browsers tend to
    print after semicolon-delimited lists of cookies.
    """
    if raw_cookies is None:
        return None
    for raw_data in raw_cookies.split(';'):
        raw_cookie = raw_data.lstrip()
        cookie_name = raw_cookie.split('=')[0]
        token = raw_cookie.split('=')[1]
        if cookie_name == check_name:
            return token
    return None


def multipart_section(buffer, cur_line, delimiter):
    """
    Given a multipart form delimiter, read in a single section.
    """
    start_line = cur_line
    section = {
        'length': 0,
        'name': None,
        'value': None,
        'type': None
    }
    while buffer[cur_line].find(delimiter) != 0:
        cur_line = cur_line + 1
    cur_line = cur_line + 1   # Past the delimiter
    if cur_line >= len(buffer):   # End of buffer, after terminating delim?
        section['length'] = cur_line - start_line
        return section

    fields = buffer[cur_line].split(';')
    # We only care about the name part here
    for field in fields:
        field = field.lstrip().rstrip()
        if field.find('name') == 0:   # name=(someval)
            name_string = field.split("=")[1]
            section['name'] = name_string[1:-1]   # no double quotes
            break

    cur_line = cur_line + 1
    if cur_line >= len(buffer):   # End of buffer, after terminating delim?
        section['length'] = cur_line - start_line
        return section
    while buffer[cur_line] == '':   # Skip any empty lines
        cur_line = cur_line + 1

    if buffer[cur_line].find("Content-Type") == 0:
        fields = buffer[cur_line].split(':')
        section['type'] = fields[1].lstrip().rstrip()
        cur_line = cur_line + 1
    if cur_line >= len(buffer):   # End of buffer, after terminating delim?
        section['length'] = cur_line - start_line
        return section
    while buffer[cur_line] == '':   # Skip any empty lines, and then content!
        cur_line = cur_line + 1
        
    content = []
    while buffer[cur_line].find(delimiter) != 0:
        content.append(buffer[cur_line])
        cur_line = cur_line + 1
    section['value'] = '\r\n'.join(content)
    section['length'] = cur_line - start_line

    return section


def process_multipart_form(buffer):
    """
    Grab the relevant POST variables for processing by other code.

    Constantina expects there to be an 'action' variable POSTed in a form that's
    a hidden <input> field. This is how Constantina decides what other methods
    will process the FORM data.

    For multipart (file-upload) forms, be very touchy on formats. The multipart
    delimiter should not be too short or too long, and should be matched by hash.
    If the data is too big, just cancel outright.
    """
    inbuf = buffer.split('\r\n')
    # First line is multipart delimiter. Be sensitive if the line is too long
    delimiter = inbuf[0]
    syslog.syslog(delimiter)
    if len(delimiter) < 0 or len(delimiter) > 100:
        return {}
    sections = []
    post = {}
    cur_line = 0 
    while cur_line < len(inbuf):
        # First line is the multipart delimiter
        # Next line is semicolon-delimited field=value pairs
        # This is followed by a blank line
        # Finally, the value appears. Read in value until the next delimiter
        mp = multipart_section(inbuf, cur_line, delimiter)
        sections.append(mp)
        cur_line = cur_line + mp['length']

    for section in sections:
        # Naive assume no duplicated form inputs. First form input is the correct one
        if post.get(section['name']) is None and section.get('value') is not None:
            post[section['name']] = section['value']
            syslog.syslog("%s = %s" % (section['name'], post[section['name']][0:3]))
        # Support single file uploads for now
        if post.get('type') is None and section.get('type') is not None:
            post['file'] = section['value']
            post['type'] = section['type']
            syslog.syslog("type = %s" % (post['type']))

    return post


def process_simple_post(inbuf):
    """
    Grab the relevant POST variables for processing by other code.

    Constantina expects there to be an 'action' variable POSTed in a form that's
    a hidden <input> field. This is how Constantina decides what other methods
    will process the FORM data.

    This is just for standard FORM "option1=value1&option2=value2" POST data.
    """
    # TODO: equals-sign in form will break this!
    post = {}
    for vals in inbuf.split('&'):
        if vals.find("=") == -1:
            continue
        [key, value] = vals.split('=')
        post[key] = value
    return post   # TODO: unify output formats


def process_post(env):
    """
    Grab the relevant length of bytes. Use a basic heuristic to determine whether
    this is a multipart form or not.
    """
    read_size = int(env.get('CONTENT_LENGTH'))
    max_size = GlobalConfig.getint('miscellaneous', 'max_request_size_mb') * 1024 * 1024
    if read_size >= max_size:
        return {}   # Don't process overlarge form inputs
    inbuf = env['wsgi.input'].read(read_size)
    if inbuf.find("-----") == 0:   # Delimiter heuristic
        return process_multipart_form(inbuf)
    else:
        return process_simple_post(inbuf)


def escape_amp(in_str):
    """Just escape ampersand characters so the etree parser can do its job."""
    return in_str.replace("&", "&amp;")


def urldecode(in_uri):
    """TODO: Establish a standard by which authenticated files are read from disk."""
    return unquote_plus(in_uri)


def safe_path(in_uri):
    """
    If a path has unsafe tendencies in it, just return 404.
    TODO: lots of security testing, limiting to configured known-good folders
    """
    if in_uri is None:
        return True
    # Prevents direct directory traversal in the URI
    if in_uri.find("..") != -1 or in_uri.find("//") != -1:
        return False
    return True
    