from math import floor
from random import random, randint, seed, shuffle
from datetime import datetime
import os
import magic
from urllib import unquote_plus
import syslog
import ConfigParser

from constantina.shared import BaseFiles, BaseCardType, opendir

syslog.openlog(ident='constantina.zoo.cards')


class ZooThreadCardList:
    """
    Linear series of ZooPost cards. Arranged as threads, but appended in order
    as individual post cards prior to returning.
    """
    def __init__(self):
        pass


    def get(self, strategy):
        """
        Based on user preferences, get either all posts, or only the last N*10.
        """
        pass


    def ordering(self):
        """
        Set the M-of-N values in the threads so we can display how many posts are
        in a single thread.
        """
        pass


class ZooPostCard:
    """
    Since forum cards must track updatable state in each item, we don't load
    these as HTML fragments anymore, but as raw JSON documents.

    Constantina Forum Posts are written in a BBCode variant, and may contain
    a single attachment pointed at (images translated into attachments)
    """
    def __init__(self, ctype, num, state, grab_body=True, permalink=False, search_result=False):
        self.config = state.config

        self.title = self.config.get("card_defaults", "title")
        self.channel = self.config.get("card_defaults", "channel")
        self.body = self.config.get("card_defaults", "body")
        self.ctype = ctype
        # Request either the Nth entry of this type, or a specific date/utime
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
        Opens JSON file based on being Nth in the directory, parses, and adds meta.
        """
        # TODO: opendir supports paging now, but where does the page info come from?
        # The state of the page? Works, but not for permalinks.
        # For permalinks, take a requested file and just open it, bypassing opendir.
        # If the file doesn't exist, return a default/empty card.
        if (self.permalink is False):
            type_files = opendir(self.config, self.ctype, self.hidden)   # TODO: paging info
        else:
            type_files = [self.num]   # TODO: validate directory

        # TODO: copy medusa's logic for shuffle/hidden cards

        # News posts are utimes. Forum threads can be utime.revision.utime...
        # For permalink files, self.num should always be 0.
        which_file = self.num
        if which_file >= len(type_files):
            if self.num in type_files:
                which_file = type_files.index(self.num)
                self.num = which_file
            else:
                return "nofile"
        
        # syslog.syslog(str(type_files[which_file]))
        return self.__interpretfile(type_files[which_file])


    def __interpretfile(self, thisfile):
        """
        Validates that a single JSON file has all of the valid forum attributes.
        If it doesn't, close/ignore the file, and log the failure.
        """
        # Add the permalink (POST) link details (TODO: Zoo-State)

        card_root = GlobalConfig.get("paths", "data_root") + "/private"
        # TODO: where are these cards coming from?
        base_path = card_root + "/" + self.config.get("paths", self.ctype)

        fpath = base_path + "/" + thisfile
        if self.hidden is True:
            fpath = base_path + "/hidden/" + thisfile
        try:
            with open(fpath, 'r') as cfile:
                pass   # TODO: the attributes must be here
        # TODO: need forum test files to start writing/resting this code!!
        pass


    def __fresh_property(self):
        """
        If the post is less than a certain period old, add "fresh" attributes
        so that we can draw this card as a "freshly updated" card.
        """
        pass


    def __first_in_thread(self):
        """
        If the post has no indications it is in response to another post, add
        markup in the JSON that tells Constantina to draw this card in the base
        page as a "start of thread" card. Likely this will be called from the 
        Thread object.
        """
        pass


    def __revisions(self):
        """
        If this thread has been revised, include the list of revisions as part of
        the JSON for the single card, so that a user can select between them.
        """
        pass


    def __attachments(self):
        """
        Validate that the links to attachments hosted by the forum are stil valid.
        """
        pass


    def get(self):
        """
        Based on user preferences, grab a post file, and return the JSON contents in
        a card object.
        """
        pass
