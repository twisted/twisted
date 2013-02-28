# Copyright (c) Twisted Matrix Laboratories
# See LICENSE for details.

"""
This program will try to connect to the server at the given URL, and print
whether or not the SSL server certificate on the server was valid.

Usage:
    $ python secureagent.py <URL>
"""

from __future__ import print_function
import sys

from OpenSSL import SSL
from twisted.internet import reactor
from twisted.web.client import Agent, StandardWebContextFactory, ResponseNeverReceived


def gotError(failure):
    if failure.check(ResponseNeverReceived):
        failure = failure.value.reasons[0]
        if failure.check(SSL.Error):
            print("Invalid server certificate: %s" % (failure.value,))
            return
        error = failure.value
    else:
        error = failure.value
    print("Error: %s" % (error,))


def main():
    url = sys.argv[1]
    if not url.startswith("https"):
        raise RuntimeError("Only HTTPS URLs are supported.")
    agent = Agent(reactor, contextFactory=StandardWebContextFactory())
    agent.request("GET", sys.argv[1]).addCallbacks(
        lambda result: print("Validated"), gotError).addBoth(
        lambda ignore: reactor.stop())
    reactor.run()


if __name__ == '__main__':
    main()
