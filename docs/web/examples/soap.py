# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
This is an example of a simple SOAP server.

Usage:
    $ python soap.py

An example session (assuming the server is running):

   >>> import SOAPpy
   >>> p = SOAPpy.SOAPProxy('http://localhost:8080/')
   >>> p.add(a=1)
   1
   >>> p.add(a=1, b=3)
   4
   >>> p.echo("Hello World")
   'Hello World'

"""

from twisted.web import soap, server
from twisted.internet import reactor, defer


class Example(soap.SOAPPublisher):
    """
    It publishs two methods, 'add' and 'echo'.
    """

    def soap_echo(self, x):
        return x

    def soap_add(self, a=0, b=0):
        return a + b
    soap_add.useKeywords = 1

    def soap_deferred(self):
        return defer.succeed(2)


reactor.listenTCP(8080, server.Site(Example()))
reactor.run()
