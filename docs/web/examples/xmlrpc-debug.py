# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
This example prints raw XML-RPC traffic for a client.

Usage:
    $ python xmlrpc-debug.py

The example will make a simple XML-RPC request to bugzilla.redhat.com and print
the raw XML response string from the server.
"""

from __future__ import print_function

from twisted.web.xmlrpc import Proxy
from twisted.web.xmlrpc import _QueryFactory
from twisted.internet import reactor


class DebuggingQueryFactory(_QueryFactory):
    """ Print the server's raw responses before continuing with parsing. """
    def parseResponse(self, contents):
        print(contents)  # show the raw XML-RPC string
        return _QueryFactory.parseResponse(self, contents)


def printValue(value):
    print(repr(value))
    reactor.stop()


def printError(error):
    print('error', error)
    reactor.stop()


proxy = Proxy('https://bugzilla.redhat.com/xmlrpc.cgi')

# Enable our debugging factory for our client:
proxy.queryFactory = DebuggingQueryFactory

# "Bugzilla.version" returns the Bugzilla software version,
# like "{'version': '4.4.12081.0'}":
proxy.callRemote('Bugzilla.version').addCallbacks(printValue, printError)

reactor.run()
