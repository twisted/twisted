
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
def success(message):
    print "Message received:",message
    reactor.stop()
def failure(error):
    print "Failure...",error
    reactor.stop()
def connected(perspective):
    perspective.callRemote('echo', "hello world").addCallbacks(success, failure)
    print "connected."
pb.connect("localhost", pb.portno,
           "guest", "guest",
           "pbecho", "guest", 30).addCallbacks(connected, failure)
reactor.run()
