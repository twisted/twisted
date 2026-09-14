# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
This example demonstrates how to use downloadPage.

Usage:
    $ python dlpage.py <url>

Don't forget the http:// when you type a URL!
"""

import sys

from twisted.internet import reactor
from twisted.python.util import println
from twisted.web.client import downloadPage

# The function downloads a page and saves it to a file, in this case, it saves
# the page to "foo".
url = sys.argv[1].encode("ascii")
downloadPage(url, "foo").addCallbacks(
    lambda value: reactor.stop(),
    lambda error: (println("an error occurred", error), reactor.stop()),
)
reactor.run()
