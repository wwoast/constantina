from math import floor
from random import random, randint, seed, shuffle
from mad import MadFile
from datetime import datetime
import os
import magic
from urllib import unquote_plus
import syslog
import ConfigParser

from constantina_shared import GlobalConfig, BaseFiles, BaseCardType, BaseState, opendir

syslog.openlog(ident='medusa_cards')


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
        type_files = opendir(self.config, self.ctype, self.hidden)

        # Find the utime value in the array if the number given isn't an array index.
        # If we're inserting cards into an active page, the state variable will be
        # given, and should be represented by a shuffled value.
        random_types = self.state.randomize

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
