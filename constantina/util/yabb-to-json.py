#!/usr/bin/env python3

"""
YaBB to Zoo forum conversion tool
  Justin Fairchild, December 2016

Tested on YaBB 2.1, to convert their pipe-delimited forum thread flat-files
into a JSON format where the post metadata can be processed by the Zoo server
software in a cleaner way. 

In normal Zoo forum posts, we don't convert any [PRE]/[URL]/:smiley tags prior
to displaying content. This is because if a post is user-modifiable, we want to
preseve the exact contents of the original forum post, as written. However, 
when migrating YaBB posts, we assume that no posts are in this modifiable state
and thus we write the bulletin-board translations out explicitly.
"""

import os
import json
import re

# Forum .txt files to read from, and a dict for them to live in
YABB_FORUMS = [ "abuse", "family", "fhanime", "general", "scrabble" ]
YABB_ORDER = {}
YABB_MEMBER = {}

# Directories
YABB_BOARDDIR = "./Boards"
YABB_MSGDIR = "./Messages"
YABB_ATTACHMENTS = "./yabbfiles/Attachments"
JSON_OUTDIR = "./zoo/messages"
ATTACHMENTS_OUTDIR = "./zoo/uploads"
SMILIES_DIR = "images/smilies"

# Block elements
YABB_BLOCK = ['pre', 'code', 'quote']

# Smilies and URL elements are all inline
YABB_INLINE = ['smiley', 'smilie', 'url']
YABB_SMILIES = {	
    # ;), ;-)
       "wink": [re.compile(r'(\W|\A)\;\)'), re.compile(r'(\W|\A)\;-\)')],
    # ;D, ;-D
       "grin": [re.compile(r'(\W|\A)\;D'), re.compile(r'(\W|\A)\;-D')],
        # :'(
        "cry": [re.compile(re.escape(r":'("))],
    # :/, :-/
  "undecided": [re.compile(r'(\W|\A)\:\/'), re.compile(r'(\W|\A)\:-\/')],
        # :-X
"lipsrsealed": [re.compile(re.escape(r":-X"))],
        # :-[
 "embarassed": [re.compile(re.escape(r":-["))],
        # :-*
       "kiss": [re.compile(re.escape(r":-*"))],
        # >:(
      "angry": [re.compile(re.escape(r"&gt;:("))],
        # ::)
   "rolleyes": [re.compile(re.escape(r"::)"))],
         # :P
     "tongue": [re.compile(re.escape(r":P"))],
    # :), :-)
     "smiley": [re.compile(re.escape(r":)")), re.compile(re.escape(r":-)"))],
         # :D
     "cheesy": [re.compile(re.escape(r":D"))],
    # :(, :-(
        "sad": [re.compile(re.escape(r":(")), re.compile(re.escape(r":-("))],
         # :o
    "shocked": [re.compile(re.escape(r":o"))],
        # 8-)
       "cool": [re.compile(re.escape(r"8-)"))],
        # :-?
        "huh": [re.compile(re.escape(r":-?"))],
        # ^_^
      "happy": [re.compile(re.escape(r"^_^"))],
  # thumbs up
   "thumbsup": [re.compile(re.escape(r":thumb:"))],
       # >:-D
       "evil": [re.compile(re.escape(r"&gt;:-D"))]
}


class zoo_post:
   """
   Individual forum post object
      pipe-delimited line => single JSON post object
   """
   def __init__(self, input_line):
      values = input_line.split("|")
      self.author = values[1]
      self.revision = 0         # Reset revision counts from YaBB until I know how they work TODO
      # self.raw = values[-5]   # Don't keep raw data since none of these posts are modifiable
      self.date = values[3]
      self.html = self.processCode(values[-5])

      # For now, don't process the attachments out of the yabbfiles dir
      # Just make a note in the JSON so we can make the requests work later
      if ( values[-1] != '' ):
         self.attachment = values[-1]

   def processCode(self, text):
      """
      Takes a forum posting and converts any nested [SQUAREBRACKET] expressions
      into their equivalent HTML statements. 
      """
      text = self.processBlock(text)
      text = self.processInline(text)
      return text      

   def processBlock(self, text):
      """Process elements that make blocks of text in the final thread"""
      wrap = {
         "code": [ r'<p class="code">', r'</p>'],
         "quote": [ r'<p class="quote">', r'</p>'],
         "pre": [ r'<pre>', r'</pre>' ]
      }
      output = text
      for block in YABB_BLOCK:
         # support start tag with a single possible "author=username" section.
         # then match all text in between the square brackets that doesn't
         # match the end-tag. \s\S is required to match across newlines.
         # NOTE: this doesn't support nested [QUOTE][QUOTE][/QUOTE][/QUOTE]. 
         #   Make sure all posts you're copying from YaBB have been "unrolled"
         pattern = re.compile(r'\[' + block + r'(?:\s*(\w+)\=(\S+)\s?)*\]((?:(?!\[\/' + block + r'\])[\s\S])*)\[/' + block + r'\]', re.IGNORECASE)
         matchsets = re.findall(pattern, text)
         for m in matchsets:
            # group 0 is always keyword (author), group1 is always the username (TODO: include)
            # group 2 is always the contents in between the square brackets
            html = wrap[block][0] + m[2] + wrap[block][1]
            output = re.sub(pattern, html, output, 1)

      # TODO: sanitize out HTML from inside these blocks
      return output

   def processInline(self, text):
      """
      Any messages' block elements that can have inline smilies or URLs should
      be processed here. Start by processing smilies, and then process URLs.
      """
      wrap = {
         "smiley": [r'<img class="smiley" src=' + SMILIES_DIR + "/", r' />'],
            "url": [r'<a href="', r'">', r'</a>']
      }
      output = text
      for smiley_name, patterns in YABB_SMILIES.items():
         for pattern in patterns:
            matchsets = re.findall(pattern, text)
            for m in matchsets:
               html = wrap["smiley"][0] + smiley_name + '.gif"' + wrap["smiley"][1]
               output = re.sub(pattern, html, output)
      for inline in YABB_INLINE:
         if (( inline == "smilie" ) or ( inline == "smiley" )):
            pattern = re.compile(r'\[' + inline + r'\=(\w+)\.(\w+)\]', re.IGNORECASE)
            matchsets = re.findall(pattern, text)
            for m in matchsets:
               html = wrap["smiley"][0] + m[0] + "." + m[1] + wrap["smiley"][1]
               output = re.sub(pattern, html, output)
               break   # All smilies of a type are the same
         elif ( inline == "url" ):
            pattern = re.compile(r'\[' + inline + r'\=([^\]]*)\]([^\[]*)\[/' + inline + '\]', re.IGNORECASE)
            matchsets = re.findall(pattern, text)
            for m in matchsets:
               html = wrap[inline][0] + m[0] + wrap[inline][1] + m[1] + wrap[inline][2]
               output = re.sub(pattern, html, output, 1)

      return output 

   def to_JSON(self):
      return json.dumps(self, default=lambda o: o.__dict__, indent=2, ensure_ascii=False)


class zoo_poll:
   """
   Individual poll object that's part of a thread. 
      .poll/.polled => something rolled into a post
   """
   def __init__(self, file_prefix):
      with open(YABB_MSGDIR + "/" + file_prefix + ".poll", 'r') as pfh:
         body = pfh.read().splitlines()
         values = body[0].split("|")
         self.question = values[0]
         self.options = []

         body.remove(body[0])
         for idx, line in enumerate(body):
            self.options.append({})
            self.options[idx]['choice'] = line.split("|")[1]
            self.options[idx]['voter'] = []

         # YaBB is either multi-vote or single vote. 
         # Zoo is "number of choices" vote.
         if ( values[-5] == 0 ):
            self.polltype = 1
         else:
            self.polltype = len(self.options)

      with open(YABB_MSGDIR + "/" + file_prefix + ".polled", 'r' ) as qfh:
         body = qfh.read().splitlines()
         for line in body:
            values = line.split("|")
            voter = values[1]
            choices = values[2].split(',')   # Poll can have multiple choices
            for choice in choices:
               choice_idx = int(choice)
               self.options[choice_idx]['voter'].append(voter)

   def to_JSON(self):
      return json.dumps(self, default=lambda o: o.__dict__, indent=2, ensure_ascii=False)


class zoo_thread:
   """Individual forum thread object. .txt => .json"""

   def __init__(self, input_file):
      self.posts = []
      self.poll = None

      # Use YaBB forum lookup to set channel
      lookup = input_file.split("/")[-1].split('.')[0]
      self.channel = "#" + YABB_MEMBER[lookup]

      self.pollProcess(lookup)

      with open(YABB_MSGDIR + "/" + input_file, 'r') as rfh:
         body = rfh.read().splitlines()
         values = body[0].split("|")
         self.title = values[0]

         for line in body:
            # Each post is a potential array of revised posts.
            self.posts.append([zoo_post(line)])

   def pollProcess(self, file_prefix):
      """If .poll and .polled files exist, roll them into the post JSON"""
      test_path = YABB_MSGDIR + "/" + file_prefix + ".poll"
      if os.path.exists(YABB_MSGDIR + "/" + file_prefix + ".poll"):
         self.poll = zoo_poll(file_prefix)

   def to_JSON(self):
      return json.dumps(self, default=lambda o: o.__dict__, indent=2, ensure_ascii=False)


def read_zoo_forum():
   """
   Load the YaBB forum list files, to learn which forum post lives in
   which forum. This data will live in each forum post.
   """
   for forum in YABB_FORUMS:
      with open(YABB_BOARDDIR + "/" + forum + ".txt", 'r') as ffh:
         body = ffh.read().splitlines()
         YABB_ORDER[forum] = []
         for line in body:
            thread_id = line.split('|')[0]
            YABB_ORDER[forum].append(thread_id)
            YABB_MEMBER[thread_id] = forum


def all_zoo_threads():
   """Determine the entire list of thread files for conversion"""
   dirlisting = os.listdir(YABB_MSGDIR)
   
   threads = [ f for f in dirlisting if ".txt" in f ]

   if not os.path.exists(JSON_OUTDIR):
      os.makedirs(JSON_OUTDIR)

   for input_file in threads:
      thread = zoo_thread(input_file)
      output_file = input_file.split("/")[-1].replace(".txt", ".json")
      with open(JSON_OUTDIR + "/" + output_file, 'w') as wfh:
         wfh.write(thread.to_JSON())


def main():
   # Load list of files per forum
   read_zoo_forum()

   # Start converting all the threadfiles
   # Load all .txt files in YABB_MSGDIR
   all_zoo_threads()


if __name__ == '__main__': main()   
