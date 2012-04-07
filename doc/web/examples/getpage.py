# Copyright (c) Twisted Matrix Laboratories
# See LICENSE for details.

# Run this example with:
#    python getpage.py <URL>

# This program will retrieve and print the resource at the given URL.

from twisted.internet import reactor
from twisted.web.client import getPage
from twisted.python.util import println
import sys

getPage(sys.argv[1]).addCallbacks(
    callback=lambda value:(println(value),reactor.stop()),
    errback=lambda error:(println("an error occurred", error),reactor.stop()))
reactor.run()
