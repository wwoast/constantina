#!/usr/bin/python
"""
Run this script from cgi-bin, and it will create the search indexes
if they don't exist, and do a search for the term "Constantina".
"""

from os import chdir
from constantina import cw_search
import ConfigParser

CONFIG = ConfigParser.SafeConfigParser()
CONFIG.read('constantina.ini')

ROOT_DIR = CONFIG.get("paths", "root")
RESOURCE_DIR = CONFIG.get("paths", "resource")

chdir(ROOT_DIR + "/" + RESOURCE_DIR)

# one page, 20 results per page, search for Constantina, no 
# filter-page-type terms, and no previously filtered items
search_results = cw_search(1, 20, ["Constantina"], [], None)
print str(search_results.hits)
