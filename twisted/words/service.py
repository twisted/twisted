
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


# System Imports
import string

# Twisted Imports
from twisted.spread import pb
from twisted.internet import passport
from twisted.python import log
from twisted.persisted import styles
from twisted import copyright

# Status "enumeration"

OFFLINE = 0
ONLINE  = 1
AWAY = 2

statuses = {
    0: "Offline",
    1: "Online",
    2: "Away"
    }


class WordsClientInterface:
    """A client to a perspective on the twisted.words service.

    I attach to that participant with Participant.attached(),
    and detatch with Participant.detached().
    """

    def receiveContactList(self, contactList):
        """Receive a list of contacts and their status.

        The list is composed of 2-tuples, of the form
        (contactName, contactStatus)
        """

    def notifyStatusChanged(self, name, status):
        """Notify me of a change in status of one of my contacts.
        """

    def receiveGroupMembers(self, names, group):
        """Receive a list of members in a group.

        'names' is a list of participant names in the group named 'group'.
        """

    def receiveDirectMessage(self, sender, message):
        """Receive a message from someone named 'sender'.
        """

    def receiveGroupMessage(self, sender, group, message):
        """Receive a message from 'sender' directed to a group.
        """

    def memberJoined(self, member, group):
        """Tells me a member has joined a group.
        """

    def memberLeft(self, member, group):
        """Tells me a member has left a group.
        """


class Participant(pb.Perspective, styles.Versioned):
    def __init__(self, name, service):
        pb.Perspective.__init__(self, name, service)
        self.name = name
        self.status = OFFLINE
        self.contacts = []
        self.reverseContacts = []
        self.groups = []
        self.client = None
        self.info = ""

    persistenceVersion = 1

    def upgradeToVersion1(self):
        self.status = OFFLINE
        self.client = None
        styles.requireUpgrade(self.service)
        pb.Perspective.__init__(self, self.name, self.service)
        log.msg("Creating account for %s" % self.name)
        ident = passport.Identity(self.name, self.service.application)
        ident.setAlreadyHashedPassword(self.password)
        del self.password
        self.setIdentity(ident)
        ident.addKeyForPerspective(self)
        try:
            self.service.application.authorizer.addIdentity(ident)
        except KeyError:
            print 'unable to add words identity for %s'% self.name

    def attached(self, client, identity):
        """Attach a client which implements WordsClientInterface to me.
        """
        if ((self.client is not None)
            and self.client.__class__ != styles.Ephemeral):
            print self.client
            raise passport.Unauthorized("duplicate login not permitted.")
        log.msg("attached: %s" % self.name)
        self.client = client
        client.receiveContactList(map(lambda contact: (contact.name,
                                                       contact.status),
                                      self.contacts))
        self.changeStatus(ONLINE)
        return self

    def changeStatus(self, newStatus):
        self.status = newStatus
        for contact in self.reverseContacts:
            contact.notifyStatusChanged(self)

    def notifyStatusChanged(self, contact):
        if self.client:
            self.client.notifyStatusChanged(contact.name, contact.status)

    def detached(self, client, identity):
        log.msg("detached: %s" % self.name)
        self.client = None
        for group in self.groups[:]:
            self.leaveGroup(group.name)
        self.changeStatus(OFFLINE)

    def addContact(self, contactName):
        contact = self.service.getPerspectiveNamed(contactName)
        self.contacts.append(contact)
        contact.reverseContacts.append(self)
        self.notifyStatusChanged(contact)

    def removeContact(self, contactName):
        for contact in self.contacts:
            if contact.name == contactName:
                self.contacts.remove(contact)
                contact.reverseContacts.remove(self)
                return
        raise pb.Error("No such contact '%s'." % (contactName,))

    def joinGroup(self, name):
        group = self.service.getGroup(name)
        if group in self.groups:
            raise pb.Error("You're already in group '%s'." % (name,))
        group.addMember(self)
        self.groups.append(group)

    def leaveGroup(self, name):
        for group in self.groups:
            if group.name == name:
                self.groups.remove(group)
                group.removeMember(self)
                return
        raise pb.Error("You're not in group '%s'." % (name,))

    def getGroupMembers(self, groupName):
        for group in self.groups:
            if group.name == groupName:
                self.client.receiveGroupMembers(map(lambda m: m.name,
                                                    group.members),
                                                group.name)
        raise pb.Error("You're not in group '%s'." % (groupName,))

    def receiveDirectMessage(self, sender, message):
        if self.client:
            self.client.receiveDirectMessage(sender.name, message)
        else:
            raise pb.Error("%s not logged in." % self.name)

    def receiveGroupMessage(self, sender, group, message):
        if sender is not self and self.client:
            self.client.receiveGroupMessage(sender.name, group.name, message)

    def memberJoined(self, member, group):
        self.client.memberJoined(member.name, group.name)

    def memberLeft(self, member, group):
        self.client.memberLeft(member.name, group.name)

    def directMessage(self, recipientName, message):
        try:
            recipient = self.service.getPerspectiveNamed(recipientName)
        except KeyError:
            raise pb.Error("No such user '%s'." % (recipientName,))
        recipient.receiveDirectMessage(self, message)

    def groupMessage(self, groupName, message):
        for group in self.groups:
            if group.name == groupName:
                group.sendMessage(self, message)
                return
        raise pb.Error("You're not in group '%s'." % (groupName,))

    # Establish client protocol for PB.
    perspective_changeStatus = changeStatus
    perspective_joinGroup = joinGroup
    perspective_directMessage = directMessage
    perspective_addContact = addContact
    perspective_removeContact = removeContact
    perspective_groupMessage = groupMessage
    perspective_leaveGroup = leaveGroup
    perspective_getGroupMembers = getGroupMembers

class Group(pb.Cacheable):

    def __init__(self, name):
        self.name = name
        self.members = []
        self.topic = "Welcome to '%s'." % self.name

    def __setstate__(self, persistentState):
        self.__dict__ = persistentState
        self.members = []

    def getStateToCopyFor(self, participant):
        assert participant in self.members, "illegal copy of group"
        return {'name':    self.name,
                'members': self.members,
                'remote':  pb.ViewPoint(participant, self)}

    def addMember(self, participant):
        if participant in self.members:
            return
        for member in self.members:
            member.memberJoined(participant, self)
        self.members.append(participant)

    def removeMember(self, participant):
        self.members.remove(participant)
        for member in self.members:
            member.memberLeft(participant, self)

    def sendMessage(self, sender, message):
        for member in self.members:
            member.receiveGroupMessage(sender, self, message)

    def __repr__(self):
        s = "<%s '%s' at %x>" % (self.__class__, self.name, id(self))
        return s

class Service(pb.Service, styles.Versioned):
    """I am a chat service.
    """
    def __init__(self, name, app):
        pb.Service.__init__(self, name, app)
        self.participants = {}
        self.groups = {}

    persistenceVersion = 1

    def upgradeToVersion1(self):
        from twisted.internet.main import theApplication
        styles.requireUpgrade(theApplication)
        pb.Service.__init__(self, 'twisted.words', theApplication)

    def getGroup(self, name):
        group = self.groups.get(name)
        if not group:
            group = Group(name)
            self.groups[name] = group
        return group

    def addParticipant(self, name):
        if not self.participants.has_key(name):
            log.msg("Created New Participant: %s" % name)
            p = Participant(name, self)
            self.participants[name] = p
            return p

    def getPerspectiveNamed(self, name):
        return self.participants[name]

    def __str__(self):
        s = "<%s in app '%s' at %x>" % (self.serviceName,
                                        self.application.name,
                                        id(self))
        return s
