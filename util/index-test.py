#!/usr/bin/python
"""
TODO: Test this from cgi-bin and fix bugs
also, allow test phrases to be queried
"""

from constantina import cw_search

search_results = cw_search(["sometest-phrase"])
print search_results
