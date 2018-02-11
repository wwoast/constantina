from math import floor
from random import random, randint, seed, shuffle
from mutagen.mp3 import MP3
from defusedxml.ElementTree import fromstring, tostring
from xml.sax.saxutils import unescape
from PIL import Image
from datetime import datetime
import os
import magic
from urllib import unquote_plus
import syslog
import ConfigParser

from constantina.shared import GlobalConfig, BaseFiles, BaseCardType, BaseState, count_ptags, opendir, unroll_newlines, escape_amp

syslog.openlog(ident='constantina.medusa.cards')


class MedusaCard:
    """
    Constantina is a single-page layout consisting of cards. For now
    it is also a single-column layout. A card may contain a news item,
    an image, a feature, a header/footer, an ad, or an embedded media
    link. We track whether the image or link may be duplicated within
    the card, as well as what its page index and type are.
    """
    def __init__(self, ctype, num, state, grab_body=True, permalink=False, search_result=False):
        self.config = state.config

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
        type_files = opendir(self.config, self.ctype, self.hidden)   # Sets BaseFiles

        # Find the utime value in the array if the number given isn't an array index.
        # If we're inserting cards into an active page, the state variable will be
        # given, and should be represented by a shuffled value.
        random_types = self.state.randomize

        # Even if we have cards of a type, don't run random-select logic if cards array is []
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
                type_files = opendir(self.config, self.ctype, self.hidden)
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
            try:
                which_file = type_files.index(self.num)
                self.num = which_file
            except IndexError:
                syslog.syslog("Card number \"" + str(self.num) + "\" is not a filename or an Nth file.")

        # syslog.syslog(str(type_files[which_file]))
        return self.__interpretfile(type_files[which_file])


    def __songfiles(self):
        """Create an array of song objects for this card"""
        for songpath in self.body.splitlines():
            card_root = GlobalConfig.get("paths", "data_root") + "/private"
            songpath = card_root + "/" + self.config.get("paths", "songs") + "/" + songpath
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

        card_root = GlobalConfig.get("paths", "data_root") + "/private"
        base_path = card_root + "/" + self.config.get("paths", self.ctype)
        fpath = base_path + "/" + thisfile
        if self.hidden is True:
            fpath = base_path + "/hidden/" + thisfile
            
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

        except IOError:        # File got moved in between dirlist caching and us reading it
            self.topics = []   # Makes the card go away if we had an error reading content
            return self.config.get("card_defaults", "file")

        if self.hidden is True:
            return self.config.get("paths", self.ctype) + "/hidden/" + thisfile
        else:
            return self.config.get("paths", self.ctype) + "/" + thisfile



class MedusaSong:
    """
    Basic grouping of song-related properties with a filename.
    Use mutagen to determine the length of each song that appears
    in the page itself.

    TODO: cache this data, so you don't need to load it on every page load!
    """
    def __init__(self, filename):
        self.songfile = filename
        self.songtitle = filename.split("/")[-1].replace(".mp3", "")
        audio = MP3(filename)
        time = audio.info.length
        minutes = time / 60
        seconds = time % 60
        self.songlength = str(int(minutes)) + ":" + str(int(seconds))
        songmb = os.path.getsize(filename) / 1048576.0
        self.songsize = "%.2f MB" % songmb


def create_medusa_simplecard(card, next_state, state):
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
    default_string = state.config.get("card_defaults", "tombstone")
    if card.title == default_string:
        output += """\n<p id="state">%s</p>""" % next_state

    output += """</div>\n"""
    return output


def create_medusa_textcard(card, display_state):
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
        output += """      <h2><a href="#%s" onclick="revealToggle('%s');">%s</a></h2>\n""" % (anchor, anchor, card.title)
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
        # Pass tags we don't care about
        if line.find('<img') != 0 and line.find('<p') != 0:
            output += line + "\n"
            continue

        # syslog.syslog(line)
        e = fromstring(escape_amp(line))
        if e.tag == 'img':
            if (line == first_line) and ('img' not in passed):
                # Check image size. If it's the first line in the body and
                # it's relatively small, display with the first paragraph.
                # Add the dot in front to let the URIs look absolute, but the
                # Python directories be relative to the image folder in the
                # private contents directory (not exposed when auth is used)
                img = Image.open("../private" + e.attrib['src'])
                if ((img.size[0] > 300) and
                    (img.size[1] > 220) and
                    (card.permalink is False) and
                    (card.search_result is False) and
                    (ptags >= 3)):
                    if 'class' in e.attrib:
                        e.attrib['class'] += " imgExpand"
                    else:
                        e.attrib['class'] = "imgExpand"

            elif ((ptags >= 3) and (card.permalink is False) and
                  (card.search_result is False)):
                # Add a showExtend tag to hide it
                if 'class' in e.attrib:
                    e.attrib['class'] += " imgExpand"
                else:
                    e.attrib['class'] = "imgExpand"
            else:
                pass

            # Track that we saw an img tag, and write the tag out
            output += unescape(tostring(e))
            passed.update({'img': True})

        elif e.tag == 'p':
            # If further than the first paragraph, write output
            if 'p' in passed:
                output += unescape(tostring(e))

            # If more than three paragraphs, and it's a news entry,
            # start hiding extra paragraphs from view
            elif ((ptags >= 3) and
                  (card.permalink is False) and
                  (card.search_result is False)):
                # First <p> is OK, but follow it with a (Read More) link, and a
                # div with showExtend that hides all the other elements
                read_more = """ <a href="#%s" class="showShort" onclick="revealToggle('%s');">(Read&nbsp;More...)</a>""" % (anchor, anchor)
                prep = unescape(tostring(e))
                output += prep.replace('</p>', read_more + '</p>')
                output += """<div class="divExpand">\n"""

            else:
                output += unescape(tostring(e))

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


def create_medusa_imagecard(card):
    """
    Pure image frames should be generated and inserted roughly
    3 per page of news items. Duplicates of images are OK, as long
    as we need to keep adding eye candy to the page.
    """
    anchor = card.cfile.split('/')[1]
    # Get URI absolute path out of a Python relative path
    uripath = "/" + "/".join(card.cfile.split('/')[0:])

    output = """<div class="card image" id="%s">\n""" % anchor
    output += """   <img src="%s" />\n""" % uripath
    output += """</div>\n"""
    return output


def create_medusa_songcard(card):
    """
    Song cards appear in two varieties -- one is made from a
    single MP3 file, and appears as a focal point. The other type
    appears as M3U playlist files, and result in multiple songs
    appearing in a single card list. The M3U version should be
    randomly sorted, and ideally has no more than 6 songs.
    """
    output = """<div class="card song">"""
    for song in card.songs:
        # Songs DIR can only be TLD, followed by album, and then songname
        uripath = "/" + "/".join(song.songfile.split("/")[-4:])

        output += """   <div class="cell">"""
        output += """      <p class="songName">%s</p>""" % song.songtitle
        output += """      <a href="%s">MP3 &darr; %s </a>""" % (uripath, song.songlength)
        output += """   </div>"""

    output += """</div>"""
    return output
