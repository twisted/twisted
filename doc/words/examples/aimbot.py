#!/usr/bin/python
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
#

"""AIM echo bot."""

from twisted.protocols import toc
from twisted.internet import reactor
from twisted.internet import base
import twisted.im.tocsupport as ts

# account info
screenname = 'username'
password = 'password'

class aimBot(toc.TOCClient):
    """AOL Instant Messenger echo bot"""

    def gotConfig(self, mode, buddylist, permit, deny):
        """called when the server sends us config info"""
        global screename

        # add someone to our deny list?
        self.add_deny([])

        # add ourself to our buddy list
        self.add_buddy([screenname])

        # finish up the signon procedure
        self.signon()

    def updateBuddy(self,username,online,evilness,signontime,idletime,userclass,away):
        """called when a buddy changes state"""
        print "status changed for",username

    def hearWarning(self, warnlvl, screenname):
        """called when someone warns us"""
        print screenname,"warned us"

    def hearError(self, errcode, *args):
        """called when server sends error"""
        print "recieved error:",errcode

    def hearMessage(self, username, message, autoreply):
        """called when a message is recieved"""

        # remove the incoming message' html
        msg = ts.dehtml(message)
        
        print "got message:",msg
        
        # construct the reply, and turn it into html
        reply = ts.html("echo: %s" % msg)

        self.say(username, reply)

bot = base.BCFactory( aimBot(screenname, password) )
reactor.connectTCP("toc.oscar.aol.com", 9898, bot)

reactor.run()
