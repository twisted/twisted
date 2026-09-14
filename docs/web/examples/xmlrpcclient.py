# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
This example makes remote XML-RPC calls.

Usage:
    $ python xmlrpcclient.py

The example will make an XML-RPC request to advogato.org and display the result.
"""

from twisted.internet import reactor
from twisted.web.xmlrpc import Proxy


def printValue(value):
    print(repr(value))
    reactor.stop()


def printError(error):
    print("error", error)
    reactor.stop()


def capitalize(value):
    print(repr(value))
    proxy.callRemote("test.capitalize", "moshe zadka").addCallbacks(
        printValue, printError
    )


proxy = Proxy(b"http://advogato.org/XMLRPC")
# The callRemote method accepts a method name and an argument list.
proxy.callRemote("test.sumprod", 2, 5).addCallbacks(capitalize, printError)
reactor.run()
