import ConfigParser
import os
from math import floor
from random import randint, seed
import syslog

from auth import authentication, authentication_page
from shared import GlobalConfig, BaseFiles, opendir
from state import ConstantinaState
from medusa.cards import *
from medusa.search import MedusaSearch
# from zoo.state import ZooState
# from zoo.cards import *
# from zoo.search import ZooSearch

# Look up Cards by application config name, instead of calling
# MedusaCard/ZooCard directly
CardClass = {
    'medusa'  : MedusaCard
#   'zoo'     : ZooCard,
#   'dracula' : DraculaCard
}

syslog.openlog(ident='constantina')


class ConstantinaPage:
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
        """
        If there was a previous state, construct array of cards for
        the state without loading any files from disk. Then, load a
        new set of cards for addition to the page, and write a new
        state variable for the next AJAX load
        """
        self.cur_len = 0
        self.cards = []
        self.state = in_state
        self.out_state = ''

        self.search_results = ''
        self.query_terms = ''    # Use this locally, in case we happen not to create a search object
        self.filter_terms = ''   # For filtering based on cardtypes
        self.filtered = 0        # Cards excluded from search results by filtering
        self.applications = GlobalConfig.get("applications", "enabled").replace(" ", "").split(",")

        # TODO: card insertion logic needs to be considerably more generic if
        # there are multiple applications in play!
        if self.state.fresh_mode() is True:
            # Create a new page of randomly-assorted images and quotes,
            # along with reverse-time-order News items
            syslog.syslog("***** Completely new page-load workflow *****")
            self.__get_cards()
            self.__distribute_cards()
            self.cards.insert(0, MedusaCard('heading', 'welcome', state=self.state.medusa, grab_body=True))

            if self.state.out_of_content(len(self.cards)) is True:
                self.cards.append(MedusaCard('heading', 'bottom', state=self.state.medusa, grab_body=True))
            else:
                # Add a hidden card to trigger loading more data when reached
                self.cards.insert(len(self.cards) - 7, MedusaCard('heading', 'scrollstone', state=self.state.medusa, grab_body=True))
                # Finally, add the "next page" tombstone to load more content
                self.cards.append(MedusaCard('heading', 'tombstone', state=self.state.medusa, grab_body=True))

        elif self.state.permalink_mode() is True:
            # This is a permalink page request. For these, use a
            # special footer card (just a header card placed at
            # the bottom of the page).
            syslog.syslog("***** Permalink page workflow *****")
            self.__get_permalink_card()
            self.cards.append(MedusaCard('heading', 'footer', state=self.state.medusa, grab_body=True, permalink=True))

        elif self.state.search_mode() is True:
            # Return search results based on the subsequent comma-separated list,
            # parsed by __import_state into self.state.search.
            # TODO: Tokenize all search parameters and remove non-alphanum characters
            # other than plus or hash for hashtags. All input-commas become pluses
            syslog.syslog("***** Search/Filter card workflow *****")
            self.search_results = MedusaSearch(self.state)
            self.query_terms = self.search_results.query_string
            self.filter_terms = self.search_results.filter_string
            self.filtered = self.search_results.filtered
            self.__get_search_result_cards()
            self.__distribute_cards()

            # If the results have filled up the page, try and load more results
            syslog.syslog("page:%d  maxitems:%d  max-filter:%d  cardlen:%d" % (self.state.page, self.state.max_items, self.state.max_items - self.filtered, len(self.cards)))
            # TODO: this logic has issues
            if (self.state.max_items - self.filtered) * (self.state.page + 1) <= len(self.cards):
                # Add a hidden card to trigger loading more data when reached
                self.cards.insert(len(self.cards) - 7, MedusaCard('heading', 'scrollstone', state=self.state.medusa, grab_body=True))
                # Finally, add the "next page" tombstone to load more content
                self.cards.append(MedusaCard('heading', 'tombstone', state=self.state.medusa, grab_body=True))
            else:
                self.cards.append(MedusaCard('heading', 'bottom', state=self.state.medusa, grab_body=True))

        else:
            # Get new cards for an existing page, tracking what the
            # previous page's state variable was in creating the list
            # of cards to display.
            syslog.syslog("***** New cards on existing page workflow *****")
            self.__get_prior_cards()
            self.__get_cards()
            self.__distribute_cards()

            if self.state.out_of_content(len(self.cards)) is False:
                # Add a hidden card to trigger loading more data when reached
                self.cards.insert(len(self.cards) - 7, MedusaCard('heading', 'scrollstone', state=self.state.medusa, grab_body=True))
                # Finally, add the "next page" tombstone to load more content
                self.cards.append(MedusaCard('heading', 'tombstone', state=self.state.medusa, grab_body=True))
            else:
                self.cards.append(MedusaCard('heading', 'bottom', state=self.state.medusa, grab_body=True))

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
        # Anything with rules for cards per page, start adding them.
        # Do not grab full data for all but the most recent cards!
        # For older cards, just track their metadata
        for application in self.applications:
            app_state = getattr(self.state, application)
            for ctype in app_state.ctypes:
                card_count = getattr(app_state, ctype).count
                # No topic cards unless they're search results, and no card types
                # that have no historical values in the last page
                if card_count == 0:
                    continue
                # No data and it's not the first page? Skip this type
                if ((self.state.fresh_mode() is False) and
                    (getattr(app_state, ctype).clist is None)):
                    continue
                # Are we doing cardtype filtering, and this isn't an included card type?
                if app_state.exclude_cardtype(ctype) is True:
                    continue

                # Grab the cnum of the last inserted thing of this type
                # and then open the next one
                # If we didn't open anyting last time, start at the beginning
                if self.state.fresh_mode() is True:
                    start = 0
                # If these are previous items, calculate how many were on previous pages
                else:
                    start = int(self.state.page * card_count)

                for i in xrange(start, start + card_count):
                    # TODO: specify generic card class for obtaining
                    card = CardClass[application](ctype, i, state=app_state, grab_body=True)
                    # Don't include cards that failed to load content
                    if card.topics != []:
                        self.cards.append(card)


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
        # TODO: make sure that medusa is a permissable state!!
        if "medusa" in self.applications:
            if self.query_terms.lower() in opendir(self.state.medusa.config, 'topics'):
                encyclopedia = MedusaCard('topics', self.query_terms.lower(), state=self.state.medusa, grab_body=True, search_result=True)
                self.cards.append(encyclopedia)

        for application in self.applications:
            app_state = getattr(self.state, application)

            # Other types of search results come afterwards
            for ctype in app_state.searchtypes:
                # Manage the encyclopedia cards separately
                if ctype == 'topics':
                    continue
                # Are we doing cardtype filtering, and this isn't an included card type?
                if app_state.exclude_cardtype(ctype) is True:
                    continue

                syslog.syslog("ctype: " + ctype + " filter: " + str(getattr(app_state, ctype).filtertype) + " card_filter_state: " + str(app_state.card_filter))
                start = 0
                end_dist = len(self.search_results.hits[ctype])
                # No results for this search type
                if end_dist == 0:
                    continue

                for j in xrange(start, end_dist):
                    grab_file = self.search_results.hits[ctype][j]
                    # If the hits[ctype][j] is a file name, figure out which Nth file this is
                    if grab_file.isdigit() is False:
                        for k in xrange(0, len(BaseFiles[ctype])):
                            # syslog.syslog("compare:" + grab_file + "==" + BaseFiles[ctype][k])
                            if BaseFiles[ctype][k] == grab_file:
                                grab_file = k
                                break

                    card = CardClass[application](ctype, grab_file, state=app_state, grab_body=True, search_result=True)
                    # News articles without topic strings won't load. Other card types that
                    # don't have embedded topics will load just fine.
                    if (card.topics != []) or (ctype == 'quotes') or (ctype == 'topics'):
                        self.cards.append(card)


    def __get_permalink_card(self):
        """
        Given a utime or card filename, return a permalink page of that type.
        """
        for application in self.applications:
            app_state = getattr(self.state, application)

            permalink_fields = [sv for sv in app_state.specials
                                if sv.find("permalink") != -1]
            for spcfield in permalink_fields:
                if getattr(app_state, spcfield) is not None:
                    # Permalink value is just a card name
                    cnum = str(getattr(app_state, spcfield))
                    # Insert a card after the first heading
                    ctype = spcfield.split("_")[0]
                    self.cards.append(CardClass[application](ctype, cnum, state=app_state, grab_body=True, permalink=True))


    def __get_prior_cards(self):
        """
        Describe all prior cards based on the state object
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
        card-type distances are properly represented.
        """
        # TODO: doesn't support zoo cards yet!
        news_items = int(self.state.medusa.news.count) * self.state.page

        # Then add the appropriate page count's worth of news
        for n in xrange(0, news_items):
            self.cards.append(MedusaCard('news', n, state=self.state.medusa, grab_body=False))

        # Now, for each card type, go back state.ctype.distance
        # and insert the run of that card type.
        # Guarantees the previous number of items on the page is
        # accurate, while not caring about where on the previous
        # pages those images might have been. It also preserves
        # the ordering of how those items appeared on the prev
        # page, which is important for once we've generated all
        # of this page's content and need to write a new state
        # variable based on the current list of cards.
        for ctype, card_count in self.state.medusa.config.items("card_counts"):
            # Are we doing cardtype filtering, and this isn't an included card type?
            if self.state.medusa.exclude_cardtype(ctype) is True:
                continue
            dist = getattr(self.state.medusa, ctype).distance
            if (len(getattr(self.state.medusa, ctype).clist) == 0) or (dist is None):
                continue
            # syslog.syslog("ctype, len, and dist: " + str(ctype) + " " + str(len(self.cards)) + " " + str(dist))
            put = len(self.cards) - 1 - int(dist)
            for cnum in getattr(self.state.medusa, ctype).clist:
                self.cards.insert(put, MedusaCard(ctype, cnum, state=self.state.medusa, grab_body=False))

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

        for application in self.applications:
            app_state = getattr(self.state, application)
            for ctype, spacing in app_state.config.items("card_spacing"):
                # Spacing rules from the last page. Subtract the distance from
                # the end of the previous page. For all other cards, follow the
                # strict card spacing rules from the config file, plus jitter
                spacing = int(spacing)
                distance = getattr(app_state, ctype).distance
                if distance is None:
                    distance = 0

                if distance >= spacing:   # Prev page ctype card not close
                    c_dist[ctype] = 0
                elif (lstop == 0) and (distance == 0):   # No pages yet
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
                if (ctype == 'news') or (ctype == 'topics'):
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
                if c_redist[ctype] == []:
                    continue   # Empty
                # Are we doing cardtype filtering, and this isn't an included card type?
                if app_state.exclude_cardtype(ctype) is True:
                    continue

                # Max distance between cards of this type on a page
                norm_dist = getattr(app_state, ctype).spacing
                # Number of input cards we're working with
                # (should never be more than getattr(self.state, ctype).count
                card_count = len(c_redist[ctype])
                # For spacing purposes, page starts at the earliest page we can
                # put a card on this page, w/o being too close to a same-type
                # card on the previous page. This shortens the effective page dist
                effective_pdist = p_dist - c_dist[ctype]
                max_dist = effective_pdist
                if card_count >= 1:
                    max_dist = floor(effective_pdist / card_count)

                # If less cards on the page then expected, degrade
                if max_dist < norm_dist:
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
                    if start_jrange >= end_jrange:
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
            if self.state.seed:
                seed(self.state.seed)

        # Lastly, add the topics cards back
        for j in xrange(0, len(c_nodist['topics'])):
            self.cards.insert(lstop + j, c_nodist['topics'][j])



def create_page(page):
    """Given a ConstantinaPage object, draw all the cards with content in
    them, Each card type has unique things it must do to process
    the data before it's drawn to screen.

    If a state is provided, return JSON-formatted data ready for
    insertion into the DOM. Otherwise, return the initial HTML.
    This is done with decorators for each of the card functions
    """
    output = ""
    total = len(page.cards)
    start_point = page.cur_len

    for i in xrange(start_point, total):
        if ((page.cards[i].ctype == "news") or
            (page.cards[i].ctype == "topics") or
            (page.cards[i].ctype == "features")):
            # TODO: export_display_state is gone, replaced by theme state
            output += create_medusa_textcard(page.cards[i], page.state.export_theme_state())

        if ((page.cards[i].ctype == "quotes") or
            (page.cards[i].ctype == "heading")):
            output += create_medusa_simplecard(page.cards[i], page.out_state, page.state.medusa)

        if (page.cards[i].ctype == "images"):
            output += create_medusa_imagecard(page.cards[i])

        if (page.cards[i].ctype == "songs"):
            output += create_medusa_songcard(page.cards[i])

    return output


def contents_page(start_response, state, headers):
    """
    Three types of states:
    1) Normal page creation (randomized elements)
    2) A permalink page (state variable has an x in it)
        One news or feature, footer, link to the main page
    3) Easter eggs
    """
    # TODO: add cookies as part of the start_response headers
    substitute = '<!-- Contents go here -->'

    # Read in headers from authentication if they exist
    headers.append(('Content-Type', 'text/html'))
    # syslog.syslog(str(headers))

    # Fresh new HTML, no previous state provided
    if state.fresh_mode() is True:
        page = ConstantinaPage(state)
        base = open(state.theme + '/contents.html', 'r')
        html = base.read()
        html = html.replace(substitute, create_page(page))
        start_response('200 OK', headers)

    # Permalink page of some kind
    elif state.permalink_mode() is True:
        page = ConstantinaPage(state)
        base = open(state.theme + '/contents.html', 'r')
        html = base.read()
        html = html.replace(substitute, create_page(page))
        start_response('200 OK', headers)

    # Did we get an empty search? If so, reshuffle
    elif state.reshuffle_mode() is True:
        syslog.syslog("***** Reshuffle Page Contents *****")
        state = ConstantinaState(None)
        page = ConstantinaPage(state)
        html = create_page(page)
        start_response('200 OK', headers)

    # Doing a search or a filter process
    elif state.search_mode() is True:
        page = ConstantinaPage(state)
        html = create_page(page)
        start_response('200 OK', headers)

    # Otherwise, there is state, but no special headers.
    else:
        page = ConstantinaPage(state)
        html = create_page(page)
        start_response('200 OK', headers)

    # Load html contents into the page with javascript
    return html


def application(env, start_response, instance="default"):
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
    root_dir = GlobalConfig.get("paths", "data_root") + "/public"
    os.chdir(root_dir)
    in_state = env.get('QUERY_STRING')
    syslog.syslog(str(env))
    if (in_state is not None) and (in_state != ''):
        # Truncate state variable at 512 characters
        in_state = in_state[0:512]
    else:
        in_state = None

    state = ConstantinaState(in_state)   # Create state object
    auth_mode = GlobalConfig.get("authentication", "mode")

    auth = authentication(env)
    if (auth_mode == "blog") or (auth_mode == "combined"):
        return contents_page(start_response, state, auth.headers)
    else:
        if auth.account.valid is True:
            return contents_page(start_response, state, auth.headers)
        else:
            return authentication_page(start_response, state)



# Allows CLI testing when QUERY_STRING is in the environment
# TODO: pass QUERY_STRING as a CLI argument
if __name__ == "__main__":
    stub = lambda a, b: a.strip()
    html_body = application(True, stub)
    print html_body
