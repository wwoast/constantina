#!/usr/bin/env python

"""
YaBB to Zoo forum conversion tool
  Justin Fairchild, December 2016

Tested on YaBB 2.1, to convert their pipe-delimited forum thread flat-files
into a JSON format where the post metadata can be processed by the Zoo server
software in a cleaner way.
"""

import os
import json

# Forum .txt files to read from, and a dict for them to live in
YABB_FORUMS = [ "abuse", "family", "fhanime", "general", "scrabble" ]
YABB_ORDER = {}
YABB_MEMBER = {}

# Directories
YABB_BOARDDIR = "./Boards"
YABB_MSGDIR = "./Messages"
JSON_OUTDIR = "./zoo"


class zoo_post:
   """
   Individual forum post object
      pipe-delimited line => single JSON post object
   """

   def __init__(self, input_line):
      self.body = []

      values = input_line.split("|")
      self.author = values[1]
      self.revision = 0   ## Reset revision counts from YaBB until I know how they work TODO
      self.processBody(values[-5])

   def processBody(self, message):
      """
      Takes a single post line and converts it to a JSON object as follows:
         * Lines of text separated by <br /><br /> become <p> entries.
         * TODO: OTHERS
         * TODO: most efficient object representation of JSON in Python
      """
      lines = message.split('<br /><br />')
      lines = [ l for l in lines if l != "" ]
      for line in lines:
         ## Make body.p objects for lines. TODO: Look for other types
         self.body.append({'p': { "contents": line, "class": "" }})

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
            self.posts.append(zoo_post(line))

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
