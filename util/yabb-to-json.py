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
      .ctb/.poll/.polled => something rolled into a post
   """
   
   def __init__(self, input_file):
      self.polltype = 1
      self.question = None
      self.body = []
      pass   ## TODO: has to read multiple yabb input files

   def to_JSON(self):
      return json.dumps(self, default=lambda o: o.__dict__, indent=2, ensure_ascii=False)


class zoo_thread:
   """Individual forum thread object. .txt => .json"""

   def __init__(self, input_file):
      self.posts = []

      # Use YaBB forum lookup to set channel
      lookup = input_file.split("/")[-1].split('.')[0]
      self.channel = "#" + YABB_MEMBER[lookup]

      with open(YABB_MSGDIR + "/" + input_file, 'r') as rfh:
         body = rfh.read().splitlines()
         values = body[0].split("|")
         self.title = values[0]

         for line in body:
            self.posts.append(zoo_post(line))

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
   # polls = [ p for p in dirlisting if ".poll" in p ]

   if not os.path.exists(JSON_OUTDIR):
      os.makedirs(JSON_OUTDIR)

   for input_file in threads:
      thread = zoo_thread(input_file)
      output_file = input_file.split("/")[-1].replace(".txt", ".json")
      with open(JSON_OUTDIR + "/" + output_file, 'w') as wfh:
         wfh.write(thread.to_JSON())

   # TODO: write logic for dealing with polls too


def main():
   # Load list of files per forum
   read_zoo_forum()

   # Start converting all the threadfiles
   # Load all .txt files in YABB_MSGDIR
   all_zoo_threads()


if __name__ == '__main__': main()   
