from math import floor
from random import random, randint, seed, shuffle
from datetime import datetime
import os
import magic
from urllib import unquote_plus
import syslog
import ConfigParser
import json

from constantina.shared import BaseFiles, BaseCardType, opendir

syslog.openlog(ident='constantina.zoo.cards')


class ZooThreadCardGroup:
    """
    Linear series of ZooPost cards. Arranged as threads, but appended in order
    as individual post cards prior to returning. Each thread is its own JSON file,
    and the posts are arranged in linear oldest-to-newest order.
    """
    def __init__(self):
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

    
    def __openfile(self):
        """
        Opens JSON file based on being Nth in the directory and parses it into a group
        of post cards.
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


class ZooPostCardGroup:
    """
    Zoo Posts may be updated or revised. When they are, track the revisions
    as post cards that are members of a ZooPostCardGroup.
    """
    def __init__(self, num, state, body=None, permalink=False, search_result=False):
        pass


class ZooPostCard:
    """
    Since forum cards must track updatable state in each item, we don't load
    these as HTML fragments anymore, but as raw JSON documents.

    Constantina Forum Posts are JSON objects. The body of the post itself is 
    written in a BBCode variant, and may contain a single attachment link such
    as an image, video, or song file that is uploaded to the forum.
    """
    def __init__(self, num, revision=None, state, body=None, permalink=False, search_result=False):
        self.config = state.config
        self.body = self.config.get("card_defaults", "body")

        # Request the Nth post in this thread. If there are revisions, request the specific
        # revision for that Nth number, which has a "duplicate" for each revision. If no
        # revision is provided, find the highest revision number and display that.
        self.num = num
        self.revision = revision

        self.songs = []
        self.cfile = self.config.get("card_defaults", "file")
        self.cdate = self.config.get("card_defaults", "date")
        self.body = body
        self.permalink = permalink
        self.search_result = search_result
        if self.body != None:
            self.__interpretpost()


    def __interpretpost(self):
        """
        Validates that a single JSON post has all of the valid forum attributes.
        If it doesn't, close/ignore the file, and log the failure.
        """
        self.revision = self.body.revision
        self.author = self.body.author
        self.date = self.body.date
        self.html = self.body.html
        # TODO: Sanity checks for revision number domain, author strings, dates, and post size.
        # TODO: Tag the post as fresh for styling


    def __fresh_property(self):
        """
        If the post is less than a certain period old, add "fresh" attributes
        so that we can draw this card as a "freshly updated" card.

        This property is added to the card prior to sending to the web client,
        and never stored on disk. It applies either if the thread got a recent post,
        or if the post itself is recent.
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
