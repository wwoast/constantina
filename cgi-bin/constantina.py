from math import floor
from random import random, randint, seed
from PIL import Image
from datetime import datetime
import os
from sys import stdin
import lxml.html
import syslog
import ConfigParser

from constantina_shared import BaseFiles, opendir, unroll_newlines
from constantina_state import ConstantinaState
from medusa_cards import MedusaCard, MedusaSong
from medusa_search import MedusaSearch

syslog.openlog(ident='constantina')
# TODO: get rid of this somehow!
CONFIG = ConfigParser.SafeConfigParser()
CONFIG.read('constantina.ini')


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
            if ((self.state.max_items - self.filtered) * (self.state.page + 1) <= len(self.cards)):
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
        for application in CONFIG.get("applications", "enabled").replace(" ", "").split(","):
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
                    card = MedusaCard(ctype, i, state=app_state, grab_body=True)
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
        if "medusa" in CONFIG.get("applications", "enabled").replace(" ","").split(","):
            if self.query_terms.lower() in opendir(self.state.medusa.config, 'topics'):
                encyclopedia = MedusaCard('topics', self.query_terms.lower(), state=self.state.medusa, grab_body=True, search_result=True)
                self.cards.append(encyclopedia)

        for application in CONFIG.get("applications", "enabled").replace(" ", "").split(","):
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

                    card = MedusaCard(ctype, grab_file, state=app_state, grab_body=True, search_result=True)
                    # News articles without topic strings won't load. Other card types that
                    # don't have embedded topics will load just fine.
                    if (card.topics != []) or (ctype == 'quotes') or (ctype == 'topics'):
                        self.cards.append(card)


    def __get_permalink_card(self):
        """
        Given a utime or card filename, return a permalink page of that type.
        """
        for application in CONFIG.get("applications", "enabled").replace(" ", "").split(","):
            app_state = getattr(self.state, application)
        
            permalink_fields = [sv[1] for sv in appstate.specials
                                if sv[1].find("permalink") != -1]
            for spcfield in permalink_fields:
                if getattr(app_state, spcfield) is not None:
                    cnum = str(getattr(app_state, spcfield))   # TODO document. wtf?
                    # Insert a card after the first heading
                    ctype = spcfield.split("_")[0]
                    self.cards.append(MedusaCard(ctype, cnum, state=app_state, grab_body=True, permalink=True))


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
        news_items = int(self.state.medusa.news.count) * self.state.page 

        syslog.syslog("news_items: " + str(news_items))
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
        syslog.syslog("cur_len: " + str(self.cur_len))


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

        for application in CONFIG.get("applications", "enabled").replace(" ","").split(","):
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


def create_simplecard(card, next_state):
    """
    Simple cards with only basic text and images are drawn here.
    This includes all card.heading and card.quotes, but possibly
    others as well. Do not apply any special logic to these cards --
    just get them drawn, whatever tags they might contain.
    """
    anchor = card.cfile.split('/').pop()

    output = ""
    output += """<div class="card %s" id="%s">\n""" % (card.ctype, anchor)

    body_lines = card.body.splitlines()
    processed_lines = unroll_newlines(body_lines)

    for line in processed_lines:
        output += line + "\n"

    # For special tombstone cards, insert the state as non-visible text
    default_string = CONFIG.get("card_defaults", "tombstone")
    if card.title == default_string:
        output += """\n<p id="state">%s</p>""" % next_state

    output += """</div>\n"""
    return output


def create_textcard(card, display_state):
    """
    All news and features are drawn here. For condensing content,
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
        if topic_header == "":
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
    output += """<div class="card %s" id="%s">\n""" % (card.ctype, anchor)
    output += """   <div class="cardTitle">\n"""
    if card.permalink is True:
        output += """      <h2>%s</h2>\n""" % card.title
        output += """      <p class="subject">%s</p>\n""" % card.cdate
    else:
        output += """      <h2><a href="#%s" onclick="cardToggle('%s');">%s</a></h2>\n""" % (anchor, anchor, card.title)
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
        if e.tag == 'img':
            if (line == first_line) and ('img' not in passed):
                # Check image size. If it's the first line in the body and
                # it's relatively small, display with the first paragraph.
                # Add the dot in front to let the URIs be absolute, but the
                # Python directories be relative to CWD
                img = Image.open("." + e.attrib['src'])
                # TODO: am I really an image? Have a bg script tell you
                if ((img.size[0] > 300) and
                    (img.size[1] > 220) and
                    (card.permalink is False) and
                    (card.search_result is False) and
                    (ptags >= 3)):
                    e.attrib.update({"id": "imgExpand"})
            elif ((ptags >= 3) and (card.permalink is False) and
                  (card.search_result is False)):
                # Add a showExtend tag to hide it
                e.attrib.update({"id": "imgExpand"})
            else:
                pass

            # Track that we saw an img tag, and write the tag out
            output += lxml.html.tostring(e)
            passed.update({'img': True})

        elif e.tag == 'p':
            # If further than the first paragraph, write output
            if 'p' in passed:
                output += lxml.html.tostring(e)
            # If more than three paragraphs, and it's a news entry,
            # and if the paragraph isn't a cute typography exercise...
            # start hiding extra paragraphs from view
            elif len(e.text_content()) < 5:
                output += lxml.html.tostring(e)
                continue   # Don't mark as passed yet

            elif ((ptags >= 3) and
                  (card.permalink is False) and
                  (card.search_result is False)):
                # First <p> is OK, but follow it with a (Read More) link, and a
                # div with showExtend that hides all the other elements
                read_more = """ <a href="#%s" class="showShort" onclick="cardToggle('%s');">(Read&nbsp;More...)</a>""" % (anchor, anchor)
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
    if ((ptags >= 3) and
        (card.permalink is False) and
        (card.search_result is False)):
        output += """   </div>\n"""

    # Convert the appearance value into a string for permalinks
    # And close the textcard
    if display_state is not None:
        permanchor = "/?x" + card.ctype[0] + anchor + ":" + display_state
    else:
        permanchor = "/?x" + card.ctype[0] + anchor

    if card.permalink is False:
        output += """   <div class="cardFooter">\n"""
        output += """      <div class="bottom">\n"""
        output += """         <p class="cardNav"><a href="%s">Permalink</a></p>\n""" % permanchor
        output += """         <p class="postDate">%s</p>\n""" % card.cdate
        output += """      </div>\n"""
        output += """   </div>\n"""

    output += """</div>\n"""
    return output


def create_imagecard(card):
    """
    Pure image frames should be generated and inserted roughly
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
    """
    Song cards appear in two varieties -- one is made from a
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
        output += """      <a href="%s">MP3 &darr; %s </a>""" % (uripath, song.songlength)
        output += """   </div>"""

    output += """</div>"""
    return output


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
            output += create_textcard(page.cards[i], page.state.export_theme_state())

        if ((page.cards[i].ctype == "quotes") or
            (page.cards[i].ctype == "heading")):
            output += create_simplecard(page.cards[i], page.out_state)

        if (page.cards[i].ctype == "images"):
            output += create_imagecard(page.cards[i])

        if (page.cards[i].ctype == "songs"):
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
    start_response('200 OK', [('Content-Type', 'text/html')])
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

    # Fresh new HTML, no previous state provided
    if state.fresh_mode() is True:
        page = ConstantinaPage(state)
        base = open(state.theme + '/contents.html', 'r')
        html = base.read()
        html = html.replace(substitute, create_page(page))
        start_response('200 OK', [('Content-Type', 'text/html')])

    # Permalink page of some kind
    elif state.permalink_mode() is True:
        page = ConstantinaPage(state)
        base = open(state.theme + '/contents.html', 'r')
        html = base.read()
        html = html.replace(substitute, create_page(page))
        start_response('200 OK', [('Content-Type', 'text/html')])

    # Did we get an empty search? If so, reshuffle
    elif state.reshuffle_mode() is True:
        syslog.syslog("***** Reshuffle Page Contents *****")
        state = ConstantinaState(None)
        page = ConstantinaPage(state)
        html = create_page(page)
        start_response('200 OK', [('Content-Type', 'text/html')])

    # Doing a search or a filter process
    elif state.search_mode() is True:
        page = ConstantinaPage(state)
        html = create_page(page)
        start_response('200 OK', [('Content-Type', 'text/html')])

    # Otherwise, there is state, but no special headers.
    else:
        page = ConstantinaPage(state)
        html = create_page(page)
        start_response('200 OK', [('Content-Type', 'text/html')])

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
            [key, value] = vals.split('=')
            post[key] = value

    if (post['username'] == "justin") and (post['password'] == "justin"):
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
    os.chdir(root_dir)
    in_state = os.environ.get('QUERY_STRING')
    if (in_state is not None) and (in_state != ''):
        # Truncate state variable at 512 characters
        in_state = in_state[0:512]
    else:
        in_state = None

    state = ConstantinaState(in_state)   # Create state object
    auth_mode = CONFIG.get("authentication", "mode")

    if os.environ.get('REQUEST_METHOD') == 'POST':
        if authentication() is True:
            return contents_page(start_response, state)
        else:
            return authentication_page(start_response, state)

    if (auth_mode == "blog") or (auth_mode == "combined"):
        return contents_page(start_response, state)
    else:
        return authentication_page(start_response, state)



# Allows CLI testing when QUERY_STRING is in the environment
# TODO: pass QUERY_STRING as a CLI argument
if __name__ == "__main__":
    stub = lambda a, b: a.strip()
    html = application(True, stub)
    print html
