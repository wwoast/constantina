from math import floor
from random import random, randint, seed, shuffle
from datetime import datetime
import os
import magic
from urllib.parse import unquote_plus
import syslog
import configparser
import json

from constantina.shared import BaseFiles, BaseCardType, GlobalConfig, GlobalTime, opendir

syslog.openlog(ident='constantina.zoo.cards')


class ZooThreadCardGroup:
    """
    Linear series of ZooPostCardStacks (aka single cards, with revisions). Conceptually,
    it's the same as a linear series of posts, but where each post is an object that includes
    whatever revisions to that post exist.

    Arranged as threads, but appended in order as individual post cards prior to returning. 
    Each thread is its own JSON file, and the posts are arranged in linear oldest-to-newest order.

    Each object is initialized with a loading strategy for the posts to return. By default
    it's all_posts, but you can opt for next_N or last_N instead.
    """
    def __init__(self):
        self.config = state.config

        self.channel = self.config.get("card_defaults", "channel")
        self.poll = None
        self.pstacks = []
        self.title = self.config.get("card_defaults", "title")
    
        self.ctype = "threads_zoo"
        self.hidden = False
        # Request either the Nth entry of this type, or a specific date/utime
        self.num = None

        self.cfile = self.config.get("card_defaults", "file")
        self.cdate = self.config.get("card_defaults", "date")
        self.permalink = permalink
        self.search_result = search_result
        self.expand_mode = self.config.get("zoo", "expand_mode")
        self.expand_posts = self.config.get("zoo", "expand_posts")

    def get_thread(self, num, expand_mode, page):
        """
        Based on user preferences, get either all posts, or only the next/last N*10.
        If doing next_10 or last_10, track the page of data shown so that a cursor
        tracks which set of N posts to grab.
        """
        # 1. Open a thread file
        self.num = num
        self.__openfile()

        # 2. We have a JSON object with an entire thread of posts. Based on the expand_mode
        # and the page, only keep the posts desired (TODO: WRITE TESTS)
        self.__keep_desired_posts(expand_mode, page)

        # 3. In the JSON, also create the navigation cards to show or hide any
        # posts that are already shown. (ADDING CARDS)
        pass

    def create_thread(self, num, rawjson):
        """
        Start a new thread with filename "num".
        New threads should always have only a single post stack.
        """
        # Process the raw JSON as a single post.
        pass

    def append_thread(self, num, rawjson):
        """
        Append a post to the filename "num" at the end of its thread-stack.
        """
        # Process the raw JSON as a single post.
        pass

    def revise_thread(self, num, index, revision, rawjson):
        """
        For the thread with filename "num", find the post-stack at "index" and
        revise the "revision"th post in that stack.
        """
        # Process the raw JSON as a single post.
        pass

    def create_poll(self, num, rawjson):
        """
        The poll is stored in the thread metadata at the top level. When creating
        a thread, if poll data is detected, we create a poll instead.
        """
        # Process the raw JSON post-section as a post, and poll section as a poll.
        pass

    def revise_poll(self, num, rawjson):
        """
        Poll entries can be revised within the post edit window. Make sure this
        window has an upper limit
        """
        # Process raw JSON as poll-section. Cannot revise poll and post at the same time
        pass

    def __calculate_page_point(expand_mode, page):
        """
        Next or last N posts from the current page the browser is showing.
        Enforce paging policy based on zoo.ini:expand_posts (10 posts at a time).
        TODO: Last == last posts in thread, not previous!
        """
        direction = "next"
        count = self.expand_posts
        max = self.config.getint("zoo", "max_expand_posts")
        point = page * count
        try:
            (direction, count) = expand_mode.split("_")
            # Improper specified expand_mode return default first page point
            if direction != "previous" and direction != "next" and direction != "last" :
                raise ValueError
            # Page count can't be a silly number
            if count > max or count < 0:
                raise ValueError
            # Page count isn't consistent with the users' settings.
            if count % self.expand_posts != 0:
                raise ValueError 
        except ValueError:
            # No underscore in the split, or other format issues
            return 0

        # Assume "count" posts per page. Current browser-displayed page
        # point prior to new page load should be post-count * page number.
        return point
        
    def __keep_desired_posts(self, expand_mode, page):
        """
        Starting with an entire thread of posts, keep the ones that match the
        policy. If expand_mode is all_posts, that mean this is a no-op.
        """
        if (expand_mode == "all_posts"):
            return

        # Find the page-point in your threads based on. If page point is
        # zero, we can only get the next page of posts.
        point = self.__calculate_page_point(expand_mode, page)
        direction = self.expand_mode.split("_")[0]
        if (direction == "last"):
            pass
            # Get the last N posts in the thread
        elif (direction == "previous"):
            # From page point, get the previous N posts
            pass
        else:
            # Get the next N posts
            pass

        return



    def __interpretfile(self, thisfile):
        """
        File opening heuristics for threads.

        If a thread is a validly-formed JSON file that contains a title, channel,
        poll flag, and at least one valid post-stack, then it's a proper thread and
        should be displayed. Otherwise, log an error.
        """
        magi = magic.Magic(mine=True)
        raw = None

        card_root = GlobalConfig.get("paths", "data_root") + "/private"
        base_path = card_root + "/" + self.config.get("paths", self.ctype)
        fpath = base_path + "/" + thisfile
        if self.hidden is True:
            fpath = base_path + "/hidden/" + thisfile

        try:
            with open(fpath, 'r') as tfh:
                ftype = magi.from_file(fpath)
                # TODO: not a great way to read in and validate a JSON file.
                if ftype == "text/plain":
                    raw = json.loads(tfh.read())
                else:
                    return "nofile"
            
            # Look for thread-specific properties
            self.channel = raw['channel']
            self.poll = raw['poll']
            self.pstacks = raw['posts']
            self.title = raw['title']
             
        except:
            # TODO: handle keyerrors and file read errors here
            return "nofile"          
        
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

    def __ordering(self):
        """
        Set the M-of-N values in the threads so we can display how many posts are
        in a single thread.
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
    def __init__(self):
        self.posts = []

    def latest(self):
        """Return the latest revision of this post."""
        return self.posts[0]

    def pop(self):
        """
        Remove a card from the revision stack before returning it to a client.
        """
        pass

    def push(self, post):
        """
        Add a Zoo post card to a revision stack, in front of whatever earlier revisions
        were already found there.
        """
        self.posts.insert(0, post)

    def __validate(self):
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
    def __init__(self):
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

    def get_post(self, num, revision, permalink=False, search_result=False):
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

    def set_post(self, num, revision, json):
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

    def __interpretpost(self):
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

    def __validate(self):
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
