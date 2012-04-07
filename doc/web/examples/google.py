# Copyright (c) Twisted Matrix Laboratories
# See LICENSE for details.

# Run this example with:
#   python google.py <keyword(s)>.

# This program will print out the URL corresponding 
# to the first webpage given by a Google search.

from twisted.web.google import checkGoogle
from twisted.python.util import println
from twisted.internet import reactor 
import sys

checkGoogle(sys.argv[1:]).addCallbacks(
 lambda l:(println(l),reactor.stop()),
 lambda e:(println('error:',e),reactor.stop()))
reactor.run()
