
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

from twisted.spread import pb
from twisted.internet import tcp, main

def success(message):
    print "Message received:",message
    main.shutDown()

def failure(error):
    print "Failure...",error
    main.shutDown()

def connected(perspective):
    perspective.echo("hello world",
                     pbcallback=success,
                     pberrback=failure)
    print "connected."

# run a client
pb.connect(connected, failure,
           "localhost", pb.portno,
           "guest", "guest",
           "pbecho", "any")

main.run()
