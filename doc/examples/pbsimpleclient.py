
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
from twisted.internet import main, tcp

def gotObject(object):
    print "got object:",object
    object.echo("hello network", pbcallback=gotEcho)
def gotEcho(echo):
    print 'server echoed:',echo
    main.shutDown()

def gotNoObject(reason):
    print "no object:",reason
    main.shutDown()

pb.getObjectAt("localhost", 8789, gotObject, gotNoObject)
main.run()
