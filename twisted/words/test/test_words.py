
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

from twisted.trial import unittest

from twisted.spread import util
from twisted.words import service
from twisted.internet import app
from twisted.cred.authorizer import DefaultAuthorizer

class WordsTestCase(unittest.TestCase):
    def testWords(self):
        
        ap = app.Application("testwords")
        au = DefaultAuthorizer()
        s = service.Service('twisted.words', ap, au)
        s.createParticipant("glyph")
        s.createParticipant("sean")
        # XXX OBSOLETE: should be async getPerspectiveRequest
        glyph = s.getPerspectiveNamed("glyph")
        sean = s.getPerspectiveNamed("sean")
        glyph.addContact("sean")
        t = glyph.transcribeConversationWith('sean')
        glyph.attached(DummyWordsClient(), None)
        sean.attached(DummyWordsClient(), None)
        glyph.directMessage("sean", "ping")
        sean.directMessage("glyph", "pong")
        self.failUnlessEqual(len(t.chat), 2)
        t.endTranscript()
        glyph.directMessage("sean", "(DUP!)")
        self.failUnlessEqual(len(t.chat), 2)

class DummyWordsClient(util.LocalAsRemote):
    """A client to a perspective on the twisted.words service.

    I attach to that participant with Participant.attached(),
    and detatch with Participant.detached().
    """

    def async_receiveContactList(self, contactList):
        """Receive a list of contacts and their status.

        The list is composed of 2-tuples, of the form
        (contactName, contactStatus)
        """

    def async_notifyStatusChanged(self, name, status):
        """Notify me of a change in status of one of my contacts.
        """

    def async_receiveGroupMembers(self, names, group):
        """Receive a list of members in a group.

        'names' is a list of participant names in the group named 'group'.
        """

    def async_setGroupMetadata(self, metadata, name):
        """Some metadata on a group has been set.

        XXX: Should this be receiveGroupMetadata(name, metedata)?
        """

    def async_receiveDirectMessage(self, sender, message, metadata=None):
        """Receive a message from someone named 'sender'.
        'metadata' is a dict of special flags. So far 'style': 'emote'
        is defined. Note that 'metadata' *must* be optional.
        """

    def async_receiveGroupMessage(self, sender, group, message, metadata=None):
        """Receive a message from 'sender' directed to a group.
        'metadata' is a dict of special flags. So far 'style': 'emote'
        is defined. Note that 'metadata' *must* be optional.
        """

    def async_memberJoined(self, member, group):
        """Tells me a member has joined a group.
        """

    def async_memberLeft(self, member, group):
        """Tells me a member has left a group.
        """

    

testCases = [WordsTestCase]
