from math import floor
from random import random, randint, seed, shuffle
from datetime import datetime
import os
import magic
from urllib import unquote_plus
import syslog
import ConfigParser
import json

from constantina.shared import BaseFiles, BaseCardType, GlobalTime, opendir

syslog.openlog(ident='constantina.zoo.cards')


class ZooThreadCardGroup:
    """
    Linear series of ZooPostCardStacks (aka single cards, with revisions). Conceptually,
    it's the same as a linear series of posts, but where each post is an object that includes
    whatever revisions to that post exist.

    Arranged as threads, but appended in order as individual post cards prior to returning. 
    Each thread is its own JSON file, and the posts are arranged in linear oldest-to-newest order.
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

        # Forum threads are utimes. Select either by Nth file in directory,
        # or by a valid utime.
        which_file = self.num
        if which_file >= len(type_files):
            if self.num in type_files:
                which_file = type_files.index(self.num)
                self.num = which_file
            else:
                return "nofile"
        
        # syslog.syslog(str(type_files[which_file]))
        return self.__interpretfile(type_files[which_file])

    def __interpretfile(self):
        """
        If a thread is a validly-formed JSON file that contains a title, channel,
        poll flag, and at least one valid post-stack, then it's a proper thread and
        should be displayed. Otherwise, log an error.
        """
        pass

    def __valid_channel(self):
        """
        Is the channel valid?
        """
        pass
    
    def __valid_title(self):
        """
        Is the post title valid, or is it too long? If too long, what do we do?
        Chop off the extra bits perhaps?
        """
        pass



class ZooPostCardStack:
    """
    Zoo Posts may be updated or revised. When they are, track the revisions
    as post cards that are members of a ZooPostCardStack.
    """
    def __init__(self, num, state, body=None, permalink=False, search_result=False):
        self.posts = []

    def push(self, post):
        """
        Add a Zoo post card to a revision stack, in front of whatever earlier revisions
        were already found there.
        """
        self.posts.insert(0, post)

    def latest(self):
        """Return the latest revision of this post."""
        return self.posts[0]

    def validate(self):
        """
        If the posts array is non-empty, and each post parses its own ZooPostCard logic
        correctly, then the Stack of Revisions is also valid.
        """
        if self.posts == []:
            return False

        for post in self.posts:
            if post.validate() != True:
                return False

        return True



class ZooPostCard:
    """
    Since forum cards must track updatable state in each item, we don't load
    these as HTML fragments anymore, but as raw JSON documents.

    Constantina Forum Posts are JSON objects. The body of the post itself is 
    written in a BBCode variant, and may contain a single attachment link such
    as an image, video, or song file that is uploaded to the forum.

    Dates are just unix times, configurable with timezone values from a user's
    browser.

    Similar to ConstantinaAuth, the modes are handled in the initialization
    routine, and the process for setting or getting a post follows, utilizing all
    of the same validation functions and default settings.
    """
    def __init__(self, process, **kwargs):
        # Set defaults that will apply if one of the validated details doesn't work
        self.body = self.config.get("card_defaults", "body")

        # Does the processed post data conform to policy? If not, don't complete
        # whatever the process action is.
        self.valid = False

        # The file path that the JSON is read from
        self.cfile = None

        # The raw JSON post file itself, and the JSON-parsed body.
        self.json = None
        self.body = None
        self.revision = 0

        self.songs = []
        self.cfile = self.config.get("card_defaults", "file")
        self.cdate = self.config.get("card_defaults", "date")
        # TODO: all the post values that we care about

        if process == "read":
            self.get_post(**kwargs)
        elif process == "write":
            self.set_post(**kwargs)
        elif process = "revise":
            self.revise_post(**kwargs)
        else:
            pass

    def __interpretpost(self, process="read"):
        """
        Validates that a single JSON post has all of the valid forum attributes.
        If it doesn't, close/ignore the file, and log the failure.

        For read-mode post interpreting, any username already written to disk is
        valid. For write-mode post interpreting, the JSON will have to match the
        username in the auth cookie. 
        """
        self.revision = self.body["revision"]
        self.author = self.body["author"]
        self.date = self.body["date"]
        self.html = self.body["html"]
        # Sanity checks for revision number domain, author strings, dates, and post size.
        self.valid = self.validate()
        # Tag the post as fresh for styling
        self.__fresh_property()

    def __fresh_property(self):
        """
        If the post is less than a certain period old, add "fresh" attributes
        so that we can draw this card as a "freshly updated" card.

        This property is added to the card prior to sending to the web client,
        and never stored on disk. It applies either if the thread got a recent post,
        or if the post itself is recent.
        """
        fresh_time = GlobalTime - self.config.getint("zoo", "fresh_window")
        if self.date > fresh_time:
            self.fresh = True
        else:
            self.fresh = False

    def __attachments(self):
        """
        Validate that the links to attachments hosted by the forum still meet policy
        and still exist on disk.
        """
        pass

    def __consistent_username(self, account):
        """
        Check if the username token in the post matches the username from the
        account state.
        """
        if (account.valid == True and self.username == account.username):
            return True
        else:
            return False

    def validate(self):
        """
        Check whether properties of this post object are valid or follow the
        configured Zoo policies. This includes sanity checks for revision number 
        domain, author strings, dates, and post size.
        """
        if not (self.revision >= 0 and self.revision <= 2**32-1):
            return False
        if type(self.date) != int:
            # Post dates are unix times
            return False
        # TODO: check that it's a valid username (length mins and max)
        # TODO: check post size and attachment size
        return True

    def get_post(self, num, revision=0, state, permalink=False, search_result=False):
        """
        Based on user preferences, grab a thread file, and return the JSON contents for
        this particular card object.
        """
        # Request the Nth post in this thread. If there are revisions, request the specific
        # revision for that Nth number, which has a "duplicate" for each revision. If no
        # revision is provided, find the highest revision number and display that.
        self.num = num
        self.revision = revision

        # Modes that will influence how this post is viewed
        self.permalink = permalink
        self.search_result = search_result
        
        # Read in the post itself
        self.cfile = "TODO"   # Build from the revision and num
        with open(filepath, 'r') as rfh:
            self.json = rfh.read()
            self.body = json.loads(self.json)

        # TODO: convert read-in JSON values to possible parameters for interpret/validate
        self.__interpretpost()

        if self.valid == False:
            # Either the number or the revision requested were invalid. Instead of
            # returning the post itself baked into the page, return an error.
            pass

    def set_post(self, num, revision=0, state, json):
        """
        Given inputs from a client, validate that all of the submitted info is correct and
        consistent with the authentication token.
        """
        self.json = json
        # TODO: try-catch, since this json is untrusted input!
        self.body = json.loads(self.json)

        self.cfile = "TODO"   # Build from the revision and num
        # TODO: convert read-in JSON values to possible parameters for interpret/validate
        self.__interpretpost()

        if self.valid == True:
            # Write the JSON to a file. Not the final location, but one where an event queue
            # can move the file into its final place "atomically"
            pass
        else:
            # Return some kind of useful error page
            pass
