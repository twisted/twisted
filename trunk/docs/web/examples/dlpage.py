# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
This example demonstrates how to use downloadPage.

Usage:
    $ python dlpage.py <url>

Don't forget the http:// when you type a URL!
"""

from twisted.internet import reactor
from twisted.web.client import downloadPage
from twisted.python.util import println
import sys

# The function downloads a page and saves it to a file, in this case, it saves
# the page to "foo".
downloadPage(sys.argv[1], "foo").addCallbacks(
   lambda value:reactor.stop(),
   lambda error:(println("an error occurred",error),reactor.stop()))
reactor.run()
