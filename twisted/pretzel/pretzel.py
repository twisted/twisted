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

class UserAgent:
    """I am a very simple UserAgent implementation that just prints messages
    out."""
    def __init__(self, distributor):
        self.distributor = distributor
        self.network = "print"

    def sendMessage(self, sender, message):
        print "<%s@%s> %s" % (sender[0], sender[1], message)

    def sendPrivMessage(self, sender, sendee, message):
        print "(To %s:) <%s@%s> %s" % (sendee[0], sender[0], sender[1], message)


class WordsGrain:
    """I am a twisted.words UserAgent."""
    def __init__(self, user, password, host, groups):
        self.network = "words"

    def sendMessage(self, sender, message):
        pass


class IRCGrain:
    """I am an IRC UserAgent."""
    def __init__(self, user, password, host, port):
        self.network = "irc"

    def sendMessage(self, sender, message):
        pass
        

class MessageDistributor:
    """I have twisty networks of communication channels.
    
    Add UserAgents (objects with a sendMessage method) to me (with
    addUserAgent) and I will distribute messages to them.
    
    sendMessages to me and I will distribute them.
    """

    def __init__(self, features=()):
        self.features = list(features)
        self.agents = {}
        self.name = "bob"
        
    def addUserAgent(self, agent):
        self.agents[agent.network] = agent

    def addFeature(self, feature):
        self.features.append(feature)

    def sendMessage(self, sender, message):
        """I send a message to all of my agents.
        'sender' is a 2-tuple of (person, network), and 'message'
        is a string
        """
        for f in self.features:
            if not f.do(sender, message): #if the feature does not want the 
                                          #message to be sent out everywhere,
                                          #then it should return false.
                break
        for p in self.agents.keys():
            self.agents[p].sendMessage(sender, message)

    def sendPrivMessage(self, sender, sendee, message):
        """I send a private message to a specific UserAgent.
        'sender' and 'sendee' are 2-tuples of (person, network). 'message'
        is a string.
        """
        try:
            self.agents[sendee[1]].sendPrivMessage(sender, sendee, message)
        except KeyError:
            try:
                self.agents[sender[1]].sendPrivMessage([self.name, self.name], sender, "That network doesn't exist!")
            except KeyError: #this really shouldn't happen
                print "gack!"
                
