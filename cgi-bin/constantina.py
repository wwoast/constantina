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
from sys import stdin
import re
import magic
import lxml.html
from urllib import unquote_plus
import syslog
import ConfigParser

syslog.openlog(ident='constantina')
CONFIG = ConfigParser.SafeConfigParser()
CONFIG.read('constantina.ini')


# Only do opendir once per directory
DIR_INDEX = {}


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
      - The spacing per page of news cards
      - Whether the page state is asking to filter cards of a specific type

   Through checking the configured card_counts, we create one of these
   objects named for each card type (ctype).
   """
   def __init__(self, ctype, count, distance, filtertype, spacing):
      self.ctype = ctype
      self.count = count
      self.distance = distance
      self.filtertype = filtertype
      self.spacing = spacing

      self.clist = []      # List of card indexes that appeared of this type
      # Number of files of this type
      self.file_count = len(opendir(self.ctype))	
      # Files per page of this type
      self.per_page = CONFIG.getint("card_counts", self.ctype)
      # How many ctype cards should we see before the same card
      # appears again in the randomized view? This is a function
      # of the number of available cards
      if ( self.per_page == 0 ):
         self.page_distance = 0
      else: 
         self.page_distance = self.file_count*2 / self.per_page


   def shuffle(self):
      """Once a fixed seed is set in the state object, run the shuffle method
         to get the shuffled file listing for this ctype created."""
      self.__shuffle_files()
      # syslog.syslog("Shuffled list of " + self.ctype + ": " + str(self.clist))
      self.__mark_uneven_distribution()
      # syslog.syslog("Marked list of " + self.ctype + ": " + str(self.clist))
      self.__replace_marked()
      syslog.syslog("Final list of " + self.ctype + ": " + str(self.clist))
            

   def __shuffle_files(self):
      """Take a card type, and create a shuffle array where we can preserve
         normal page-state numbering, using those page-state values as indexes
         into a shuffled list of files. The shuffled array is extended, but
         adjusted so that repeat rules across pages will be respected"""
      total_pages = int(floor(len(opendir("news")) / CONFIG.getint("card_counts", "news")))
      total_ctype = total_pages * self.per_page

      # Guarantee enough cards to choose from
      self.clist = range(0, self.file_count) * total_ctype
      self.clist = self.clist[0:total_ctype]
      shuffle(self.clist)


   def __mark_uneven_distribution(self):
      """Look across a clist and remove any cards that would appear on the next
         Nth page, which duplicate a card you've seen on this page. The array is made
         large enough that just outright removing items should be ok. The N distance
         between pages is a function of the number of possible elements."""
      for i in range(0, len(self.clist)):
         if ( self.clist[i] == 'x' ):
            continue

         part_end = i + self.page_distance
         if ( i + part_end > len(self.clist)):
            part_end = len(self.clist)

         # Mark array items for removal
         for j in range(i+1, part_end):
            if ( self.clist[i] == self.clist[j] ):
               self.clist[j] = 'x'

   
   def __replace_marked(self):
      """Given 'x' marked indexes from __mark_even_distribution, determine good 
         replacement values."""
      for i in range(0, len(self.clist)):
         if ( self.clist[i] != 'x' ):
            continue

         part_start = i - self.page_distance
         if ( i - part_start < 0 ):
            part_start = 0;
         part_end = i + self.page_distance
         if ( i + part_end > len(self.clist)):
            part_end = len(self.clist)

         choices = range(0, self.file_count)
         shuffle(choices)
         for k in choices:
            if ( k not in self.clist[part_start:part_end] ):
               self.clist[i] = k
               break


class cw_state:
   """
   Constantina Page State Object.

   This is serialized and deserialized from a string embedded in JS
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
      self.in_state = in_state      # Track the original state string
      self.__set_state_defaults()

      # Was there an initial state string? Process it if there was.
      # TODO: manage all the import state code
      if ( self.in_state != None ):
         self.state_vars = self.in_state.split(':')   # TODO: max state params?
      else:
         self.state_vars = []
      self.__import_state()

      # For any card types we want to shuffle, do the shuffle dance
      # TODO: must have imported all states first
      for ctype in CONFIG.get("card_properties", "randomize").replace(" ","").split(","):
         getattr(self, ctype).shuffle()

      # syslog.syslog("Random seed: " + str(self.seed))


   def __set_state_defaults(self):
      """
      Set basic default values for special_state properties and normal
      content-card properties, as well as upper limits on how many cards can
      exist on a single Constantina page.
      """
      self.max_items = 0             # Max items per page, based on
                                     # counts from all card types
      for ctype, cpp in CONFIG.items('card_counts'):
         self.max_items = self.max_items + int(cpp)

      # For the card types in the card_counts config, create variables, i.e.
      #   state.news.distance, state.topics.spacing
      for ctype, card_count in CONFIG.items('card_counts'):
         setattr(self, ctype, cw_cardtype(
            ctype=ctype,
            count=int(card_count),
            distance=None,
            filtertype=False,
            spacing=CONFIG.getint('card_spacing', ctype)))

      for spctype, spcfield in CONFIG.items("special_states"):
         setattr(self, spcfield, None)       # All state vals are expected to exist

      # TODO: refactor card_filter so this isn't necessary
      self.card_filter = []


   def __find_state_variable(self, search):
      """
      Leveraged by all the other state functions. Find the given state
      variable, either by state variable name, or "number" to find the 
      random seed. Once a state variable is consumed, remove it from
      the state_vars.
      """
      if ( self.state_vars == [] ): 
         return None

      hits = []
      output = None 

      # Random seed is the one all-numeric state variable
      if ( search == "seed" ):
         hits = [token for token in self.state_vars if token.isdigit()]
         if ( len(hits) > 0 ):
            output = hits[0]
      # Special state variables are singleton values. Typically a
      # two-letter value starting with "x" as the first letter.
      # TODO: do we need to preserve the comma-separated crap?
      elif ( CONFIG.has_option("special_states", search) ):
         hits = [token for token in self.state_vars if token.find(search) == 0]
         if ( len(hits) > 0 ):
            output = unquote_plus(hits[0][2:])
      # Individual content card state variables. Each one is a distance
      # from the current page. 
      elif ( search in [s[0] for s in CONFIG.options("card_counts")] ):
         hits = [token for token in self.state_vars if token.find(search) == 0]
         if ( len(hits) > 0 ):
            output = int(hits[0][1:])

      # Remove any matches for state variables, including extraneous duplicates
      [self.state_vars.remove(x) for x in hits]
      return output


   def __import_random_seed(self):
      """
      Set the return seed based on a 14-digit string from the state variable.
      As an input to seed(), this has to be a float between zero and one.

      This seed is used to consistently seed the shuffle function, so that
      between page loads, we know the shuffled card functions give the same
      shuffle ordering.
      """
      self.seed = self.__find_state_variable("seed")		          
      if (self.seed == None):
         self.seed = round(random(), 14)
      else:
         self.seed = float(str("0." + self.seed))
      seed(self.seed)   # Now the RNG is seeded with our consistent value


   def __import_content_card_state(self):   
      """
      News cards and other content cards' state is tracked here. Seed tracking
      between page loads means we don't need to log which content cards were
      shown on a previous page. 

      However, to preserve card spacing rules, we do need to track the distance
      of each card type from the first element of the current page.
      """
      # For each content card type, populate the state variables
      # as necessary. TODO: news distance is actually a news[] index
      for state_var in [s[0] for s in CONFIG.options('card_counts')]:
         # NOTE: This ctype attribute naming requires each content card type to
         # begin with a unique alphanumeric character.
         ctype = [value for value in CONFIG.options("card_counts") if value[0] == state_var][0]
         distance = self.__find_state_variable(state_var)
         getattr(self, ctype).distance = distance
         

   def __import_page_count_state(self):
      """
      For all subsequent "infinite-scroll AJAX" content after the initial page
      load, we track the current page number of content.
      """
      self.page = self.__find_state_variable('xp')

      # If page was read in as a special state variable, use that (for search results)
      if ( self.page != None ) and (( self.search != None ) or ( self.card_filter != None )):
         self.page = int(self.page[0])
      # Otherwise, determine our page number from the news article index reported
      # TODO: for news articles, it's not a distance value! Its a news[] index
      elif ( self.news.distance != None ):
         self.page = ( int(self.news.distance) + 1 ) / CONFIG.getint('card_counts', 'news')
      else:
         self.page = 0


   def __import_theme_state(self):
      """
      In the state object, we track an appearance variable, which corresponds
      to the exact state variable imported (and exported) for the appearance.

      The appearance value lets us look up which theme we display for the user.
      This theme value is a path fragment to a theme's images and stylesheets.
      """
      self.appearance = self.__find_state_variable('xa')

      # Default theme specified in configs (exclude the default setting)
      if ( self.appearance != None ):
         self.appearance = int(self.appearance[0])

      theme_count = len(CONFIG.items("themes")) - 1
      self.theme = None
      if ( self.appearance == None ):
         self.theme = CONFIG.get("themes", "default")
      elif ( self.appearance >= theme_count ):
         self.theme = CONFIG.get("themes", str(self.appearance % theme_count))
      else:
         self.theme = CONFIG.get("themes", str(self.appearance))


   def __import_permalink_state(self):
      """
      Any card type that can be displayed on its own is a permalink-type
      card, and will have state that describes which permalink page should
      be loaded.
      """
      permalink_states = [sv[0] for sv in CONFIG.items("special_states") if sv[1].find("permalink") != -1]
      for state in permalink_states:
         value = self.__find_state_variable(state)
         if value != None:
            attrib = CONFIG.get("special_states", state)
            setattr(self, attrib, value)
            return   # Only one permalink state per page. First one takes precedence


   def __import_search_state(self):
      """
      Import the search terms that were used on previous page loads

      Some of these terms may be prefixed with a #, which makes them either cardtypes or 
      channel names. 
      """	
      self.search = self.__find_state_variable('xs')

      # First, check if any of the search terms should be processed as a 
      # cardtype and be added to the filter state instead.
      if ( self.search != None ):
         searchterms = self.search.split(' ')
         searchterms = filter(None, searchterms)   # remove nulls
         self.card_filter = self.__add_filter_cardtypes(searchterms)
         # Remove filter strings from the search state list if they exist
         [searchterms.remove(term) for term in self.card_filter]
         self.search = " ".join(searchterms)   # TODO: consider making self.search an array

      # Now, if no filter strings were found, we may need to process a set
      # of filter strings that were excised out on a previous page load.
      if ( self.card_filter == [] ):
         self.card_filter = self.__find_state_variable('xo')
         # Add-filter-cardtypes expects strings that start with #
         if ( self.card_filter != None ):
            hashtag_process = map(lambda x: "#" + x, self.card_filter)
            self.card_filter = self.__add_filter_cardtypes(hashtag_process)
         else:
            self.card_filter = []   # TODO: factor this out


   def __import_filtered_card_count(self):
      """
      Filtered card count, tracked when we have a query type and a filter count
      and cards on previous pages were omitted from being displayed. Tracking
      this allows you to fix the page count to represent reality better.
      """
      self.filtered = self.__find_state_variable('xx')
      if ( self.filtered != None ) and (( self.search != None ) and ( self.card_filter != None )):
         self.filtered = int(self.filtered[0])
      else:
         self.filtered = 0
   

   def __add_filter_cardtypes(self, searchterms):
      """
      If you type a hashtag into the search box, Constantina will do a 
      filter based on the cardtype you want. Aliases for various types
      of cards are configured in constantina.ini
      """
      removeterms = []
      filtertypes = []

      for term in searchterms:
         # syslog.syslog("searchterm: " + term + " ; allterms: " + str(searchterms))
         if term[0] == '#':
            for ctype, filterlist in CONFIG.items("card_filters"):
               filternames = filterlist.replace(" ", "").split(',')
               for filtername in filternames:
                  if term == '#' + filtername:
                     # Toggle this cardtype as one we'll filter on
                     getattr(self, ctype).filtertype = True
                     # Page filtering by type is enabled
                     # Add to the list of filterterms, and prepare to
                     # remove any filter tags from the search state.
                     filtertypes.append(ctype)
                     removeterms.append(term)

      return removeterms


   def __import_state(self):
      """
      Given a state variable string grabbed from the page, parse a
      parse into an object full of card-list properties. This will 
      be used to define which cards should be obtained for the page.
      """
      self.__import_random_seed()          # Import the random seed first
      self.__import_content_card_state()   # Then import the normal content cards
      self.__import_theme_state()          # Theme settings
      self.__import_search_state()         # Search strings and filter strings
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
      all_ctypes = CONFIG.options("card_counts")

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
      hidden_cards = 0    # Account for each hidden card in the distance
                          # between here and the end of the page
      news_seen = False   # Have we processed a news card yet?
                          # TODO: how to clean deal with news_last?
      # Traversing backwards from the end, find the last of each cardtype shown
      for i in xrange(len(cards) - 1, -1, -1):
         card = cards[i]
         if (card.ctype == 'news'):
            if ( news_seen == False ):
               self.news.distance = card.num   # TODO: news index, not distance!!
               news_seen = True
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
         syslog.syslog("=> %s dist: %d i: %d card-len: %d  eff-len: %d" % ( card.ctype, dist, i, len(cards), len(cards) - hidden_cards))
         getattr(self, card.ctype).distance = str(dist)
         # Early break once we've seen all the card types
         if ( done_distance == all_ctypes ):
            break


   def __export_random_seed(self):
      """Export the random seed for adding to the state variable"""
      return str(self.seed).replace("0.", "")


   def __export_content_card_state(self):
      """
      Construct a string representing the cards that were loaded on this
      page, for the sake of informing the next page load.
      """
      state_tokens = []
      content_string = None

      for ctype in CONFIG.options("card_counts"):
         # If no cards for this state, do not track
         if (( getattr(self, ctype).clist == [] ) or ( getattr(self, ctype).distance == None )):
            continue

         # Track the distance to the last-printed card in each state variable
         stype = ctype[0]
         cdist = getattr(self, ctype).distance
         state_tokens.append(stype + str(cdist))

      # Track page number for the next state variable by adding one to the current
      news_last = str(getattr(self, 'news').distance)   # TODO: not distance, but news index!
      if ( state_tokens != [] ):
         content_string = ":".join(state_tokens) + ":" + "n" + news_last
      else:
         content_string = "n" + news_last
      return content_string


   def __export_page_count_state(self, query_terms, filter_terms):
      """
      If we had search results and used a page number, write an incremented page
      number into the next search state for loading
      """
      # TODO: don't use query_terms and filter_terms. Use the state mode checks
      page_string = None
      if (( query_terms != '' ) or ( filter_terms != '' )):
         export_page = int(self.page) + 1
         page_string = "xp" + str(export_page)
      return page_string      


   def __export_theme_state(self):
      """
      If there was a appearance or theme tracked, include it in state links
      """
      appearance_string = None
      if ( self.appearance != None ):
         appearance_string = "xa" + str(self.appearance)
      return appearance_string


   def __export_search_state(self, query_terms, filter_terms):
      """
      Export state related to searched cards and filtered card types.
      """ 
      # TODO: don't use query_terms and filter_terms. Use the state mode checks
      filter_string = None
      query_string = None
      search_string = None

      if ( filter_terms != '' ):
         filter_string = "xo" + filter_terms
      if ( query_terms != '' ):
         query_string = "xs" + query_terms

      if (( filter_string != None ) or ( query_string != None )):
         search_string = ':'.join([filter_string, query_string])

      return search_string


   def __export_filtered_card_count(self, query_terms, filtered_terms):
      """
      If any cards were excluded by filtering, and a search is in progress,
      track the number of filtered cards in the state.
      """
      # TODO: don't use query_terms and filter_terms. Use the state mode checks
      filtered_count_string = None
      if (( query_terms != '' ) and ( filter_terms != '' )):
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
      # TODO: don't use query_terms and filter_terms. Use the state mode checks
      export_parts = [ self.__export_random_seed(),
                       self.__export_content_card_state(),
                       self.__export_search_state(query_terms, filter_terms),
                       self.__export_filtered_card_count(query_terms, filter_terms),
                       self.__export_page_count_state(query_terms, filter_terms),
                       self.__export_theme_state() ]

      export_parts = filter(None, export_parts)
      syslog.syslog(str(export_parts))
      export_string = ':'.join(export_parts)
      return export_string


   def configured_states(self):
      """Check to see which special states are enabled. Return an array of 
         either card types or special state types that are not set to None."""
      state_names = [val[1] for val in CONFIG.items('special_states')]
      state_names.remove('page')       # These two are set no matter what
      state_names.remove('filtered')
      return [state for state in state_names 
                 if (( getattr(self, state) != None ) and 
                     ( getattr(self, state) != [] ))]


   def fresh_mode(self):
      """Either an empty state, or just an empty state and a theme is set"""
      # syslog.syslog("initial state:" + str(self.in_state) + "  configured states: " + str(self.configured_states()))
      if (( self.page == 0 ) and 
          (( self.in_state == None ) or 
           ( self.configured_states() == ['appearance'] ))):
         return True
      else:
         return False


   def permalink_mode(self):
      """Is one of the permalink modes on?"""
      if (( self.news_permalink != None ) or 
          ( self.features_permalink != None ) or 
          ( self.topics_permalink != None )):
         return True
      else:
         return False


   def filter_processed_mode(self):
      """Is it a search state, and did we already convert #hashtag strings into
         filter queries?"""
      states = self.configured_states()
      if (( 'search' in states ) or 
          ( 'card_filter' in states )):
         return True
      else:
         return False


   def filter_only_mode(self):
      """All search queries converted into card filters"""
      if ( self.configured_states() == ['card_filter'] ):
         return True
      else:
         return False


   def search_only_mode(self):
      """There is a search query, but no terms converted into card filters"""
      if ( self.configured_states() == ['search'] ):
         return True
      else:
         return False


   def search_mode(self):
      """Any valid state from a search mode will trigger this mode"""
      if (( self.search != None ) or
          ( self.card_filter != [] ) or 
          ( self.filtered != 0 )):
         return True
      else:
         return False


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
      self.state = in_state
      self.out_state = ''

      self.search_results = ''
      self.query_terms = ''    # Use this locally, in case we happen not to create a search object
      self.filter_terms = ''   # For filtering based on cardtypes 
      self.filtered = 0        # Cards excluded from search results by filtering

      news_items = CONFIG.getint("card_counts", "news")

      if ( self.state.fresh_mode() == True ):
         # Create a new page of randomly-assorted images and quotes,
         # along with reverse-time-order News items
         syslog.syslog("***** Completely new page-load workflow *****")
         self.__get_cards()
         self.__distribute_cards()
         self.cards.insert(0, cw_card('heading', 'welcome', grab_body=True))

         if ( len(self.cards) - self.cur_len > news_items ):
            # Add a hidden card to trigger loading more data when reached
            self.cards.insert(len(self.cards) - 7, cw_card('heading', 'scrollstone', grab_body=True))
            # Finally, add the "next page" tombstone to load more content
            self.cards.append(cw_card('heading', 'tombstone', grab_body=True))
         else:
            self.cards.append(cw_card('heading', 'bottom', grab_body=True))

      elif ( self.state.permalink_mode() == True ):
         # This is a permalink page request. For these, use a
         # special footer card (just a header card placed at 
         # the bottom of the page).
         syslog.syslog("***** Permalink page workflow *****")
         self.__get_permalink_card()
         self.cards.append(cw_card('heading', 'footer', grab_body=True, permalink=True))

      elif ( self.state.search_mode() == True ):
         # Return search results based on the subsequent comma-separated list,
         # parsed by __import_state into self.state.search.
         # TODO: Tokenize all search parameters and remove non-alphanum characters
         # other than plus or hash for hashtags. All input-commas become pluses
         syslog.syslog("***** Search/Filter card workflow *****")
         self.search_results = cw_search(self.state.page, self.state.max_items, self.state.search, self.state.card_filter, self.state.filtered)
         self.query_terms = self.search_results.query_string
         self.filter_terms = self.search_results.filter_string
         self.filtered = self.search_results.filtered
         self.__get_search_result_cards()
         self.__distribute_cards()
       
         # If the results have filled up the page, try and load more results
         syslog.syslog("page:%d  maxitems:%d  max-filter:%d  cardlen:%d" % (self.state.page, self.state.max_items, self.state.max_items - self.filtered, len(self.cards))) 
         if (( self.state.max_items - self.filtered ) * ( self.state.page + 1 ) <= len(self.cards)):
            # Add a hidden card to trigger loading more data when reached
            self.cards.insert(len(self.cards) - 7, cw_card('heading', 'scrollstone', grab_body=True))
            # Finally, add the "next page" tombstone to load more content
            self.cards.append(cw_card('heading', 'tombstone', grab_body=True))
         else:
            self.cards.append(cw_card('heading', 'bottom', grab_body=True))

      else:
         # Get new cards for an existing page, tracking what the
         # previous page's state variable was in creating the list 
         # of cards to display.
         syslog.syslog("***** New cards on existing page workflow *****")
         self.__get_prior_cards()
         self.__get_cards()
         self.__distribute_cards()

         # TODO: news dist isn't dist!
         if ( self.state.news.distance + self.state.news.per_page <= self.state.news.file_count ): 
            # Add a hidden card to trigger loading more data when reached
            self.cards.insert(len(self.cards) - 7, cw_card('heading', 'scrollstone', grab_body=True))
            # Finally, add the "next page" tombstone to load more content
            self.cards.append(cw_card('heading', 'tombstone', grab_body=True))
         else:
            self.cards.append(cw_card('heading', 'bottom', grab_body=True))

      # Once we've constructed the new card list, update the page
      # state for insertion, for the "next_page" link.
      self.out_state = self.state.export_state(self.cards, self.query_terms, self.filter_terms, self.filtered)
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
      for ctype, count in CONFIG.items("card_counts"):
         card_count = int(count)
         # No topic cards unless they're search results, and no card types
         # that have no historical values in the last page
         if ( card_count == 0 ):
            continue
         # No data and it's not the first page? Skip this type
         if ( getattr(self.state, ctype).clist == None ) and ( self.state.fresh_mode() == False ):
            continue
         # Are we doing cardtype filtering, and this isn't an included card type?
         if ( getattr(self.state, ctype).filtertype == False ) and ( len(self.state.card_filter) > 0 ):
            continue

         # Grab the cnum of the last inserted thing of this type
         # and then open the next one
         # If we didn't open anyting last time, start at the beginning
         if ( self.state.fresh_mode() == True ):
            start = 0
         # If these are previous items, calculate how many were on previous pages
         else:
            start = int(self.state.page * card_count) + 1

         for i in xrange(start, start + card_count):
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
      # card of the results. TOPIC articles must be filenamed lowercase!!
      # HOWEVER if we're beyond the first page of search results, don't add
      # the encyclopedia page again! Use image count as a heuristic for page count.
      if ( self.query_terms.lower() in opendir('topics')):
         encyclopedia = cw_card('topics', self.query_terms.lower(), state=self.state, grab_body=True, search_result=True)
         self.cards.append(encyclopedia)

      # Other types of search results come afterwards
      search_types = CONFIG.get("card_properties", "search").replace(" ","").split(",")
      for ctype in search_types:
         # Manage the encyclopedia cards separately
         if ( ctype == 'topics' ):
            continue
         # Are we doing cardtype filtering, and this isn't an included card type?
         syslog.syslog("ctype: " + ctype + " filter: " + str(getattr(self.state, ctype).filtertype) + " card_filter_state: " + str(self.state.card_filter))
         if ( getattr(self.state, ctype).filtertype == False ) and ( len(self.state.card_filter) > 0 ):
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
               for k in xrange(0, len(DIR_INDEX[ctype])):
                  # syslog.syslog("compare:" + grab_file + "==" + DIR_INDEX[ctype][k])
                  if DIR_INDEX[ctype][k] == grab_file:
                     grab_file = k
                     break

            card = cw_card(ctype, grab_file, state=self.state, grab_body=True, search_result=True)
            # News articles without topic strings won't load. Other card types that
            # don't have embedded topics will load just fine.
            if ( card.topics != [] ) or ( ctype == 'quotes' ) or ( ctype == 'topics' ):
               self.cards.append(card)
               # print "%s %s %s" % ( len(self.cards), ctype, self.cards[-1].title )


   def __get_permalink_card(self):
      """Given a utime or card filename, return a pre-constructed
         permalink page of that type."""
      for spctype, spcfield in CONFIG.items("special_states"):
         if ( getattr(self.state, spcfield) != None ):
            if ( spctype == "xo" ) or ( spctype == "xp" ) or ( spctype == "xx" ) or ( spctype == "xa" ): 
               # TODO: make xo objects consistent with other absent states
               continue
            cnum = str(getattr(self.state, spcfield))
            syslog.syslog("permalink card loaded: " + str(cnum))
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
      if ( self.state.news.distance != None ):
         news_items = int(self.state.news.distance)   # TODO: track separately
      else:
         news_items = 0

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
      for ctype, card_count in CONFIG.items("card_counts"):
         # Are we doing cardtype filtering, and this isn't an included card type?
         if ( getattr(self.state, ctype).filtertype == False ) and ( len(self.state.card_filter) > 0 ):
            continue
         dist = getattr(self.state, ctype).distance
         if (( len(getattr(self.state, ctype).clist) == 0 ) or ( dist == None )):
            continue
         # syslog.syslog("ctype, len, and dist: " + str(ctype) + " " + str(len(self.cards)) + " " + str(dist))
         put = len(self.cards) - 1 - int(dist)
         for cnum in getattr(self.state, ctype).clist:
            self.cards.insert(put, cw_card(ctype, cnum, grab_body=False))

      # Current length should properly track the starting point
      # of where we begin adding new cards to the page, not just 
      # tracking the old ones.
      self.cur_len = len(self.cards)


   def __distribute_cards(self):
      """
      Distribute cards evenly in the array in order to 
      describe the ordering of a page. Use slight random jitter
      in placement to guarantee fresh page ordering every time
      """
      total = len(self.cards)
      lstop = self.cur_len 
      p_dist = total - lstop
      # Distance from last ctype'd card on the previous page
      c_dist = {}
      # "hold-aside" hash to help shuffle the main run of cards
      c_redist = {}
      # non-redist set (news articles)
      c_nodist = {}      

      for ctype, spacing in CONFIG.items("card_spacing"):
         # Spacing rules from the last page. Subtract the distance from
         # the end of the previous page. For all other cards, follow the
         # strict card spacing rules from the config file, plus jitter
         spacing = int(spacing)
         distance = getattr(self.state, ctype).distance
         if ( distance == None ):
            distance = 0

         if ( distance >= spacing ):   # Prev page ctype card not close
            c_dist[ctype] = 0
         elif (( lstop == 0 ) and ( distance == 0 )):   # No pages yet
            c_dist[ctype] = 0
         else:   # Implement spacing from the beginning of the new page
            c_dist[ctype] = spacing - distance
         # syslog.syslog("*** initial spacing: ctype:%s  spacing:%d  c_dist:%d  distance:%d  lstop:%d" % ( ctype, spacing, c_dist[ctype], distance, lstop))
         c_redist[ctype] = []
         c_nodist[ctype] = []

      # Make arrays of each card type, so we can random-jump their inserts later.
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
      # TODO: lowest card-count ctype inserts happen first, so there is better
      # spacing for higher-card-count types
      for ctype in sorted(c_redist, key=lambda ctype: len(c_redist[ctype])):
         if ( c_redist[ctype] == [] ):
            continue   # Empty
         # Are we doing cardtype filtering, and this isn't an included card type?
         if ( getattr(self.state, ctype).filtertype == False ) and ( len(self.state.card_filter) > 0 ):
            continue

         # Max distance between cards of this type on a page
         norm_dist = getattr(self.state, ctype).spacing
         # Number of input cards we're working with 
         # (should never be more than getattr(self.state, ctype).count
         card_count = len(c_redist[ctype])
         # For spacing purposes, page starts at the earliest page we can
         # put a card on this page, w/o being too close to a same-type
         # card on the previous page. This shortens the effective page dist
	 effective_pdist = p_dist - c_dist[ctype]
         max_dist = effective_pdist
         if ( card_count >= 1 ):
            max_dist = floor(effective_pdist / card_count)

         # If less cards on the page then expected, degrade
         if ( max_dist < norm_dist ):
            max_dist = norm_dist
            norm_dist = max_dist - 1

         # Let jumps be non-deterministic
         seed()

         # Start with an initial shorter distance for shuffling.
         # The furthest initial insert spot isn't the "first space", but
         # the maximum insert distance before spacing rules are not possible
         # to properly follow.
         start_jrange = c_dist[ctype]
         cur_p_dist = len(self.cards) - lstop
         next_cnt = 1
         cards_ahead = card_count - next_cnt 
         end_jrange = cur_p_dist - (cards_ahead * norm_dist)
         # syslog.syslog("*** dist initial: ctype:%s  cnt:%d  spacing:%d cur_pd:%d  sj:%d  ej:%d" % ( ctype, len(c_redist[ctype]), norm_dist, cur_p_dist, start_jrange, end_jrange))

         # Add back the cards. NOTE all jumpranges must be offsets from lstop,
         # not specific indexes that refer to the insert points in the array
         for k in xrange(0, card_count):
            # Not many items in the array?
            if ( start_jrange >= end_jrange ):
               jump = start_jrange
            else:
               jump = randint(start_jrange, end_jrange)

            ins_index = lstop + jump  

            card = c_redist[ctype][k]
            self.cards.insert(ins_index, card)
            # syslog.syslog("k:%d  ins_index:%d  jump:%d  cur_pd:%d  sj:%d  ej:%d" % ( k, ins_index, jump, cur_p_dist, start_jrange, end_jrange))

            # For next iteration, spacing is at least space distance away from
            # the current insert, and no further than the distance by which
            # future spacing rules are not possible to follow.
            start_jrange = jump + norm_dist
            cur_p_dist = len(self.cards) - lstop
            next_cnt = next_cnt + 1
            cards_ahead = card_count - next_cnt
            end_jrange = cur_p_dist - (cards_ahead * norm_dist)


      # Return seed to previous deterministic value, if it existed
      if ( self.state.seed ):
         seed(self.state.seed)

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
      self.title = CONFIG.get("card_defaults", "title")
      self.topics = []
      self.body = CONFIG.get("card_defaults", "body")
      self.ctype = ctype
      # Request either the Nth entry of this type, or a specific utime/date
      self.num = num
      # If we need to access data from the state object, for card shuffling
      self.state = state
      self.songs = []
      self.cfile = CONFIG.get("card_defaults", "file")
      self.cdate = CONFIG.get("card_defaults", "date")
      self.permalink = permalink
      self.search_result = search_result
      self.hidden = False
      # Don't hit the filesystem if we're just tracking which cards have
      # been previously opened (cw_page.__get_previous_cards)
      if ( grab_body == True ):
         self.cfile = self.__openfile()


   def __openfile(self):
      """Open a file in a folder by "number", and populate the cw_card object.
         For most files, this will be an integer (card number) that represents 
         the Nth file in a directory.
         For news files, the filename itself is a Unix timestamp number, and
         can be specified directly."""
      type_files = opendir(self.ctype, self.hidden)

      # Find the utime value in the array if the number given isn't an array index.
      # If we're inserting cards into an active page, the state variable will be
      # given, and should be represented by a shuffled value.
      random_types = CONFIG.get("card_properties", "randomize").replace(" ","").split(",")
      if (( self.ctype in random_types ) and ( self.state != False )
                                         and ( self.search_result == False )
                                         and ( self.hidden == False )):
         cycle = len(getattr(self.state, self.ctype).clist)
         which_file = getattr(self.state, self.ctype).clist[self.num % cycle]

         # Logic for hidden files, which only works because it's inside the
         # random_types check
         if ( which_file == 'x' ):
            self.hidden = True
            type_files = opendir(self.ctype, self.hidden)
            # syslog.syslog(str(DIR_INDEX.keys()))
            hidden_cards = xrange(0, len(DIR_INDEX[self.ctype + "/hidden"]))
            self.num = hidden_cards[randint(0, len(hidden_cards)-1)]
            # TODO: totally random selected card (unset seed)
            # syslog.syslog("open hidden file: " + str(self.num) + "/" + str(hidden_cards))
            which_file = self.num
         else:
            # syslog.syslog("open file: " + str(self.num) + "/" + str(cycle))
            pass

      else:
         which_file = self.num

      # News files: convert utime filename to the "Nth" item in the folder
      if ( which_file >= len(type_files)): 
         if ( self.num in type_files):
            which_file = type_files.index(self.num)
            self.num = which_file
         else:
            return "nofile"

      return self.__interpretfile(type_files[which_file])


   def __songfiles(self):
      """Create an array of song objects for this card"""
      for songpath in self.body.splitlines():
         songpath = CONFIG.get("paths", "songs") + "/" + songpath
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

      base_path = CONFIG.get("paths", self.ctype)
      if ( self.hidden == True ):
         fpath = base_path + "/hidden/" + thisfile
      else: 
         fpath = base_path + "/" + thisfile

      try:
         with open(fpath, 'r') as cfile:
            ftype = magi.from_file(fpath)
            # News entries or features are processed the same way
            if (( "text" in ftype ) and 
                (( CONFIG.get("paths", "news") in cfile.name ) or
                 ( CONFIG.get("paths", "heading") in cfile.name ) or 
                 ( CONFIG.get("paths", "quotes") in cfile.name ) or 
                 ( CONFIG.get("paths", "topics") in cfile.name ) or 
                 ( CONFIG.get("paths", "features") in cfile.name ))):
               self.title = cfile.readline().replace("\n", "")
               rawtopics = cfile.readline().replace("\n", "")
               for item in rawtopics.split(', '):
                  self.topics.append(item)
               self.body = cfile.read()
   
            # Multiple-song playlists
            if (( "text" in ftype ) and
                ( CONFIG.get("paths", "songs") in cfile.name )):
               self.title = fpath
               self.topics.append("Song Playlist")
               self.body = cfile.read()
               self.__songfiles()   # Read song metadata
   
            # Single-image cards
            if ((( "jpeg" in ftype ) or ( "png" in ftype)) and 
                 ( CONFIG.get("paths", "images") in cfile.name )):
               # TODO: alt/img metadata
               self.title = fpath
               self.topics.append("Images")
               self.body = fpath
   
            # Single-song orphan cards
            if ((( "mpeg" in ftype ) and ( "layer iii" in ftype)) and
                 ( CONFIG.get("paths", "songs") in cfile.name )):
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
         return CONFIG.get("card_defaults", "file")

      if ( self.hidden == True ):
          return CONFIG.get("paths", self.ctype) + "/hidden/" + thisfile
      else:
          return CONFIG.get("paths", self.ctype) + "/" + thisfile



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
   def __init__(self, page, resultcount, unsafe_query_terms, unsafe_filter_terms, previous_filtered):
      # List of symbols to filter out in the unsafe input
      self.ignore_symbols = []
      # Regex of words that won't be indexed
      self.ignore_words = ''
      # After processing unsafe_query or unsafe_filter, save it in the object
      # Assume we're searching for all terms, unless separated by pluses
      self.query_string = ''
      self.filter_string = ''
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

      # Max search results per page is equal to the number of cards that would
      # be shown on a normal news page. And while whoosh expects pages starting
      # at one, the page state counting will be from zero (possible TODO)
      self.page = page + 1
      self.resultcount = resultcount
      self.filtered = previous_filtered

      # File paths for loading things
      self.index_dir = CONFIG.get('search', 'index_dir')
      self.words_file = CONFIG.get('search', 'ignore_words')
      self.symobls_file = CONFIG.get('search', 'ignore_symbols')
      self.search_types = CONFIG.get("card_properties", "search").replace(" ","").split(",")

      # Define the indexing schema. Include the mtime to track updated 
      # content in the backend, ctype so that we can manage the distribution
      # of returned search results similar to the normal pages, and the 
      # filename itself as a unique identifier (most filenames are utimes).
      self.schema = Schema(file=ID(stored=True, unique=True, sortable=True), ctype=ID(stored=True), mtime=ID(stored=True), content=TEXT)

      # If index doesn't exist, create it
      if ( index.exists_in(self.index_dir)):
         self.index = index.open_dir(self.index_dir)
         # print "Index exists"
      else:
         self.index = index.create_in(self.index_dir, schema=self.schema)
         # print "Index not found -- creating one"
      # Prepare for query searching (mtime update, search strings)
      self.searcher = self.index.searcher()

      for ctype in self.search_types:
         # Prior to processing input, prepare the results arrays.
         # Other functions will expect this to exist regardless.
         self.hits[ctype] = []

      # Process the filter strings first, in case that's all we have
      if ( unsafe_filter_terms != None ):
         self.__process_input(' '.join(unsafe_filter_terms), returning="filter")

      # Double check if the query terms exist or not
      if ( unsafe_query_terms == None ):
         if ( self.filter_string != '' ):
            self.__filter_cardtypes()
            self.searcher.close()
            return
         else:
            self.searcher.close()
            return

      # If the query string is null after processing, don't do anything else.
      # Feed our input as a space-delimited set of terms. NOTE that we limit
      # this in the __import_state function in cw_state.
      if not ( self.__process_input(' '.join(unsafe_query_terms))):
         if ( self.filter_string != '' ):
            self.__filter_cardtypes()
            self.searcher.close()
            return
         else:
            self.searcher.close()
            return

      for ctype in self.search_types:
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

      self.searcher.close()


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
         with open(self.words_file, 'r') as wfile:
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
         with open(self.symbols_file, 'r') as sfile:
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
         elif ( returning == "filter" ):
            self.filter_string = safe_input
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
      card_path = CONFIG.get("paths", ctype)

      with open(card_path + "/" + filename, 'r') as indexfh:
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
      card_path = CONFIG.get("paths", ctype)

      for filename in DIR_INDEX[ctype]:
         try:
            fnmtime = int(os.path.getmtime(card_path + "/" + filename))
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


   def __search_index(self):
      """Given a list of search paramters, look for any of them in the 
      indexes. For now don't return more than 200 hits"""
      self.parser = QueryParser("content", self.schema)
      self.query = self.parser.parse(unicode(self.query_string))
      self.results = self.searcher.search_page(self.query, self.page, sortedby="file", reverse=True, pagelen=self.resultcount)
      # print self.results[0:]

      # Just want the utime filenames themselves? Here they are, in 
      # reverse-utime order just like we want for insert into the page
      for result in self.results:
         ctype = result['ctype']
         # Account for filter strings
         if ( self.filter_string != '' ):
            if result['ctype'] in self.filter_string.split(' '):
               self.hits[ctype].append(result['file'])
            else:
               self.filtered = self.filtered + 1
         else:
            self.hits[ctype].append(result['file'])


   def __filter_cardtypes(self):
      """Get a list of cards to return, in response to a card-filter
      event. These tend to be of a single card type."""
      self.parser = QueryParser("content", self.schema)

      for filter_ctype in self.filter_string.split(' '):
         self.query = self.parser.parse("ctype:" + filter_ctype)
         # TODO: implement a "search order" card parameter
         # Some card types get non-reverse-sorting by default
         self.results = self.searcher.search_page(self.query, self.page, sortedby="file", reverse=True, pagelen=self.resultcount)

         for result in self.results:
            ctype = result['ctype']
            # Account for filter strings
            if result['ctype'] in self.filter_string.split(' '):
               self.hits[ctype].append(result['file'])
            else:
               self.filtered = self.filtered + 1



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


def opendir(ctype, hidden=False):
   """
   Return either cached directory information or open a dir and
   list all the files therein. Used for both searching and for the
   card reading functions, so we manage it outside those.
   """
   directory = CONFIG.get("paths", ctype)
   if ( hidden == True ):
      directory += "/hidden" 
      ctype += "/hidden"

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
   This includes all card.heading and card.quotes, but possibly
   others as well. Do not apply any special logic to these cards -- 
   just get them drawn, whatever tags they might contain."""
   anchor = card.cfile.split('/').pop()

   output = ""
   output += """<div class="card %s" id="%s">\n""" % ( card.ctype, anchor )

   body_lines = card.body.splitlines()
   processed_lines = unroll_newlines(body_lines)

   for line in processed_lines:
      output += line + "\n"

   # For special tombstone cards, insert the state as non-visible text
   default_string = CONFIG.get("card_defaults", "tombstone")
   if ( card.title == default_string ):
      output += """\n<p id="state">%s</p>""" % next_state

   output += """</div>\n"""
   return output


def create_textcard(card, appearance):
   """All news and features are drawn here. For condensing content, 
   wrap any nested image inside a "read more" bracket that will appear 
   after the 1st paragraph of text. Hide images behind this link too.

   Fill out the next/previous type links based on #anchors done with a
   descending number. If the next page of content isn't loaded, make
   the link also load the next page of content before the anchor tag
   is followed.
   """
   # TODO: VET title and topics for reasonable size restrictions
   topic_header = ""
   for topic in card.topics:
       topic_link = """<a class="topicLink" href="javascript:">%s</a>""" % topic
       if ( topic_header == "" ):
           topic_header = topic_link
       else:
           topic_header = topic_header + ", " + topic_link
   anchor = card.cfile.split('/').pop()

   # The body of a text card consists of paragraphs of text, possibly
   # with a starting image tag. Wrap all tags other than the first 
   # paragraph tag with a "Expand" style that will keep that text
   # properly hidden. Then, after the end of the first paragraph, add
   # a "Read More" link for expanding the other hidden items.

   output = ""
   output += """<div class="card %s" id="%s">\n""" % ( card.ctype, anchor )
   output += """   <div class="cardTitle">\n"""
   if ( card.permalink == True ):
      output += """      <h2>%s</h2>\n""" % card.title
      output += """      <p class="subject">%s</p>\n""" % card.cdate
   else:
      output += """      <h2><a href="#%s" onclick="cardToggle('%s');">%s</a></h2>\n""" % ( anchor, anchor, card.title )
      output += """      <p class="subject">%s</p>\n""" % topic_header
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
            read_more = """ <a href="#%s" class="showShort" onclick="cardToggle('%s');">(Read&nbsp;More...)</a>""" % ( anchor, anchor )
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

   # Convert the appearance value into a string for permalinks
   appanchor = ""
   if ( appearance != None ):
      appanchor += ":xa" + str(appearance)

   # And close the textcard
   permanchor = "/?x" + card.ctype[0] + anchor + appanchor

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
   anchor = card.cfile.split('/')[1]
   # Get URI absolute path out of a Python relative path
   uripath = "/" + "/".join(card.cfile.split('/')[0:])

   output = ""
   output += """<div class="card image" id="%s">\n""" % anchor
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
   output += """<div class="card song">"""
   for song in card.songs:
      # Songs DIR can only be TLD, followed by album, and then songname
      uripath = "/" + "/".join(song.songfile.split("/")[-4:])

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
         output += create_textcard(page.cards[i], page.state.appearance)

      if (( page.cards[i].ctype == "quotes" ) or
          ( page.cards[i].ctype == "heading" )):
         output += create_simplecard(page.cards[i], page.out_state)

      if ( page.cards[i].ctype == "images" ):
         output += create_imagecard(page.cards[i])

      if ( page.cards[i].ctype == "songs" ):
         output += create_songcard(page.cards[i])

   return output


def authentication_page(start_response, state):
   """
   If Constantina is in "forum" mode, you get the authentication
   page. You also get an authentication page when you search for
   a @username in the search bar in "combined" mode.
   """
   base = open(state.theme + '/authentication.html', 'r')
   html = base.read()
   start_response('200 OK', [('Content-Type','text/html')])
   # TODO: persist in_state after login

   return html


def contents_page(start_response, state):
   """
   Three types of states:
   1) Normal page creation (randomized elements)
   2) A permalink page (state variable has an x in it)
      One news or feature, footer, link to the main page
   3) Easter eggs
   """ 
   substitute = '<!-- Contents go here -->'

   # Instantiating all objects
   page = cw_page(state)

   # Fresh new HTML, no previous state provided
   if ( state.fresh_mode() == True ):
      base = open(state.theme + '/contents.html', 'r')
      html = base.read()
      html = html.replace(substitute, create_page(page))
      start_response('200 OK', [('Content-Type','text/html')])

   # Permalink page of some kind
   elif ( state.permalink_mode() == True ):
      base = open(state.theme + '/contents.html', 'r')
      html = base.read()
      html = html.replace(substitute, create_page(page))
      start_response('200 OK', [('Content-Type','text/html')])

   # Doing a search or a filter process
   elif ( state.search_mode() == True ):
      if ( state.search == [''] ) and ( state.card_filter == [] ):
         # No search query given -- just regenerate the page
         syslog.syslog("***** Reshuffle Page Contents *****")
         page = cw_page()

      start_response('200 OK', [('Content-Type','text/html')])
      html = create_page(page)

   # Otherwise, there is state, but no special headers.
   else:
      start_response('200 OK', [('Content-Type','text/html')])
      html = create_page(page)

   # Load html contents into the page with javascript
   return html


def authentication():
   """
   Super naive test authentication function just as a proof-of-concept
   for validating my use of environment variabls and forms!
   """
   size = int(os.environ.get('CONTENT_LENGTH'))
   post = {}
   with stdin as fh:
      # TODO: max content length, check for EOF
      inbuf = fh.read(size)
      for vals in inbuf.split('&'):
         [ key, value ] = vals.split('=')
         post[key] = value

   if ( post['username'] == "justin" and post['password'] == "justin" ):
      return True
   else:
      return False


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
   root_dir = CONFIG.get("paths", "root")
   resource_dir = CONFIG.get("paths", "resource")

   os.chdir(root_dir + "/" + resource_dir)
   in_state = os.environ.get('QUERY_STRING')
   if ( in_state != None ) and ( in_state != '' ):
      # Truncate state variable at 1024 characters
      in_state = in_state[0:1024]
   else:
      in_state = None

   state = cw_state(in_state)   # Create state object
   auth_mode = CONFIG.get("authentication", "mode")

   if ( os.environ.get('REQUEST_METHOD') == 'POST' ):
      if ( authentication() == True ):
         return contents_page(start_response, state)
      else:   
         return authentication_page(start_response, state)

   if ( auth_mode == "blog" or auth_mode == "combined" ):
      return contents_page(start_response, state)
   else:
      return authentication_page(start_response, state)



# Allows CLI testing when QUERY_STRING is in the environment
# TODO: pass QUERY_STRING as a CLI argument
if __name__ == "__main__":
   stub = lambda a, b: a.strip()
   html = application(True, stub)
   print html
