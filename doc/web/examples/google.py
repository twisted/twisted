# Copyright (c) Twisted Matrix Laboratories
# See LICENSE for details.

"""
This program will print out the URL corresponding to the first webpage given by
a Google search.

Usage:
    $ python google.py <keyword(s)>
"""

import sys

from twisted.web.google import checkGoogle
from twisted.python.util import println
from twisted.internet import reactor

checkGoogle(sys.argv[1:]).addCallbacks(
 lambda l:(println(l),reactor.stop()),
 lambda e:(println('error:',e),reactor.stop()))
reactor.run()
