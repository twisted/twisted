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

"""I am an uber-bot that can do anything and everything."""

class SaltGrain:
    """I am a very simple SaltGrain implementation that just prints messages
    out."""
    def __init__(self):
        self.network = "print"

    def sendMessage(self, sender, network, message):
        print "<%s@%s> %s" % (sender, network, message)


class WordsGrain:
    def __init__(self, user, password, host, groups):
        self.network = "words"

    def sendMessage(self, sender, network, message):
        

class BreadStick:
    """I am a pretzel with no salt: I have twisty networks of communication
    channels.
    
    Add Grains of salt (objects with a sendMessage method) to me (with
    addGrainOfSalt) and I will distribute messages to them.
    
    sendMessages to me and I will distribute them.
    """

    def __init__(self, protocols=[]):
        self.grains = grains 

    def addGrainOfSalt(self, saltGrain):
        self.grains.append(saltGrain)

    def sendMessage(self, sender, message):
        for p in self.grains:
            p.sendMessage(sender, p.network, message)

