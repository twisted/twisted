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
    def __init__(self, breadstick):
        self.breadstick = breadstick
        self.network = "print"

    def sendMessage(self, sender, message):
        print "<%s@%s> %s" % (sender[0], sender[1], message)

    def sendPrivMessage(self, sender, sendee, message):
        print "(To %s:) <%s@%s> %s" % (sendee[0], sender[0], sender[1], message)


class WordsGrain:
    """I am a twisted.words salt grain."""
    def __init__(self, user, password, host, groups):
        self.network = "words"

    def sendMessage(self, sender, message):
        pass


class IRCGrain:
    """I am an IRC salt grain."""
    def __init__(self, user, password, host, port):
        self.network = "irc"

    def sendMessage(self, sender, message):
        pass
        

class BreadStick:
    """I am a pretzel with no salt: I have twisty networks of communication
    channels.
    
    Add Grains of salt (objects with a sendMessage method) to me (with
    addGrainOfSalt) and I will distribute messages to them.
    
    sendMessages to me and I will distribute them.
    """

    def __init__(self, features=()):
        self.features = list(features)
        self.name = "bob"
        
    def addGrainOfSalt(self, saltGrain):
        self.grains[saltGrain.network] = saltGrain

    def addFeature(self, feature):
        self.features.append(feature)

    def sendMessage(self, sender, message):
        """I send a message to everyone on all SaltGrains.
        'sender' is a 2-tuple of (person, network), and 'message'
        is a string
        """
        for f in self.features:
            if not f.do(sender, message): #if the feature does not want the 
                                          #message to be sent out everywhere,
                                          #then it should return false.
                break
        for p in self.grains.keys():
            self.grains[p].sendMessage(sender, message)

    def sendPrivMessage(self, sender, sendee, message):
        """I send a private message to someone on a specific SaltGrain.
        'sender' and 'sendee' are 2-tuples of (person, network). 'message'
        is a string.
        """
        try:
            self.grains[sendee[1]].sendPrivMessage(sender, sendee, message)
        except KeyError:
            try:
                self.grains[sender[1]].sendPrivMessage([self.name, self.name], sender, "That network doesn't exist!")
            except KeyError: #this really shouldn't happen
                print "gack!"
                
