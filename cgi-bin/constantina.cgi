#!/usr/bin/python

# CGI wrapper to uwsgi constantina app

import os
import sys

from wsgiref.handlers import CGIHandler
from constantina import *

CGIHandler().run(application)
