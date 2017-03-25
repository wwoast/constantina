#!/usr/bin/python
"""
Run this script at the shell, and it will create the search indexes
if they don't exist, and do a search for the term "Constantina".
"""

from os import chdir
from constantina_state import ConstantinaState
from medusa_search import MedusaSearch
import ConfigParser

CONFIG = ConfigParser.SafeConfigParser()
CONFIG.read('constantina.ini')

ROOT_DIR = CONFIG.get("paths", "root")

chdir(ROOT_DIR)

# one page, 20 results per page, search for Constantina, no 
# filter-page-type terms, and no previously filtered items
state = ConstantinaState(None)
state.medusa.search = ["Constantina"]
search_results = MedusaSearch(state)
print str(search_results.hits)
