# -*- test-case-name: twisted.test.test_words -*-

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


"""

Twisted Words Service objects.  Chat and messaging for Twisted.

Twisted words is a general-purpose chat and instant messaging system designed
to be a suitable replacement both for Instant Messenger systems and
conferencing systems like IRC.

Currently it provides presence notification, web-based account creation, and a
simple group-chat abstraction.

Stability: incendiary

Maintainer: Maintainer: U{Glyph Lefkowitz<mailto:glyph@twistedmatrix.com>}

Future Plans: Woah boy.  This module is incredibly unstable.  It has an
incredible deficiency of features.  There are also several features which are
pretty controvertial.  As far as stability goes, it is lucky that the current
interfaces are really simple: at least the uppermost external ones will almost
certainly be preserved, but there is a lot of plumbing work.

First of all the fact that users must have accounts generated through a web
interface to sign in is a serious annoyance, especially to people who are
familiar with IRC's semantics.  The following features are proposed to
mitigate this annoyance:

  - account creation through the various client interfaces available to Words
    users.

  - guest accounts, so that users who join for an hour once don't pollute the
    authentication database with huge amounts of cruft.

  - 'mood' metadata for users.  Since you can't change nicks, you need a way to
    do the equivalent thing on IRC where people will sign in multiple times and
    have foo_work and foo_home

There is no plan to make it possible to log-in without an account.  This is
simply a broken behavior of IRC; all possible convenience features that mimic
this should be integrated, but authentication is an important part of chat.

There are also certain things that are just missing.

  - restricted group operations.  Typical IRC-style stuff, except you don't
    ever see the @.  Permimssions should be grantable in a capability style,
    rather than with a single bit.

  - server-to-server communication.  As much as possible this should be
    decentralized and not have the notion of 'hub' servers; rooms have
    'physical' locality.  This is really hard to integrate with IRC client
    protocol stuff, so it may end up that this feature requires a rewrite of
    Twisted Words so that servers that present an IRC gateway are treated as
    leaf nodes, and the recommended mode of operation is for the user to run a
    lightweight proxy locally.

  - a serious logging, monitoring, and routing framework

Then there's a whole bunch of things that would be nice to have.

  - public key authentication

  - robust wire-level security

  - integrated consensus web authoring tools

  - management tools and guidelines for community leaders

  - interface to operator functionality through 'bot' interface with
    per-channel personality configuration

  - graphical extensions to clients to allow formatted text (but detect
    obviously annoying or abusive formatting)

  - rate limiting, simple DoS protection, firewall integration

  - basically everything OPN wants to be able to do, but better

"""

# System Imports
import types, time

# Twisted Imports
from twisted.spread import pb
from twisted.python import log, roots, components
from twisted.persisted import styles
from twisted import copyright
from twisted.cred import authorizer

# Status "enumeration"

OFFLINE = 0
ONLINE  = 1
AWAY = 2

statuses = ["Offline","Online","Away"]

class WordsError(pb.Error, KeyError):
    pass

class NotInCollectionError(WordsError):
    pass

class NotInGroupError(NotInCollectionError):
    def __init__(self, groupName, pName=None):
        WordsError.__init__(self, groupName, pName)
        self.group = groupName
        self.pName = pName

    def __str__(self):
        if self.pName:
            pName = "'%s' is" % (self.pName,)
        else:
            pName = "You are"
        s = ("%s not in group '%s'." % (pName, self.group))
        return s

class UserNonexistantError(NotInCollectionError):
    def __init__(self, pName):
        WordsError.__init__(self, pName)
        self.pName = pName

    def __str__(self):
        return "'%s' does not exist." % (self.pName,)

class WrongStatusError(WordsError):
    def __init__(self, status, pName=None):
        WordsError.__init__(self, status, pName)
        self.status = status
        self.pName = pName

    def __str__(self):
        if self.pName:
            pName = "'%s'" % (self.pName,)
        else:
            pName = "User"

        if self.status in statuses:
            status = self.status
        else:
            status = 'unknown? (%s)' % self.status
        s = ("%s status is '%s'." % (pName, status))
        return s


class IWordsClient(components.Interface):
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

    def setGroupMetadata(self, metadata, name):
        """Some metadata on a group has been set.

        XXX: Should this be receiveGroupMetadata(name, metedata)?
        """

    def receiveDirectMessage(self, sender, message, metadata=None):
        """Receive a message from someone named 'sender'.
        'metadata' is a dict of special flags. So far 'style': 'emote'
        is defined. Note that 'metadata' *must* be optional.
        """

    def receiveGroupMessage(self, sender, group, message, metadata=None):
        """Receive a message from 'sender' directed to a group.
        'metadata' is a dict of special flags. So far 'style': 'emote'
        is defined. Note that 'metadata' *must* be optional.
        """

    def memberJoined(self, member, group):
        """Tells me a member has joined a group.
        """

    def memberLeft(self, member, group):
        """Tells me a member has left a group.
        """

class WordsClient:
    __implements__ = IWordsClient
    """A stubbed version of L{IWordsClient}.

    Useful for partial implementations.
    """

    def receiveContactList(self, contactList): pass
    def notifyStatusChanged(self, name, status): pass
    def receiveGroupMembers(self, names, group): pass
    def setGroupMetadata(self, metadata, name): pass
    def receiveDirectMessage(self, sender, message, metadata=None): pass
    def receiveGroupMessage(self, sender, group, message, metadata=None): pass
    def memberJoined(self, member, group): pass
    def memberLeft(self, member, group): pass


class Transcript:
    """I am a transcript of a conversation between multiple parties.
    """
    def __init__(self, voice, name):
        self.chat = []
        self.voice = voice
        self.name = name
    def logMessage(self, voiceName, message, metadata):
        self.chat.append((time.time(), voiceName, message, metadata))
    def endTranscript(self):
        self.voice.stopTranscribing(self.name)

class IWordsPolicy(components.Interface):
    def getNameFor(self, participant):
        """Give a name for a participant, based on the current policy."""
    def lookUpParticipant(self, nick):
        """ Get a Participant, given a name."""

class NormalPolicy:
    __implements__ = IWordsPolicy

    def __init__(self, participant):
        self.participant = participant
    def getNameFor(self, participant):
        return participant.name

    def lookUpParticipant(self, nick):
        return self.participant.service.getPerspectiveNamed(nick)

class Participant(pb.Perspective, styles.Versioned):
    def __init__(self, name):
        pb.Perspective.__init__(self, name)
        self.name = name
        self.status = OFFLINE
        self.contacts = []
        self.reverseContacts = []
        self.groups = []
        self.client = None
        self.loggedNames = {}

        self.policy = NormalPolicy(self)
    persistenceVersion = 2

    def upgradeToVersion2(self):
        self.loggedNames = {}

    def __getstate__(self):
        state = styles.Versioned.__getstate__(self)
        # Assumptions:
        # * self.client is a RemoteReference, or otherwise represents
        #   a transient presence.
        if isinstance(state["client"], styles.Ephemeral):
            state["client"] = None
            # * Because we have no client, we are not online.
            state["status"] = OFFLINE
            # * Because we are not online, we are in no groups.
            state["groups"] = []

        return state

    def attached(self, client, identity):
        """Attach a client which implements L{IWordsClient} to me.
        """
        if ((self.client is not None)
            and self.client.__class__ != styles.Ephemeral):
            self.detached(client, identity)
        log.msg("attached: %s" % self.name)
        self.client = client
        client.callRemote('receiveContactList', map(lambda contact: (contact.name,
                                                                     contact.status),
                                                    self.contacts))
        self.changeStatus(ONLINE)
        return self

    def transcribeConversationWith(self, voiceName):
        t  = Transcript(self, voiceName)
        self.loggedNames[voiceName] = t
        return t

    def stopTranscribing(self, voiceName):
        del self.loggedNames[voiceName]

    def changeStatus(self, newStatus):
        self.status = newStatus
        for contact in self.reverseContacts:
            contact.notifyStatusChanged(self)

    def notifyStatusChanged(self, contact):
        if self.client:
            self.client.callRemote('notifyStatusChanged', contact.name, contact.status)

    def detached(self, client, identity):
        log.msg("detached: %s" % self.name)
        self.client = None
        for group in self.groups[:]:
            try:
                self.leaveGroup(group.name)
            except NotInGroupError:
                pass
        self.changeStatus(OFFLINE)

    def addContact(self, contactName):
        # XXX This should use a database or something.  Doing it synchronously
        # like this won't work.
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
        raise NotInCollectionError("No such contact '%s'."
                                   % (contactName,))

    def joinGroup(self, name):
        group = self.service.getGroup(name)
        if group in self.groups:
            # We're in that group.  Don't make a fuss.
            return
        group.addMember(self)
        self.groups.append(group)

    def leaveGroup(self, name):
        for group in self.groups:
            if group.name == name:
                self.groups.remove(group)
                group.removeMember(self)
                return
        raise NotInGroupError(name)

    def getGroupMembers(self, groupName):
        if self.client:
            for group in self.groups:
                if group.name == groupName:
                    self.client.callRemote('receiveGroupMembers',
                                           map(lambda m: m.name,
                                               group.members),
                                           group.name)
                    return
            raise NotInGroupError(groupName)

    def getGroupMetadata(self, groupName):
        if self.client:
            for group in self.groups:
                if group.name == groupName:
                    self.client.callRemote('setGroupMetadata', group.metadata, group.name)

    def receiveDirectMessage(self, sender, message, metadata):
        if self.client:
            # is this wrong?
            # nick = self.policy.getNameFor(sender)
            nick = sender.name
            if self.loggedNames.has_key(nick):
                self.loggedNames[nick].logMessage(sender.name, message,
                                                         metadata)
            self.client.callRemote('receiveDirectMessage', nick,
                                   message, metadata)
        else:
            raise WrongStatusError(self.status, self.name)


    def receiveGroupMessage(self, sender, group, message, metadata):
        if sender is not self and self.client:
            self.client.callRemote('receiveGroupMessage',sender.name, group.name,
                                   message, metadata)

    def memberJoined(self, member, group):
        if self.client:
            self.client.callRemote('memberJoined', member.name, group.name)

    def memberLeft(self, member, group):
        if self.client:
            self.client.callRemote('memberLeft', member.name, group.name)

    def directMessage(self, recipientName, message, metadata=None):
        recipient = self.policy.lookUpParticipant(recipientName)
        recipient.receiveDirectMessage(self, message, metadata or {})
        if self.loggedNames.has_key(recipientName):
            self.loggedNames[recipientName].logMessage(self.name, message, metadata)


    def groupMessage(self, groupName, message, metadata=None):
        for group in self.groups:
            if group.name == groupName:
                group.sendMessage(self, message, metadata or {})
                return
        raise NotInGroupError(groupName)

    def setGroupMetadata(self, dict_, groupName):
        if self.client:
            self.client.callRemote('setGroupMetadata', dict_, groupName)

    def perspective_setGroupMetadata(self, dict_, groupName):
        #pre-processing
        if dict_.has_key('topic'):
            #don't want topic-spoofing, now
            dict_["topic_author"] = self.name

        for group in self.groups:
            if group.name == groupName:
                group.setMetadata(dict_)

    # Establish client protocol for PB.
    perspective_changeStatus = changeStatus
    perspective_joinGroup = joinGroup
    perspective_directMessage = directMessage
    perspective_addContact = addContact
    perspective_removeContact = removeContact
    perspective_groupMessage = groupMessage
    perspective_leaveGroup = leaveGroup
    perspective_getGroupMembers = getGroupMembers

    def __repr__(self):
        if self.identityName != "Nobody":
            id_s = '(id:%s)' % (self.identityName, )
        else:
            id_s = ''
        s = ("<%s '%s'%s on %s at %x>"
             % (self.__class__, self.name, id_s,
                self.service.serviceName, id(self)))
        return s

class Group(styles.Versioned):
    """
    This class represents a group of people engaged in a chat session
    with one another.

    @type name:            C{string}
    @ivar name:            The name of the group
    @type members:         C{list}
    @ivar members:         The members of the group
    @type metadata:        C{dictionary}
    @ivar metadata:        Metadata that describes the group.  Common
                           keys are:
                             - C{'topic'}: The topic string for the group.
                             - C{'topic_author'}: The name of the user who
                               last set the topic.
    """
    def __init__(self, name):
        self.name = name
        self.members = []
        self.metadata = {'topic': 'Welcome to %s!' % self.name,
                         'topic_author': 'admin'}

    def __getstate__(self):
        state = styles.Versioned.__getstate__(self)
        state['members'] = []
        return state

    def addMember(self, participant):
        if participant in self.members:
            return
        for member in self.members:
            member.memberJoined(participant, self)
        participant.setGroupMetadata(self.metadata, self.name)
        self.members.append(participant)

    def removeMember(self, participant):
        try:
            self.members.remove(participant)
        except ValueError:
            raise NotInGroupError(self.name, participant.name)
        else:
            for member in self.members:
                member.memberLeft(participant, self)

    def sendMessage(self, sender, message, metadata):
        for member in self.members:
            member.receiveGroupMessage(sender, self, message, metadata)

    def setMetadata(self, dict_):
        self.metadata.update(dict_)
        for member in self.members:
            member.setGroupMetadata(dict_, self.name)

    def __repr__(self):
        s = "<%s '%s' at %x>" % (self.__class__, self.name, id(self))
        return s


    ##Persistence Versioning

    persistenceVersion = 1

    def upgradeToVersion1(self):
        self.metadata = {'topic': self.topic}
        del self.topic
        self.metadata['topic_author'] = 'admin'


class Service(pb.Service, styles.Versioned):
    """I am a chat service.
    """

    perspectiveClass = Participant

    def __init__(self, name, parent=None, auth=None):
        pb.Service.__init__(self, name, parent, auth)
        self.groups = {}
        self.bots = []

    ## Persistence versioning.
    persistenceVersion = 4

    def upgradeToVersion1(self):
        from twisted.internet.app import theApplication
        styles.requireUpgrade(theApplication)
        pb.Service.__init__(self, 'twisted.words', theApplication)

    def upgradeToVersion3(self):
        self.perspectives = self.participants
        del self.participants

    def upgradeToVersion4(self):
        self.bots = []

    ## Service functionality.

    def getGroup(self, name):
        group = self.groups.get(name)
        if not group:
            group = Group(name)
            self.groups[name] = group
        return group

    def createPerspective(self, name):
        if self.perspectives.has_key(name):
            raise KeyError("Participant already exists: %s." % name)
        log.msg("Creating New Participant: %s" % name)
        return pb.Service.createPerspective(self, name)

    def getPerspectiveNamed(self, name):
        try:
            return pb.Service.getPerspectiveNamed(self, name)
        except KeyError:
            raise UserNonexistantError(name)

    def addBot(self, name, bot):
        try:
            p = self.getPerspectiveNamed(name)
        except UserNonexistantError:
            p = self.createPerspective(name)

        bot.setupBot(p) # XXX this method needs a better name
        from twisted.spread.util import LocalAsyncForwarder
        p.attached(LocalAsyncForwarder(bot, IWordsClient, 1), None)
        self.bots.append(bot)

    def deleteBot(self, bot):
        bot.voice.detached(bot, None)
        self.bots.remove(bot)
        del self.perspectives[bot.voice.perspectiveName]

    createParticipant = createPerspective

    def __str__(self):
        s = "<%s in app '%s' at %x>" % (self.serviceName,
                                        self.application.name,
                                        id(self))
        return s
