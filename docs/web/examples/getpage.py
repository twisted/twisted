# Copyright (c) Twisted Matrix Laboratories
# See LICENSE for details.

"""
This program will retrieve and print the resource at the given URL.

Usage:
    $ python getpage.py <URL>
"""

import sys

from twisted.internet import reactor
from twisted.python.util import println
from twisted.web.client import getPage

url = sys.argv[1].encode("ascii")
getPage(url).addCallbacks(
    callback=lambda value: (println(value), reactor.stop()),
    errback=lambda error: (println("an error occurred", error), reactor.stop()),
)
reactor.run()
