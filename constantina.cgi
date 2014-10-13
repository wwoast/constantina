#!/usr/bin/python

# CGI wrapper to uwsgi constantina app

import os
import sys
sys.path.append(os.path.abspath("./constantina.py"))

from wsgiref.handlers import CGIHandler
from constantina import *

CGIHandler().run(application)
