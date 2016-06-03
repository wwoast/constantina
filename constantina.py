from math import ceil, floor
from random import random, randint, seed, shuffle
from cgi import FieldStorage
from PIL import Image
from mad import MadFile
from datetime import datetime
from whoosh import index
from whoosh.fields import Schema, ID, TEXT
from whoosh.qparser import QueryParser
import os
import re
import magic
import lxml.html
from urllib import unquote_plus
import syslog


syslog.openlog(ident='constantina')


# (Full path) Web resources and directories that Constantina reads from
ROOT_DIR = "/var/www"

# (Relative to RESOURCE DIR) Root of the Constantina files
RESOURCE_DIR = "/cwdc"

# Per-page global values are based on news items per page
NEWSITEMS = 10


# Card types, and where their data lives. 
# All card types MUST start with a unique letter of the
# alphabet, since state variables come from the first
# letter of each card type. 
CARD_PATHS = {
    'news': './news/',
  'images': './pictures/',
   'songs': './songs/',
  'quotes': './interjections/',
     'ads': './gracias/',
   'media': './embedded/',
'features': './features/',
 'heading': './headers/',
  'topics': './encyclopedia/'
}


# Both describes how many cards per page, and serves as
# the canonical list of card types designed to be
# randomly distributed on each page. TWO KEYS IN THIS
# HASH MAY NOT START WITH THE SAME FIRST LETTER!
CARD_COUNTS = {
    'news': NEWSITEMS,
  'images': int(ceil(NEWSITEMS / 3)),
   'songs': int(ceil(NEWSITEMS / 10)),
  'quotes': int(ceil(NEWSITEMS / 3)),
     'ads': int(ceil(NEWSITEMS / 10)),
   'media': int(ceil(NEWSITEMS / 8)),
'features': int(ceil(NEWSITEMS / 10)),
  'topics': 0
}


# Some state tokens represent special queries to our
# script, and shouldn't represent specific card types.
# These are permalink types, and the permalink fields
# must be underscore_delimited versions of the CARD_COUNTS
# fields should new ones be defined.
SPECIAL_STATES = {
       'xn': 'news_permalink',
       'xf': 'features_permalink',
       'xt': 'topics_permalink',
       'xs': 'search'
}


# How many cards in between each card of this type. 0 means
# we can have cards right next to each other.
CARD_SPACING = {
    'news': 0,
  'images': int(floor(NEWSITEMS / 3)),
   'songs': int(floor(NEWSITEMS / 1.5)),
  'quotes': int(floor(NEWSITEMS / 4)),
     'ads': int(floor(NEWSITEMS / 1.5)),
   'media': int(ceil(NEWSITEMS / 2)),
'features': int(ceil(NEWSITEMS / 2)),
  'topics': 0
}


# Only do opendir once per directory
DIR_INDEX = {}


# Default card values, occasionally used for checking
# to see if something has been set or not. In case of
# an error, these values will not look too obvious as 
# default-values on a public webpage.
DEFAULT = {
     'body': 'Zen-like calm.',
    'title': 'Empty Card',
     'file': 'No filename grabbed.',
     'date': 'Insert date here',
'tombstone': 'Next-page Tombstone'
}


# Directory and parameters for the search indexing
SEARCH_INDEX = {
           'dir': "./index/",
  'ignore-words': "./index/ignore-words",
'ignore-symbols': "./index/ignore-symbols"
}


# Types of cards that we both index and search for
SEARCH_CARDS = [
     'news',
 'features',
   'quotes',
]


# Types of cards we randomize in the output pages
RANDOMIZE_CARDS = [
   'images',
   'quotes',
]


# Max search results to return in a query
MAX_SEARCH_RESULTS = 200
# Max number of comma-separated values for a parameter
# This is also the max number of search terms (TODO?)
MAX_STATE_PARAMETERS = 10


class cw_cardtype:
   """
   Constantina Card Type State Tracking.

   In the cw_state class, we track the following properties per-card-type:
      - How many of each item was displayed
      - Which news or image items were displayed
         - This is condensed into a start and end range of file indices
           in each card-type data directory
      - The distance from the last-displayed item of this type to the end
        of the displayed page

   Through introspection of the CARD_COUNTS settings, we create one of these
   objects named for each card type (ctype).
   """
   def __init__(self, count, distance, spacing, start, end):
      self.count = count
      self.distance = distance
      self.spacing = spacing
      self.start = start
      self.end = end
      self.clist = []      # List of card indexes that appeared of this type


class cw_state:
   """
   Constantina Page State Object.

   This is serialized and deserialized from a string embedded in JS
   on the page itself that describes the following details:
      - How many of each item was displayed
      - Which news or image items were displayed
         - This is condensed into a range of item indexes
      - The distance from the last-displayed item of this type to the end
        of the displayed page
      - The seed number that defines the displayed random order
      - Any search strings that might have been provided in previous views
      - Whether a permalink is being viewed (feature, news, or topic page)
   It is also a cleaner interface to grab at the global configuration
   variables defined in the top of this file.
   """
   def __init__(self, state_string=None):
      self.in_state = state_string   # Track the original state string
      self.seed = None		     # The Random Seed for the page
      self.shuffled = {}             # Arrays of shuffled index lists

      # For the card types in CARD_COUNTS, create variables, i.e.
      #   state.news.distance, state.topics.spacing
      for ctype in CARD_COUNTS:
         setattr(self, ctype, cw_cardtype(
            count=CARD_COUNTS[ctype],
            distance=None,
            spacing=CARD_SPACING[ctype],
            start=None,
            end=None))

      # For permalink settings or search strings, define object fields as well
      #    Examples: self.search, self.news_permalink
      for spctype, spcfield in SPECIAL_STATES.iteritems():
         setattr(self, spcfield, None)

      # Was there an initial state string? Read it if there is
      self.__import_state(state_string)

      # If there wasn't a random seed, we better generate one :)
      if (self.seed == None):
         self.__set_random_seed()

      # Calculate consistent shuffled arrays of filetypes for the real state
      # indexes to make reference to in card selection
      for ctype in RANDOMIZE_CARDS:
         self.__shuffle_files(ctype)

      syslog.syslog("Random seed: " + str(self.seed))


   def __import_state(self, state_string):
      """Given a state variable string grabbed from the page, parse a
         parse into an object full of card-list properties. This will 
         be used to define which cards should be obtained for the page."""
      valid_tokens = {}
      last_parsed = []

      # No prior state? Nothing to worry about
      if ( state_string == None ):
         return

      # State types are the same as the first letter of each card type
      for ctype in CARD_COUNTS:
         valid_tokens[ctype[0]] = ctype

      # Special two-letter states may be processed as well
      for spctype, spcfield in SPECIAL_STATES.iteritems():
         valid_tokens[spctype] = spcfield

      # Parse each colon-separated item that matches a state type
      for token in state_string.split(':'):
         # News tokens are just a single number for the last item loaded
         if token[0] == 'n' and token[0] not in last_parsed:
            getattr(self, 'news').end = int(token[1:])
            last_parsed.append(token[0])   # Add to the parsed stack

         # Single-character tokens typically have a "start, end, and spacing" 
         # value, so we only need three items.
         elif token[0] in valid_tokens and token[0] not in last_parsed:
            # Determine ctype from introspection
            ctype = valid_tokens[token[0]]  
            item_range_dist = token[1:].split(',')[0:3]
            try:
               getattr(self, ctype).distance = int(item_range_dist.pop())
               getattr(self, ctype).start = int(item_range_dist[0])
               getattr(self, ctype).end = int(item_range_dist[1])
            except:
               continue

            last_parsed.append(token[0])   # Add to the parsed stack

         # Special two-character tokens don't denote typical state
         # Just post whatever comma-separated items we have, up to 
         # the first ten.
         elif token[0:2] in valid_tokens and token[0:2] not in last_parsed:
            try:
               item_str = unquote_plus(token[2:])
               items = item_str.split(',')[0:MAX_STATE_PARAMETERS]
            except:
               continue

            spcfield = SPECIAL_STATES[token[0:2]]
            setattr(self, spcfield, [])
            for i in items:
               getattr(self, spcfield).append(i)
            last_parsed.append(token[0:2])   # Add to the parsed stack

         # If the token can be interpreted as a float when putting 0. in front,
         # this will become our random seed for shuffling
         elif ( token.isdigit() ):
            self.__import_random_seed(token)

         else:
            pass


   # TODO: move update_state portions to their own function?
   # TODO: most of the update-state stuff is calculating distance
   def export_state(self, cards, query_terms):
      """Once all cards are read, calculate a new state variable to
         embed in the more-contents page link."""
      all_ctypes = CARD_COUNTS.keys()

      # Populate the state object, which we'll later build the
      # state_string from. Don't deal with news items yet
      for card in cards:
         # Do not proces news items in the state variable
         if ((card.ctype == 'news') or (card.ctype == 'heading')):
            continue
         # For adding into a string later, make card.num a string too
         getattr(self, card.ctype).clist.append(str(card.num))
         if ( card.ctype not in all_ctypes ):
            all_ctypes.append(card.ctype)

      # Add distance values to the end of each state_hash
      # array, as is the standard for these state tokens.
      done_distance = []
      all_ctypes.sort()


      # Terminate the loop if we either get to the bottom of the
      # array, or whether we've calculated distances for all
      # possible state types
      hidden_cards = 0   # Account for each hidden card in the distance
                         # between here and the end of the page
      news_last = 0      # Last news card seen, by index

      # Traversing backwards, find the last card of each type shown
      for i in xrange(len(cards) - 1, -1, -1):
         card = cards[i]
         if (card.ctype == 'news') and ( news_last == 0 ):
            news_last = card.num
            continue
         if (card.ctype == 'heading' ):
            # Either a tombstone card or a "now loading" card
            # Subtract one from the distance of "shown cards"
            hidden_cards = hidden_cards + 1
            continue
         if ( card.ctype in done_distance ):
            continue

         # We've now tracked this card type
         done_distance.append(card.ctype)
         done_distance.sort()

         dist = len(cards) - hidden_cards - i
         # print "=> %s dist: %d i: %d card-len: %d  eff-len: %d" % ( card.ctype, dist, i, len(self.cards), len(self.cards) - hidden_cards)
         getattr(self, card.ctype).distance = str(dist)
         # Early break once we've seen all the card types
         if ( done_distance == all_ctypes ):
            break


      # Finally, construct the state string for the next page
      seed = self.__export_random_seed()
      export_string = ''
      state_tokens = []

      for ctype in all_ctypes:
         # If no cards for this state, do not track
         if ( getattr(self, ctype).clist == [] ):
            continue

         # Track just the range of values, not the intermediaries
         # TODO TODO: this is why items repeat state. You need to track the last N actual
         # appearance items so that there's at least N entries between duplicates.
         stype = ctype[0]
         crange = getattr(self, ctype).clist
         cdist = getattr(self, ctype).distance
         crange.sort()

         item_range_dist = crange[0] + "," + crange[-1] + "," + cdist
         state_tokens.append(stype + item_range_dist)
      export_string = ":".join(state_tokens) + ":" + "n" + str(news_last) + ":" + str(seed)

      # The up-to-10 search terms come after the primary state variable,
      # letting us know that the original query was a search attempt, and that
      # future data to insert into the page should be filtered by these 
      # provided terms.
      if ( query_terms != '' ):
         export_string = export_string + ":" + "xs" + query_terms
      return export_string


   def __set_random_seed(self):
      """Return a consistent random seed for the shuffle function, so that
      between page loads we can utilize the same initial random shuffle."""
      self.seed = round(random(), 14)
      seed(self.seed)
      

   def __import_random_seed(self, num):
      """Set the return seed based on a 5-digit integer from the prior_state.
      For shuffle, this has to be a float between zero and one, but for the
      state variable it should be a N-digit number."""
      self.seed = float(str("0." + num))
      seed(self.seed)


   def __export_random_seed(self):
      """Export the random seed for adding to the state variable"""
      return str(self.seed).replace("0.", "")


   def __shuffle_files(self, ctype):
      """Take a card type, and create a shuffle array where we can preserve
      normal page-state numbering, using those page-state values as indexes
      into a shuffled list of files."""
      file_count = len(opendir(ctype))
      self.shuffled[ctype] = range(0, file_count)
      syslog.syslog("Unshuffled " + ctype + ": " + str(self.shuffled[ctype]))
      shuffle(self.shuffled[ctype])
      syslog.syslog("    Random " + ctype + ": " + str(self.shuffled[ctype]))



class cw_page:
   """
   Constantina Page Object.
   
   Constantina page returns the latest N news items, along with 
   floor(N/3) random images and floor(N/10) random features. For every 
   page output, a state variable encodes the page's displayed contents.
   When the more-content footer link is clicked, this state variable
   describes what has already been shown so that new randomly-
   inserted content is not a duplicate that was previously shown. 
   """ 

   def __init__(self, in_state=None):
      """If there was a previous state, construct array of cards for
         the state without loading any files from disk. Then, load a
         new set of cards for addition to the page, and write a new
         state variable for the next AJAX load"""
      self.cur_len = 0
      self.cards = []
      self.state = cw_state(in_state)
      self.out_state = ''

      self.search_results = ''
      self.query_terms = ''   # Use this locally, in case we happen not to create a search object

      if ( self.state.in_state == None ):
         # Create a new page of randomly-assorted images and quotes,
         # along with reverse-time-order News items
         self.__get_cards()
         self.__distribute_cards()
         self.cards.insert(0, cw_card('heading', 'basic', grab_body=True))

         if ( len(self.cards) - self.cur_len > NEWSITEMS ):
            # Add a hidden card to trigger loading more data when reached
            self.cards.insert(len(self.cards) - 7, cw_card('heading', 'scrollstone', grab_body=True))
            # Finally, add the "next page" tombstone to load more content
            self.cards.append(cw_card('heading', 'tombstone', grab_body=True))
         else:
            self.cards.append(cw_card('heading', 'bottom', grab_body=True))

      elif (( self.state.news_permalink != None ) or 
            ( self.state.features_permalink != None ) or 
            ( self.state.topics_permalink != None )):
         # This is a permalink page request. For these, use a
         # special footer card (just a header card placed at 
         # the bottom of the page).
         self.__get_permalink_card()
         self.cards.append(cw_card('heading', 'footer', grab_body=True, permalink=True))

      elif ( self.state.search != None ):
         # Return search results based on the subsequent comma-separated list,
         # parsed by __import_state into self.state.search.
         # TODO: Tokenize all search parameters and remove non-alphanum characters
         # other than plus. All input-commas become pluses
         self.search_results = cw_search(self.state.search)
         self.query_terms = self.search_results.query_string
         self.__get_search_result_cards()
         self.__distribute_cards()
        
         # TODO: Implement search result paging
         if ( len(self.cards) > 0 ):
            self.cards.append(cw_card('heading', 'bottom', grab_body=True))

      else:
         # Get new cards for an existing page, tracking what the
         # previous page's state variable was in creating the list 
         # of cards to display.
         self.__get_prior_cards()
         self.__get_cards()
         self.__distribute_cards()

         if ( len(self.cards) - self.cur_len > NEWSITEMS ): 
            # Add a hidden card to trigger loading more data when reached
            self.cards.insert(len(self.cards) - 7, cw_card('heading', 'scrollstone', grab_body=True))
            # Finally, add the "next page" tombstone to load more content
            self.cards.append(cw_card('heading', 'tombstone', grab_body=True))
         else:
            self.cards.append(cw_card('heading', 'bottom', grab_body=True))

      # Once we've constructed the new card list, update the page
      # state for insertion, for the "next_page" link.
      self.out_state = self.state.export_state(self.cards, self.query_terms)
      syslog.syslog("Initial state: " + str(self.state.in_state))
      syslog.syslog("To-load state: " + str(self.out_state))
      

   def __get_cards(self):
      """
      Get a page's worth of news updates. Include images and
      features and other details. 
      """
      # for i in xrange(0, len(self.cards)):
      #    print "%s %s %s" % ( i, self.cards[i].ctype, self.cards[i].title )
      # print self.cur_len   
 
      # Anything with rules for cards per page, start adding them.
      # Do not grab full data for all but the most recent cards!
      # For older cards, just track their metadata
      for ctype in CARD_COUNTS:
         # No topic cards unless they're search results, and no card types
         # that have no historical values in the last page
         if ( CARD_COUNTS[ctype] == 0 ):
            continue
         # No data and it's not the first page? Skip this type
         if ( getattr(self.state, ctype).end == None ) and ( self.state.in_state != None ):
            continue

         # Grab the cnum of the last inserted thing of this type
         # and then open the next one
         # If we didn't open anyting last time, start at the beginning
         if ( self.state.in_state == None ):
            start = 0
         # If these are previous items, calculate how many were on previous pages
         else:
            start = int(getattr(self.state, ctype).end) + 1

         for i in xrange(start, start + CARD_COUNTS[ctype]):
            card = cw_card(ctype, i, state=self.state, grab_body=True)
            # Don't include cards that failed to load content
            if ( card.topics != [] ):
               self.cards.append(card)
               # print "%s %s %s" % ( len(self.cards), ctype, self.cards[-1].title )


   def __get_search_result_cards(self):
      """
      Get all available search updates. Include only the sorted, arranged list
      of search results that we wanted, and make sure all result cards are expanded
      to their fully-readable size.
      """
      # Treat topics cards special. If there's an exact match between the name
      # of an encyclopedia entry and the search query, return that as the first
      # page of the results. TOPIC articles must be filenamed lowercase!!
      # HOWEVER if we're beyond the first page of search results, don't add
      # the encyclopedia page again! Use image count as a heuristic for page count.
      if ( self.query_terms.lower() in opendir('topics')):
         encyclopedia = cw_card('topics', self.query_terms.lower(), state=self.state, grab_body=True, search_result=True)
         self.cards.append(encyclopedia)

      # Other types of search results come afterwards
      for ctype in SEARCH_CARDS:
         # Manage the encyclopedia cards separately
         if ( ctype == 'topics' ):
            continue

         start = 0
         end_dist = len(self.search_results.hits[ctype])
         # No results for this search type
         if ( end_dist == 0 ):
            continue

         for j in xrange(start, end_dist):
            grab_file = self.search_results.hits[ctype][j]
            # If the hits[ctype][j] is a file name, figure out which Nth file this is
            if ( grab_file.isdigit() == False ):
               # Most dirlists are in reverse-time order. If files aren't datenames,
               # put this in normal order.
               DIR_INDEX[ctype].reverse()
               for k in xrange(0, len(DIR_INDEX[ctype])):
                  syslog.syslog("compare:" + grab_file + "==" + DIR_INDEX[ctype][k])
                  if DIR_INDEX[ctype][k] == grab_file:
                     grab_file = k
                     break
               DIR_INDEX[ctype].reverse()   # Put the list back the way it was

            card = cw_card(ctype, grab_file, state=self.state, grab_body=True, search_result=True)
            # News articles without topic strings won't load. Other card types that
            # don't have embedded topics will load just fine.
            if ( card.topics != [] ) or ( ctype == 'quotes' ) or ( ctype == 'topics' ):
               self.cards.append(card)
               # print "%s %s %s" % ( len(self.cards), ctype, self.cards[-1].title )


   def __get_permalink_card(self):
      """Given a utime or card filename, return a pre-constructed
         permalink page of that type."""
      for spctype, spcfield in SPECIAL_STATES.iteritems():
         if ( getattr(self.state, spcfield) != None ):
            cnum = str(getattr(self.state, spcfield)[0])
            # Insert a card after the first heading
            ctype = spcfield.split("_")[0]
            self.cards.append(cw_card(ctype, cnum, grab_body=True, permalink=True))
      

   def __get_prior_cards(self):
      """Describe all prior cards based on the state object
         without opening any files for contents. This is used to
         guarantee that new random selections are not repeats of
         earlier pages. 

         Since the previous state variable omits description of
         precise card ordering, the cardlist we construct only
         needs to represent what would have been shown. However,
         the FINAL state.ctype describes the distance from the
         current page for that card type.

         Achieve the proper estimate of the previously displayed
         contents by distributing news articles such that the
         card-type distances are properly represented."""
      news_items = int(self.state.news.end)

      # Then add the appropriate page count's worth of news
      for n in xrange(0, news_items):
         self.cards.append(cw_card('news', n, grab_body=False))

      # Now, for each card type, go back state.ctype.distance 
      # and insert the run of that card type.
      # Guarantees the previous number of items on the page is
      # accurate, while not caring about where on the previous
      # pages those images might have been. It also preserves
      # the ordering of how those items appeared on the prev
      # page, which is important for once we've generated all
      # of this page's content and need to write a new state
      # variable based on the current list of cards.
      for ctype in CARD_COUNTS:
         if ( len(getattr(self.state, ctype).clist) == 0 ):
            continue
         dist = getattr(self.state, ctype).distance
         put = len(self.cards) - 1 - int(dist)
         for cnum in getattr(self.state, ctype).clist:
            self.cards.insert(put, cw_card(ctype, cnum, grab_body=False))

      # Current length should properly track the starting point
      # of where we begin adding new cards to the page, not just 
      # tracking the old ones.
      self.cur_len = len(self.cards)


   def __last_item_per_type(self):
      """Given the largest spacing value, determine distance between
         our starting card on this page and a card of equal type that
         appeared on the previous page."""
      # If this is the first page, there's no distance to
      # items on the last page. 
      last_dist = {}
      if ( self.state.in_state == None ):
         for ctype in CARD_SPACING:
            last_dist[ctype] = 0
         return last_dist

      # Otherwise go back in our cardlist and determine
      # the distances between current cards and the last
      # card of each type.
      lb = self.cur_len - max(CARD_SPACING.values())
      for card in self.cards[lb::]:
         last_dist[card.ctype] = self.cur_len - lb

      # If no cards of a particular type, set dist to zero
      for ctype in CARD_SPACING.keys():
         if ctype not in last_dist:
            last_dist[ctype] = 0

      return last_dist


   def __distribute_cards(self):
      """
      Distribute cards evenly in the array in order to 
      describe the ordering of a page. Use slight random jitter
      in placement to guarantee fresh page ordering every time
      """
      total = len(self.cards)
      lstop = self.cur_len 
      p_dist = total - lstop
      # On this page and the last, the most recent card seen
      c_lastcard = self.__last_item_per_type()   # Index nums
      # Distance from last ctype'd card on the previous page
      c_dist = {}
      # "hold-aside" hash to help shuffle the main run of cards
      c_redist = {}
      # non-redist set (news articles)
      c_nodist = {}      

      for ctype in CARD_SPACING:
         # Spacing rules from the last page. Subtract the distance from
         # the end of the previous page. For all other cards, follow the
         # strict CARD_SPACING rules, plus jitter
         if ( lstop - c_lastcard[ctype] >= CARD_SPACING[ctype] ):
            c_dist[ctype] = 0
         elif (( lstop == 0 ) and ( c_lastcard[ctype] == 0 )):
            c_dist[ctype] = 0
         else:
            c_dist[ctype] = CARD_SPACING[ctype] - (lstop - c_lastcard[ctype])
         # print "------ ctype %s   spacing %d   c_dist %d   c_lsatcard %d   lstop %d" % ( ctype, CARD_SPACING[ctype], c_dist[ctype], c_lastcard[ctype], lstop)
         c_redist[ctype] = []
         c_nodist[ctype] = []

      # Make arrays of each card type, so we can shuffle,
      # jitter, and reinsert them later.
      for i in xrange(lstop, total):
         ctype = self.cards[i].ctype
         # News cards don't get redistributed, and cards that we 
         # already adjusted don't get moved either
         if ( ctype == 'news' ) or ( ctype == 'topics'):
            c_nodist[ctype].append(self.cards[i])
         else:
            # Take all non-news cards out
            c_redist[ctype].append(self.cards[i])

      # Erase this snippet of the cards array, so we can reconstruct
      # it manually. Keep popping from the point where we snipped things
      for i in xrange(lstop, total):
         self.cards.pop(lstop)

      # Now, add the news cards back
      for j in xrange(0, len(c_nodist['news'])):
         self.cards.insert(lstop + j, c_nodist['news'][j])

      # Now, for each type of non-news card, figure out the starting point
      # where cards can be inserted, follow the spacing rules, and redist
      # them throughout the cards.
      for ctype in c_redist.keys():
         if ( c_redist[ctype] == [] ):
            continue   # Empty

         # Max distance between cards of this type on a page
         norm_dist = CARD_SPACING[ctype]
         # For spacing purposes, page starts at the earliest page we can
         # put a card on this page, w/o being too close to a same-type
         # card on the previous page. This shortens the effective page dist
	 effective_pdist = p_dist - c_dist[ctype]
         max_dist = effective_pdist
         if ( CARD_COUNTS[ctype] >= 1 ):
            max_dist = floor(effective_pdist / CARD_COUNTS[ctype])

         # If less cards on the page then expected, degrade
         if ( max_dist < norm_dist ):
            max_dist = norm_dist
            norm_dist = max_dist - 1

         # Take the cards for this type and re-add them to the cards list
         # jitter = randint(c_dist[ctype], norm_dist)
         seen_type = {}

         # Start with an initial shorter distance for shuffling
         start_jrange = c_dist[ctype]
         end_jrange = norm_dist 

         # Add back the cards
         for k in xrange(0, len(c_redist[ctype])):
            if ( ctype not in seen_type ):   # If first page AND not seen before, add them early
               if ( start_jrange >= end_jrange ):   # Not many items?
                  jitter = 1
               else:
                  jitter = randint(start_jrange, end_jrange)
               ins_index = lstop + c_dist[ctype] + jitter
               seen_type[ctype] = True
            else:   # Now we've seen cards, start spacing
               start_jrange = norm_dist
               end_jrange = max_dist
               if ( start_jrange >= end_jrange ):   # Not many items?
                  jitter = 1
               else:
                  jitter = randint(start_jrange, end_jrange)
               ins_index = ins_index + jitter

            card = c_redist[ctype][k]
            self.cards.insert(ins_index, card)
            # print "ctype %s   ct-cnt %d   len %d   ins_index %d   jitter %d" % ( ctype, len(c_redist[ctype]), len(self.cards), ins_index, jitter)

      # Lastly, add the topics cards back
      for j in xrange(0, len(c_nodist['topics'])):
         self.cards.insert(lstop + j, c_nodist['topics'][j])


class cw_card:
   """
   Constantina is a single-page layout consisting of cards. For now
   it is also a single-column layout. A card may contain a news item,
   an image, a feature, a header/footer, an ad, or an embedded media 
   link. We track whether the image or link may be duplicated within
   the card, as well as what its page index and type are.
   """

   def __init__(self, ctype, num, state=False, grab_body=True, permalink=False, search_result=False):
      self.title = DEFAULT['title']
      self.topics = []
      self.body = DEFAULT['body']
      self.ctype = ctype
      # Request either the Nth entry of this type, or a specific utime/date
      self.num = num
      # If we need to access data from the state object, for card shuffling
      self.state = state
      self.songs = []
      self.cfile = DEFAULT['file']
      self.cdate = DEFAULT['date']
      self.permalink = permalink
      self.search_result = search_result
      # Don't hit the filesystem if we're just tracking which cards have
      # been previously opened (cw_page.__get_previous_cards)
      if ( grab_body == True ):
         self.cfile = self.__openfile()


   def __openfile(self):
      """Either open the Nth file or the utime-named file in the dir,
         populate the object, and return the name of the opened file"""
      type_files = opendir(self.ctype)

      # Find the utime value in the array if the number given isn't an array index.
      # If we're inserting cards into an active page, the state variable will be
      # given, and should be represented by a shuffled value.
      if ( self.ctype in RANDOMIZE_CARDS ) and ( self.state != False ):
         cycle = len(self.state.shuffled[self.ctype])
         syslog.syslog("open file: " + str(self.num) + "/" + str(cycle))
         which_file = self.state.shuffled[self.ctype][self.num % cycle]
      else:
         which_file = self.num

      if which_file >= len(type_files):
         if ( self.num in type_files ):
            which_file = type_files.index(self.num)
            self.num = which_file   # Don't save the filename as the number
         elif ( self.ctype in RANDOMIZE_CARDS ): 
            # Some types should support looping over the available
            # content. Add those to this clause. To make the monotonic
            # content appearances more evenly distributed and less
            # obviously in sequence, jitter the next image count in
            # a consistent positive direction.
            rand_travel = 1
            while (( rand_travel < 2 ) and 
                   ( CARD_COUNTS[self.ctype] % rand_travel == 0 ) and 
                   ( CARD_COUNTS[self.ctype] > 3 )):
               # Without looping, try to cycle the array of possible inserts
               # in a unique way on every page load
               rand_travel = randint(2, CARD_COUNTS[self.ctype])
            which_file = ( self.num + rand_travel ) % len(type_files)
         else:
            return "nofile"

      return self.__interpretfile(type_files[which_file])


   def __songfiles(self):
      """Create an array of song objects for this card"""
      for songpath in self.body.splitlines():
         songpath = CARD_PATHS['songs'] + songpath
         self.songs.append(cw_song(songpath))


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
      fpath = CARD_PATHS[self.ctype] + thisfile

      try:
         with open(fpath, 'r') as cfile:
            ftype = magi.from_file(fpath)
            # News entries or features are processed the same way
            if (( "text" in ftype ) and 
                (( CARD_PATHS['news'] in cfile.name ) or
                 ( CARD_PATHS['heading'] in cfile.name ) or 
                 ( CARD_PATHS['quotes'] in cfile.name ) or 
                 ( CARD_PATHS['topics'] in cfile.name ) or 
                 ( CARD_PATHS['features'] in cfile.name ))):
               self.title = cfile.readline().replace("\n", "")
               rawtopics = cfile.readline().replace("\n", "")
               for item in rawtopics.split(', '):
                  self.topics.append(item)
               self.body = cfile.read()
   
            # Multiple-song playlists
            if (( "text" in ftype ) and
                ( CARD_PATHS['songs'] in cfile.name )):
               self.title = fpath
               self.topics.append("Song Playlist")
               self.body = cfile.read()
               self.__songfiles()   # Read song metadata
   
            # Single-image cards
            if ((( "jpeg" in ftype ) or ( "png" in ftype)) and 
                 ( CARD_PATHS['images'] in cfile.name )):
               # TODO: alt/img metadata
               self.title = fpath
               self.topics.append("Images")
               self.body = fpath
   
            # Single-song orphan cards
            if ((( "mpeg" in ftype ) and ( "layer iii" in ftype)) and
                 ( CARD_PATHS['songs'] in cfile.name )):
               self.title = fpath      # TODO: filename from title
               self.topics.append("Songs")   # TODO: include the album
               self.body = fpath
               self.__songfiles()   # Read song metadata      
   
         # If the filename is in unix-time format, track the creation date
         if ( thisfile.isdigit() ):
            if ( int(thisfile) > 1141161200 ):
               self.cdate = datetime.fromtimestamp(int(thisfile)).strftime("%B %-d, %Y") 
         else:
            fnmtime = os.path.getmtime(fpath)
            self.cdate = datetime.fromtimestamp(int(fnmtime)).strftime("%B %-d, %Y")

         file.close(cfile)

      except:   # File got moved in between dirlist caching and us reading it
         return DEFAULT['file']

      return CARD_PATHS[self.ctype] + thisfile



class cw_search:
   """Constantina search object -- anything input into the search bar
   will run through the data managed by this object and the Whoosh index.
   News objects and Features will both be indexed, along with their last- 
   modified date at the time of indexing.

   The indexes are updated whenever someone starts a search, and there's
   been a new feature or news item added since the previous search. File
   modifications in the news/features directory will also trigger reindex
   for those updated news/feature items.

   We only index non-pointless words, so there's a ignore-index list. This
   prevents pointless queries to the indexing system, and keeps the index
   file smaller and quicker to search. Prior to index insertion, an 
   ignore-symbols list will parse text and remove things like punctuation
   and equals-signs.

   Finally, there is an "index-tree" list where if specific search terms
   are queried, all related terms are pulled in as well. If the user requests
   the related phrases can be turned off."""
   def __init__(self, unsafe_query_terms):
      # List of symbols to filter out in the unsafe input
      self.ignore_symbols = []
      # Regex of words that won't be indexed
      self.ignore_words = ''
      # After processing unsafe_query, save it in the object
      # Assume we're searching for all terms, unless separated by pluses
      self.query_string = ''
      # The contents of the last file we read
      self.content = ''
      # Notes on what was searched for. This will either be an error
      # message, or provide context on the search results shown.
      # Array of ctypes, each with an array of filename hits
      self.hits = {}

      # Whoosh object defaults
      self.schema = '' 
      self.index = ''
      self.query = ''
      self.parser =''
      self.searcher = ''
      self.results = ''

      # Define the indexing schema. Include the mtime to track updated 
      # content in the backend, ctype so that we can manage the distribution
      # of returned search results similar to the normal pages, and the 
      # filename itself as a unique identifier (most filenames are utimes).
      self.schema = Schema(file=ID(stored=True, unique=True), ctype=ID(stored=True), mtime=ID(stored=True), content=TEXT)

      # If index doesn't exist, create it
      if ( index.exists_in(SEARCH_INDEX['dir'])):
         self.index = index.open_dir(SEARCH_INDEX['dir'])
         # print "Index exists"
      else:
         self.index = index.create_in(SEARCH_INDEX['dir'], schema=self.schema)
         # print "Index not found -- creating one"
      # Prepare for query searching (mtime update, search strings)
      self.searcher = self.index.searcher()

      for ctype in SEARCH_CARDS:
         # Prior to processing input, prepare the results arrays.
         # Other functions will expect this to exist regardless.
         self.hits[ctype] = []

      # If the query string is null after processing, don't do anything else.
      # Feed our input as a space-delimited set of terms. NOTE that we limit
      # this in the __import_state function in cw_state.
      if not ( self.__process_input(' '.join(unsafe_query_terms))):
         return

      for ctype in SEARCH_CARDS:
         # Now we have good safe input, but we don't know if our index is 
         # up-to-date or not. If have changed since their last-modified date, 
         # reindex all the modified files
         self.__add_ctype_to_index(ctype)


      # TODO: Prior to searching, __parse_input to allow union searches
      # with "word1 + word2" or negative searches (word1 - word2)
      # TODO: Save these results to query_string somehow

      # Return only up to CARD_COUNT items per page for each type of returned
      # search result query. We calculate the max sum of all returned items,
      # and then we'll later determine which of these results we'll display
      # on the returned search results page.
      self.__search_index()
      self.__sort_search_results() 


   def __process_input(self, unsafe_input, returning="query"):
      """Squeeze out ignore-characters, and modify the incoming query
      string to not search for things we don't index. This can set either
      self.query (search processing) or self.content (adding to index).
      Return values:
         0: word list and symbol erasing ate all the search terms
         1: valid query 
      """
      # Make a or-regex of all the words in the wordlist
      if ( self.ignore_words == '' ):
         with open(SEARCH_INDEX['ignore-words'], 'r') as wfile:
            words = wfile.read().splitlines()
            remove = '|'.join(words)
            self.ignore_words = re.compile(r'\b('+remove+r')\b', flags=re.IGNORECASE)

      # Then remove them from whatever input we're processing
      safe_input = self.ignore_words.sub("", unsafe_input)
      if ( safe_input == '' ):
         return 0

      # Get rid of symbol instances in whatever input we're processing
      # Note this only works on ASCII symbol characters, not the special
      # double-quote characters &ldquo; and &rdquo;, as well as other
      # lxml.html converted &-escaped HTML characters
      if ( self.ignore_symbols == '' ):
         with open(SEARCH_INDEX['ignore-symbols'], 'r') as sfile:
            for character in sfile.read().splitlines():
               self.ignore_symbols.push(character)
               safe_input = safe_input.replace(character, " ")               
      else:
         for character in self.ignore_symbols:
            safe_input = safe_input.replace(character, " ")               

      # Did we sanitize a query, or a round of content? Infer by what 
      # we're setting in the object itself.
      if (safe_input != '' ):
         if ( returning == "query" ):
            self.query_string = safe_input
         else:
            self.content = safe_input
         return 1

      else:
         return 0


   def __add_file_to_index(self, fnmtime, filename, ctype="news"):
      """Reads in a file, processes it into lines, lxml.html grabs 
      text out of the tags, processes the input to remove banal words
      and symbols, and then adds it to the index."""
      # Enable writing to our chosen index
      # TODO: Should we only open the writer once, in a different scope?
      writer = self.index.writer()

      with open(CARD_PATHS[ctype] + filename, 'r') as indexfh:
         body = ""
         lines = indexfh.read().splitlines()
         unrolled = unroll_newlines(lines)
         for line in unrolled:
            e = lxml.html.fromstring(line)
            if ( e.tag == 'p' ):
               body += e.text_content() + " "
         self.__process_input(body, returning="contents")
         # Update wraps add if the document hasn't been inserted, and 
         # replaces current indexed data if it has been inserted. This
         # requires the file parameter to be set "unique" in the Schema
         writer.update_document(file=unicode(filename), ctype=unicode(ctype), mtime=unicode(fnmtime), content=unicode(self.content))

      # Finish by commiting the updates
      writer.commit()


   def __add_ctype_to_index(self, ctype):
      """Take a file type, list all the files there, and add all the
      body contents to the index."""
      # Make sure the DIR_INDEX is populated
      opendir(ctype)

      for filename in DIR_INDEX[ctype]:
         try:
            fnmtime = int(os.path.getmtime(CARD_PATHS[ctype] + filename))
         except:
            return   # File has been removed, nothing to index

         lastmtime = ''
         try: 
            lastmtime = int(float(self.searcher.document(file=unicode(filename))['mtime']))
         except:
            lastmtime = 0
         # If small revisions were made after the fact, the indexes won't
         # be accurate unless we reindex this file now
         if ( lastmtime < fnmtime ):
            # print "%s was updated or not in the index. Consistentifying..." % filename
            self.__add_file_to_index(fnmtime, filename, ctype)


   def __search_index(self, count=MAX_SEARCH_RESULTS):
      """Given a list of search paramters, look for any of them in the 
      indexes. For now don't return more than 200 hits"""
      self.parser = QueryParser("content", self.schema)
      self.query = self.parser.parse(unicode(self.query_string))
      self.results = self.searcher.search(self.query, limit=count)

      # Just want the utime filenames themselves? Here they are, in 
      # reverse-utime order just like we want for insert into the page
      # print self.results[0:]
      for i in xrange(0, len(self.results)):
         ctype = self.results[i]['ctype']
         self.hits[ctype].append(self.results[i]['file'])


   def __sort_search_results(self):
      """Sort the search results in reverse-time order. For the randomly-
      shuffled elements, reverse-lexicographic sorting shouldn't matter"""
      for ctype in SEARCH_CARDS:
         self.hits[ctype].sort()
         self.hits[ctype].reverse()



class cw_song:
   """Basic grouping of song-related properties with a filename.
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



def remove_future(dirlisting):
   """For any files named after a Unix timestamp, don't include the
   files in a directory listing if the timestamp-name is in the future.
   Assumes the dirlisting is already sorted in reverse order!"""
   for testpath in dirlisting:
      date = datetime.fromtimestamp(int(testpath)).strftime("%s") 
      current = datetime.strftime(datetime.now(), "%s")
      if ( date > current ):
         dirlisting.remove(testpath)
      else:
         break

   return dirlisting


def opendir(ctype):
   """Return either cached directory information or open a dir and
   list all the files therein. Used for both searching and for the
   card reading functions, so we manage it outside those."""
   directory = CARD_PATHS[ctype]

   # If the directory wasn't previously cached
   if ( ctype not in DIR_INDEX.keys() ):
      # Default value. If no files, keep the empty array
      DIR_INDEX[ctype] = []

      dirlisting = os.listdir(directory)
      if ( dirlisting == [] ):
         return DIR_INDEX[ctype]

      # Any newly-generated list of paths should be weeded out
      # so that subdirectories don't get fopen'ed later
      for testpath in dirlisting:
         if os.path.isfile(os.path.join(directory, testpath)):
            DIR_INDEX[ctype].append(testpath)

      # Sort the output. Most directories should use
      # utimes for their filenames, which sort nicely. Use 
      # reversed array for newest-first utime files
      DIR_INDEX[ctype].sort()
      DIR_INDEX[ctype].reverse()

      # For news items, remove any items newer than the current time
      if ( ctype == "news" ):
         DIR_INDEX[ctype] = remove_future(DIR_INDEX[ctype])

   return DIR_INDEX[ctype]


def unroll_newlines(body_lines):
   """Given lines of text, remove all newlines that occur within an
   HTML element. Anything that we parse with lxml.html will inevitably
   start trying to use this utility function."""
   processed_lines = []
   pro_line = ""
   i = 0

   # For processing purposes, if no p tag at the beginning of a line, combine
   # it with the next line. This guarantees one HTML tag per line for the 
   # later per-element processing
   while ( i < len(body_lines)):
      # Add a space back to the end of each line so
      # they don't clump together when reconstructed
      this_line = body_lines[i].strip() + " "
      # Don't parse empty or whitespace lines
      if (( this_line.isspace() ) or ( this_line == '' )):
         i = i + 1
         continue

      if ( this_line.find('<p>') == 0 ):
         if not (( pro_line.isspace() ) or ( pro_line == '' )):
            processed_lines.append(pro_line)
         pro_line = this_line
      elif ( this_line.find('<img') != -1 ):
         if not (( pro_line.isspace() ) or ( pro_line == '' )):
           processed_lines.append(pro_line)
         pro_line = this_line
      else:
         pro_line += this_line
      i = i + 1

   processed_lines.append(pro_line)
   return processed_lines


def count_ptags(processed_lines):
   """ Count all the <p> tags. If there's less than three paragraphs, the
   create_card logic may opt to disable the card's "Read More" link."""
   ptags = 0
   for line in processed_lines: 
      if line.find('<p>') >= 0:
         ptags = ptags + 1
   return ptags


def create_simplecard(card, next_state):
   """Simple cards with only basic text and images are drawn here.
   This includes all headingCards and quotesCards, but possibly
   others as well. Do not apply any special logic to these cards -- 
   just get them drawn, whatever tags they might contain."""
   anchor = card.cfile.split('/').pop()

   output = ""
   output += """<div class="%sCard" id="%s">\n""" % ( card.ctype, anchor )

   body_lines = card.body.splitlines()
   processed_lines = unroll_newlines(body_lines)

   for line in processed_lines:
      output += line + "\n"

   # For special tombstone cards, insert the state as non-visible text
   if ( card.title == DEFAULT['tombstone'] ):
      output += """\n<p id="state">%s</p>""" % next_state

   output += """</div>\n"""
   return output


def create_textcard(card):
   """All news and features are drawn here. For condensing content, 
   wrap any nested image inside a "read more" bracket that will appear 
   after the 1st paragraph of text. Hide images behind this link too.

   Fill out the next/previous type links based on #anchors done with a
   descending number. If the next page of content isn't loaded, make
   the link also load the next page of content before the anchor tag
   is followed.
   """
   # TODO: VET title and topics for reasonable size restrictions
   topics = ", ".join(card.topics)
   anchor = card.cfile.split('/').pop()

   # The body of a text card consists of paragraphs of text, possibly
   # with a starting image tag. Wrap all tags other than the first 
   # paragraph tag with a "Expand" style that will keep that text
   # properly hidden. Then, after the end of the first paragraph, add
   # a "Read More" link for expanding the other hidden items.

   output = ""
   output += """<div class="%sCard" id="%s">\n""" % ( card.ctype, anchor )
   output += """   <div class="cardTitle">\n"""
   if ( card.permalink == True ):
      output += """      <h2>%s</h2>\n""" % card.title
      output += """      <p class="subject">%s</p>\n""" % card.cdate
   else:
      output += """      <h2><a href="#%s" onclick="cardToggle('%s');">%s</a></h2>\n""" % ( anchor, anchor, card.title )
      output += """      <p class="subject">%s</p>\n""" % topics
   output += """   </div>\n"""

   passed = {}
   body_lines = card.body.splitlines()
   processed_lines = unroll_newlines(body_lines)
   first_line = processed_lines[0]

   # Count all the <p> tags. If there's less than three paragraphs, don't do the
   # "Read More" logic for that item.
   ptags = count_ptags(processed_lines)

   for line in processed_lines:
      # Parsing the whole page only works for full HTML pages
      e = lxml.html.fromstring(line)
      if ( e.tag == 'img' ):
         if (( line == first_line ) and ( 'img' not in passed )):
            # Check image size. If it's the first line in the body and
            # it's relatively small, display with the first paragraph.
            # Add the dot in front to let the URIs be absolute, but the
            # Python directories be relative to CWD
            img = Image.open("." + e.attrib['src'])
            # TODO: am I really an image? Have a bg script tell you
            if (( img.size[0] > 300 ) and ( img.size[1] > 220 ) and 
                ( card.permalink == False ) and (card.search_result == False ) and
                ( ptags >= 3 )):
               e.attrib.update({"id": "imgExpand" })
         elif (( ptags >= 3 ) and ( card.permalink == False ) and
               ( card.search_result == False )):
            # Add a showExtend tag to hide it 
            e.attrib.update({"id": "imgExpand" })
         else: 
            pass

         # Track that we saw an img tag, and write the tag out
         output += lxml.html.tostring(e)
         passed.update({'img': True})
   
      elif ( e.tag == 'p' ):
         # If further than the first paragraph, write output
         if ( 'p' in passed ): 
            output += lxml.html.tostring(e)
         # If more than three paragraphs, and it's a news entry,
         # and if the paragraph isn't a cute typography exercise...
         # start hiding extra paragraphs from view
         elif ( len(e.text_content()) < 5 ):
            output += lxml.html.tostring(e)
            continue   # Don't mark as passed yet

         elif (( ptags >= 3 ) and ( card.permalink == False ) and
               ( card.search_result == False )):
            # First <p> is OK, but follow it with a (Read More) link, and a 
            # div with showExtend that hides all the other elements
            read_more = """ <a href="#%s" class="showShort" onclick="cardToggle('%s');">(Read More...)</a>""" % ( anchor, anchor )
            prep = lxml.html.tostring(e)
            output += prep.replace('</p>', read_more + '</p>')
            output += """<div class="divExpand">\n"""

         else:
            output += lxml.html.tostring(e)
         
         # Track that we saw an img tag, and write the tag out
         passed.update({'p': True})

      else:
         # pass all other tags unmodified
         output += line + "\n"

   # End loop. now close the showExtend div if we 
   # added it earlier during tag processing
   if (( ptags >= 3 ) and ( card.permalink == False ) and
       ( card.search_result == False )):
      output += """   </div>\n"""

   # And close the textcard
   permanchor = RESOURCE_DIR + "/?x" + card.ctype[0] + anchor

   if ( card.permalink == False ):
      output += """   <div class="cardFooter">\n"""
      output += """      <div class="bottom">\n"""
      output += """         <p class="cardNav"><a href="%s">Permalink</a></p>\n""" % permanchor
      output += """         <p class="postDate">%s</p>\n""" % card.cdate
      output += """      </div>\n"""
      output += """   </div>\n"""

   output += """</div>\n"""
   return output


def create_imagecard(card):
   """Pure image frames should be generated and inserted roughly
   3 per page of news items. Duplicates of images are OK, as long
   as we need to keep adding eye candy to the page.
   """
   anchor = card.cfile.split('/')[2]
   # Get URI absolute path out of a Python relative path
   uripath = "/" + "/".join(card.cfile.split('/')[1:])

   output = ""
   output += """<div class="imageCard" id="%s">\n""" % anchor
   output += """   <img src="%s" />\n""" % uripath
   output += """</div>\n"""
   return output



def create_songcard(card):
   """Song cards appear in two varieties -- one is made from a
   single MP3 file, and appears as a focal point. The other type
   appears as M3U playlist files, and result in multiple songs 
   appearing in a single card list. The M3U version should be 
   randomly sorted, and ideally has no more than 6 songs.
   """

   output = ""
   output += """<div class="songCard">"""
   for song in card.songs:
      # Songs DIR can only be TLD, followed by album, and then songname
      uripath = "/" + "/".join(song.songfile.split("/")[-3:])

      output += """   <div class="cell">"""
      output += """      <p class="songName">%s</p>""" % song.songtitle
      output += """      <a href="%s">MP3 &darr; %s </a>""" % ( uripath, song.songlength )
      output += """   </div>"""
   
   output += """</div>"""
   return output


def create_page(page):
   """Given a cw_page object, draw all the cards with content in
   them, Each card type has unique things it must do to process
   the data before it's drawn to screen.
   
   If a state is provided, return JSON-formatted data ready for 
   insertion into the DOM. Otherwise, return the initial HTML.
   This is done with decorators for each of the card functions
   """
   output = ""
   total = len(page.cards)
   start_point = page.cur_len
   # print "%d %d" % ( page.cur_len, total )

   for i in xrange(start_point, total):
      if (( page.cards[i].ctype == "news" ) or
          ( page.cards[i].ctype == "topics" ) or
          ( page.cards[i].ctype == "features" )):
         output += create_textcard(page.cards[i])

      if (( page.cards[i].ctype == "quotes" ) or
          ( page.cards[i].ctype == "heading" )):
         output += create_simplecard(page.cards[i], page.out_state)

      if ( page.cards[i].ctype == "images" ):
         output += create_imagecard(page.cards[i])

      if ( page.cards[i].ctype == "songs" ):
         output += create_songcard(page.cards[i])

   return output


def application(env, start_response):
   """
   uwsgi entry point and main Constantina application.

   If no previous state is given, assume we're returning
   HTML for a browser to render. Include the first page
   worth of card DIVs, and embed the state into the next-
   page link at the bottom.

   If a state is given, assume we're inserting new divs
   into the page, and return JSON for the client-side 
   javascript to render into the page.

   If a special state is given (such as for a permalink),
   generate a special randomized page just for that link,
   with an introduction, footers, an image, and more...
   """
   os.chdir(ROOT_DIR + RESOURCE_DIR)
   in_state = os.environ.get('QUERY_STRING')
   if ( in_state != None ) and ( in_state != '' ):
      # Truncate state variable at 1024 characters
      in_state = in_state[0:1024]
   else:
      in_state = None


   substitute = '<!-- Contents go here -->'

   # Instantiating all objects
   page = cw_page(in_state)

   # Three types of states:
   # 1) Normal page creation (randomized elements)
   # 2) A permalink page (state variable has an x in it)
      # One news or feature, footer, link to the main page)
   # 3) Easter eggs

   # Fresh new HTML, no previous state provided
   if ( page.state.in_state == None ):
      base = open('base.html', 'r')
      html = base.read()
      html = html.replace(substitute, create_page(page))
      start_response('200 OK', [('Content-Type','text/html')])

   # Permalink page of some kind
   elif (( page.state.news_permalink != None ) or
         ( page.state.features_permalink != None ) or 
         ( page.state.topics_permalink != None )): 
      base = open('base.html', 'r')
      html = base.read()
      html = html.replace(substitute, create_page(page))
      start_response('200 OK', [('Content-Type','text/html')])

   # Doing a search
   elif ( page.state.search != None ): 
      if ( page.state.search == [''] ):
         # No search query given -- just regenerate the page
         page = cw_page()

      start_response('200 OK', [('Content-Type','text/html')])
      html = create_page(page)

   # Otherwise, there is state, but no special headers.
   else:
      start_response('200 OK', [('Content-Type','text/html')])
      html = create_page(page)

   # Load html contents into the page with javascript
   return html



# Allows CLI testing when QUERY_STRING is in the environment
# TODO: pass QUERY_STRING as a CLI argument
if __name__ == "__main__":
   stub = lambda a, b: a.strip()
   html = application(True, stub)
   print html
