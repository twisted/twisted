# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
This example demonstrates how to logon to a remote server and post a diary.

Usage:
    $ python advogato.py <name> <diary entry file>
"""

import sys
from getpass import getpass

from twisted.web.xmlrpc import Proxy
from twisted.internet import reactor

class AddDiary:

    def __init__(self, name, password):
        self.name = name
        self.password = password
        self.proxy = Proxy('http://advogato.org/XMLRPC')

    def __call__(self, filename):
        self.data = open(filename).read()
        d = self.proxy.callRemote('authenticate', self.name, self.password)
        d.addCallbacks(self.login, self.noLogin)

    def noLogin(self, reason):
        print "could not login"
        reactor.stop()

    def login(self, cookie):
        d = self.proxy.callRemote('diary.set', cookie, -1, self.data)
        d.addCallbacks(self.setDiary, self.errorSetDiary)

    def setDiary(self, response):
        reactor.stop()

    def errorSetDiary(self, error):
        print "could not set diary", error
        reactor.stop()

diary = AddDiary(sys.argv[1], getpass())
diary(sys.argv[2])
reactor.run()
