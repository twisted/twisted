# Twisted, the Framework of Your Internet
# Copyright (C) 2001-2002 Matthew W. Lefkowitz
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#

'''
Usage: 
advogato.py <name> <diary entry file>
'''

from twisted.web.xmlrpc import Proxy
from twisted.internet import reactor
from getpass import getpass
import sys

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
