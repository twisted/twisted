
# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
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

from twisted.internet import reactor
from twisted.spread import pb
from twisted.cred.credentials import UsernamePassword

from pbecho import DefinedError

def success(message):
    print "Message received:",message
    # reactor.stop()

def failure(error):
    t = error.trap(DefinedError)
    print "error received:", t
    reactor.stop()

def connected(perspective):
    perspective.callRemote('echo', "hello world").addCallbacks(success, failure)
    perspective.callRemote('error').addCallbacks(success, failure)
    print "connected."


factory = pb.PBClientFactory()
reactor.connectTCP("localhost", pb.portno, factory)
factory.login(
    UsernamePassword("guest", "guest")).addCallbacks(connected, failure)

reactor.run()
