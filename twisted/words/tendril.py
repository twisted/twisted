# -*- test-case-name: twisted.test.test_tendril -*-
# $Id: tendril.py,v 1.32 2003/01/08 10:34:29 acapnotic Exp $
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

"""Tendril between Words and IRC servers.

A Tendril, attached to a Words service, signs on as a user to an IRC
server.  It can then relay traffic for one or more channels/groups
between the two servers.  Anything it hears on a Words group it will
repeat as a user in an IRC channel; anyone it hears on IRC will appear
to be logged in to the Words service and speaking in a group there.

How to Start a Tendril
======================

In manhole::

  from twisted.internet import reactor as R
  from twisted.internet.app import theApplication as A
  from twisted.words import tendril as T

  w = A.getServiceNamed('twisted.words')
  f = T.TendrilFactory(w)
  # Maybe do some customization of f here, i.e.
  ## f.nickname = 'PartyLink'
  ## f.groupList = ['this', 'that', 'other']
  R.connectTCP(irchost, 6667, f)

Stability: No more stable than L{words<twisted.words.service>}.

Future plans: Use \"L{Policy<twisted.words.service.Policy>}\" to get
Perspectives.

@author: U{Kevin Turner<acapnotic@twistedmatrix.com>}
"""

from twisted import copyright
from twisted.cred import authorizer, error
from twisted.internet import defer, protocol
from twisted.persisted import styles
from twisted.protocols import irc
from twisted.python import log, reflect
from twisted.words import service
from twisted.spread.util import LocalAsyncForwarder

wordsService = service
del service

import string
import traceback
import types

True = (1==1)
False = not True

_LOGALL = False

# XXX FIXME -- This will need to be fixed to work asynchronously in order to
# support multiple-server twisted.words and database access to accounts

class TendrilFactory(protocol.ReconnectingClientFactory, reflect.Accessor):
    """I build Tendril clients for a words service.

    All of a tendril's configurable state is stored here with me.
    """

    wordsService = None
    wordsclient = None

    networkSuffix = None
    nickname = None
    perspectiveName = None

    protocol = None # will be set to TendrilIRC as soon as it's defined.
    _groupList = ['tendril_test']
    _errorGroup = 'TendrilErrors'

    helptext = (
        "Hi, I'm a Tendril bridge between here and %(service)s.",
        "You can send a private message to someone like this:",
        "/msg %(myNick)s msg theirNick Hi there!",
        )

    def __init__(self, service):
        """Initialize this factory with a words service."""
        self.reallySet('wordsService', service)

    def startFactory(self):
        self.wordsclient = TendrilWords(
            service=self.wordsService, ircFactory=self,
            nickname=self.nickname, perspectiveName=self.perspectiveName,
            networkSuffix=self.networkSuffix, groupList=self.groupList,
            errorGroup=self.errorGroup)

    def buildProtocol(self, addr):
        if self.wordsclient.irc:
            log.msg("Warning: building a new %s protocol while %s is still active."
                    % (self.protocol, self.wordsclient.irc))

        proto = protocol.ClientFactory.buildProtocol(self, addr)
        self.wordsclient.setIrc(proto)

        # Ermm.
        ## self.protocol.__dict__.update(self.getConfiguration())
        for k in ('nickname', 'helptext'):
            setattr(proto, k, getattr(self, k))

        return proto

    def __getstate__(self):
        state = self.__dict__.copy()
        try:
            del state["wordsclient"]
        except KeyError:
            pass
        return state

    def set_wordsService(self, service):
        raise TypeError, "%s.wordsService is a read-only attribute." % (repr(self),)

    def set_groupList(self, groupList):
        if self.wordsclient:
            oldlist = self.wordsclient.groupList
            if groupList != oldlist:
                newgroups = filter(lambda g, ol=oldlist: g not in ol,
                                   groupList)
                deadgroups = filter(lambda o, gl=groupList: o not in gl,
                                    oldlist)

                self.wordsclient.groupList[:] = groupList
                if self.wordsclient.irc:
                    for group in newgroups:
                        self.wordsclient.irc.join(groupToChannelName(group))
                    for group in deadgroups:
                        self.wordsclient.irc.part(groupToChannelName(group))
        self._groupList = groupList

    def get_groupList(self):
        if self.wordsclient:
            return self.wordsclient.groupList
        else:
            return self._groupList

    def set_nickname(self, nick):
        if self.wordsclient and self.wordsclient.irc:
            self.wordsclient.irc.setNick(nick)
        self.reallySet('nickname', nick)

    def set_errorGroup(self, errorGroup):
        if self.wordsclient:
            oldgroup = self.wordsclient.errorGroup
            if oldgroup != errorGroup:
                self.wordsclient.joinGroup(errorGroup)
                self.wordsclient.errorGroup = errorGroup
                self.wordsclient.leaveGroup(oldgroup)
        self._errorGroup = errorGroup

    def get_errorGroup(self):
        if self.wordsclient:
            return self.wordsclient.errorGroup
        else:
            return self._errorGroup

    def set_helptext(self, helptext):
        if isinstance(helptext, types.StringType):
            helptext = string.split(helptext, '\n')
        if self.wordsclient and self.wordsclient.irc:
            self.wordsclient.irc.helptext = helptext
        self.reallySet('helptext', helptext)


class ProxiedParticipant(wordsService.WordsClient,
                         styles.Ephemeral):
    """I'm the client of a participant who is connected through Tendril.
    """

    nickname = None
    tendril = None

    def __init__(self, tendril, nickname):
        self.tendril = tendril
        self.nickname = nickname

    def setNick(self, nickname):
        self.nickname = nickname

    def receiveDirectMessage(self, sender, message, metadata=None):
        """Pass this message through tendril to my IRC counterpart.
        """
        self.tendril.msgFromWords(self.nickname,
                                  sender, message, metadata)


class TendrilIRC(irc.IRCClient, styles.Ephemeral):
    """I connect to the IRC server and broker traffic.
    """

    realname = 'Tendril'
    versionName = 'Tendril'
    versionNum = '$Revision: 1.32 $'[11:-2]
    versionEnv = copyright.longversion

    helptext = TendrilFactory.helptext

    words = None

    def __init__(self):
        """Create a new Tendril IRC client."""
        self.dcc_sessions = {}

    ### Protocol-level methods

    def connectionLost(self, reason):
        """When I lose a connection, log out all my IRC participants.
        """
        self.log("%s: Connection lost: %s" % (self.transport, reason), 'info')
        self.words.ircConnectionLost()

    ### Protocol LineReceiver-level methods

    def lineReceived(self, line):
        try:
            irc.IRCClient.lineReceived(self, line)
        except:
            # If you *don't* catch exceptions here, any unhandled exception
            # raised by anything lineReceived calls (which is most of the
            # client code) ends up making Connection Lost happen, which
            # is almost certainly not necessary for us.
            log.deferr()

    def sendLine(self, line):
        """Send a line through my transport, unless my transport isn't up.
        """
        if (not self.transport) or (not self.transport.connected):
            return

        self.log(line, 'dump')
        irc.IRCClient.sendLine(self, line)

    ### Protocol IRCClient server->client methods

    def irc_JOIN(self, prefix, params):
        """Join IRC user to the corresponding group.
        """
        nick = string.split(prefix,'!')[0]
        groupName = channelToGroupName(params[0])
        if nick == self.nickname:
            self.words.joinGroup(groupName)
        else:
            self.words._getParticipant(nick).joinGroup(groupName)

    def irc_NICK(self, prefix, params):
        """When an IRC user changes their nickname

        this does *not* change the name of their perspectivee, just my
        nickname->perspective and client->nickname mappings.
        """
        old_nick = string.split(prefix,'!')[0]
        new_nick = params[0]
        if old_nick == self.nickname:
            self.nickname = new_nick
        else:
            self.words.changeParticipantNick(old_nick, new_nick)

    def irc_PART(self, prefix, params):
        """Parting IRC members leave the correspoding group.
        """
        nick = string.split(prefix,'!')[0]
        channel = params[0]
        groupName = channelToGroupName(channel)
        if nick == self.nickname:
            self.words.groupMessage(groupName, "I've left %s" % (channel,))
            self.words.leaveGroup(groupName)
            self.words.evacuateGroup(groupName)
            return
        else:
            self.words.ircPartParticipant(nick, groupName)

    def irc_QUIT(self, prefix, params):
        """When a user quits IRC, log out their participant.
        """
        nick = string.split(prefix,'!')[0]
        if nick == self.nickname:
            self.words.detach()
        else:
            self.words.logoutParticipant(nick)

    def irc_KICK(self, prefix, params):
        """Kicked?  Who?  Not me, I hope.
        """
        nick = string.split(prefix,'!')[0]
        channel = params[0]
        kicked = params[1]
        group = channelToGroupName(channel)
        if string.lower(kicked) == string.lower(self.nickname):
            # Yikes!
            if self.words.participants.has_key(nick):
                wordsname = " (%s)" % (self.words._getParticipant(nick).name,)
            else:
                wordsname = ''
            if len(params) > 2:
                reason = '  "%s"' % (params[2],)
            else:
                reason = ''

            self.words.groupMessage(group, '%s%s kicked me off!%s'
                              % (prefix, wordsname, reason))
            self.log("I've been kicked from %s: %s %s"
                     % (channel, prefix, params), 'NOTICE')
            self.words.evacuateGroup(group)

        else:
            self.words.ircPartParticipant(kicked, group)

    def irc_INVITE(self, prefix, params):
        """Accept an invitation, if it's in my groupList.
        """
        group = channelToGroupName(params[1])
        if group in self.groupList:
            self.log("I'm accepting the invitation to join %s from %s."
                     % (group, prefix), 'NOTICE')
            self.words.join(groupToChannelName(group))

    def irc_TOPIC(self, prefix, params):
        """Announce the new topic.
        """
        # XXX: words groups *do* have topics, but they're currently
        # not used.  Should we use them?
        nick = string.split(prefix,'!')[0]
        channel = params[0]
        topic = params[1]
        self.words.groupMessage(channelToGroupName(channel),
                                "%s has just decreed the topic to be: %s"
                                % (self.words._getParticipant(nick).name,
                                   topic))

    def irc_ERR_BANNEDFROMCHAN(self, prefix, params):
        """When I can't get on a channel, report it.
        """
        self.log("Join failed: %s %s" % (prefix, params), 'NOTICE')

    irc_ERR_CHANNELISFULL = \
                          irc_ERR_UNAVAILRESOURCE = \
                          irc_ERR_INVITEONLYCHAN =\
                          irc_ERR_NOSUCHCHANNEL = \
                          irc_ERR_BADCHANNELKEY = irc_ERR_BANNEDFROMCHAN

    def irc_ERR_NOTREGISTERED(self, prefix, params):
        self.log("Got ERR_NOTREGISTERED, re-running connectionMade().",
                 'NOTICE')
        self.connectionMade()


    ### Client-To-Client-Protocol methods

    def ctcpQuery_DCC(self, user, channel, data):
        """Accept DCC handshakes, for passing on to others.
        """
        nick = string.split(user,"!")[0]

        # We're pretty lenient about what we pass on, but the existance
        # of at least four parameters (type, arg, host, port) is really
        # required.
        if len(string.split(data)) < 4:
            self.ctcpMakeReply(nick, [('ERRMSG',
                                       'DCC %s :Malformed DCC request.'
                                       % (data))])
            return

        dcc_text = irc.dccDescribe(data)

        self.notice(nick, "Got your DCC %s"
                    % (irc.dccDescribe(data),))

        pName = self.words._getParticipant(nick).name
        self.dcc_sessions[pName] = (user, dcc_text, data)

        self.notice(nick, "If I should pass it on to another user, "
                    "/msg %s DCC PASSTO theirNick" % (self.nickname,))


    ### IRCClient client event methods

    def signedOn(self):
        """Join my groupList once I've signed on.
        """
        self.log("Welcomed by IRC server.", 'info')
        self.factory.resetDelay()
        for group in self.words.groupList:
            self.join(groupToChannelName(group))

    def privmsg(self, user, channel, message):
        """Dispatch privmsg as a groupMessage or a command, as appropriate.
        """
        nick = string.split(user,'!')[0]
        if nick == self.nickname:
            return

        if string.lower(channel) == string.lower(self.nickname):
            parts = string.split(message, ' ', 1)
            cmd = parts[0]
            if len(parts) > 1:
                remainder = parts[1]
            else:
                remainder = None

            method = getattr(self, "bot_%s" % cmd, None)
            if method is not None:
                method(user, remainder)
            else:
                self.botUnknown(user, channel, message)
        else:
            # The message isn't to me, so it must be to a group.
            group = channelToGroupName(channel)
            self.words.ircParticipantMsg(nick, group, message)

    def noticed(self, user, channel, message):
        """Pass channel notices on to the group.
        """
        nick = string.split(user,'!')[0]
        if nick == self.nickname:
            return

        if string.lower(channel) == string.lower(self.nickname):
            # A private notice is most likely an auto-response
            # from something else, or a message from an IRC service.
            # Don't treat at as a command.
            pass
        else:
            # The message isn't to me, so it must be to a group.
            group = channelToGroupName(channel)
            self.words.ircParticipantMsg(nick, group, message)

    def action(self, user, channel, message):
        """Speak about a participant in third-person.
        """
        group = channelToGroupName(channel)
        nick = string.split(user,'!',1)[0]
        self.words.ircParticipantMsg(nick, group, message, emote=True)

    ### Bot event methods

    def bot_msg(self, sender, params):
        """Pass along a message as a directMessage to a words Participant
        """
        (nick, message) = string.split(params, ' ', 1)
        sender = string.split(sender, '!', 1)[0]
        try:
            self.words._getParticipant(sender).directMessage(nick, message)
        except wordsService.WordsError, e:
            self.notice(sender, "msg to %s failed: %s" % (nick, e))

    def bot_help(self, user, params):
        nick = string.split(user, '!', 1)[0]
        for l in self.helptext:
            self.notice(nick, l % {
                'myNick': self.nickname,
                'service': self.factory.wordsService,
                })

    def botUnknown(self, user, channel, message):
        parts = string.split(message, ' ', 1)
        cmd = parts[0]
        if len(parts) > 1:
            remainder = parts[1]
        else:
            remainder = None

        if remainder is not None:
            # Default action is to try anything as a 'msg'
            # make sure the message is from a user and not a server.
            if ('!' in user) and ('@' in user):
                self.bot_msg(user, message)
        else:
            # But if the msg would be empty, don't that.
            # Just act confused.
            nick = string.split(user, '!', 1)[0]
            self.notice(nick, "I don't know what to do with '%s'.  "
                        "`/msg %s help` for help."
                        % (cmd, self.nickname))

    def bot_DCC(self, user, params):
        """Commands for brokering DCC handshakes.

        DCC -- I'll tell you if I'm holding a DCC request from you.

        DCC PASSTO nick -- give the DCC request you gave me to this nick.

        DCC FORGET -- forget any DCC requests you offered to me.
        """
        nick = string.split(user,"!")[0]
        pName = self.words._getParticipant(nick).name

        if not params:
            # Do I have a DCC from you?
            if self.dcc_sessions.has_key(pName):
                dcc_text = self.dcc_sessions[pName][1]
                self.notice(nick,
                            "I have an offer from you for DCC %s"
                            % (dcc_text,))
            else:
                self.notice(nick, "I have no DCC offer from you.")
            return

        params = string.split(params)

        if (params[0] == 'PASSTO') and (len(params) > 1):
            (cmd, dst) = params[:2]
            cmd = string.upper(cmd)
            if self.dcc_sessions.has_key(pName):
                (origUser, dcc_text, orig_data)=self.dcc_sessions[pName]
                if dcc_text:
                    dcc_text = " for " + dcc_text
                else:
                    dcc_text = ''

                ctcpMsg = irc.ctcpStringify([('DCC',orig_data)])
                try:
                    self.words._getParticipant(nick).directMessage(dst,
                                                                   ctcpMsg)
                except wordsService.WordsError, e:
                    self.notice(nick, "DCC offer to %s failed: %s"
                                % (dst, e))
                else:
                    self.notice(nick, "DCC offer%s extended to %s."
                                % (dcc_text, dst))
                    del self.dcc_sessions[pName]

            else:
                self.notice(nick, "I don't have an active DCC"
                            " handshake from you.")

        elif params[0] == 'FORGET':
            if self.dcc_sessions.has_key(pName):
                del self.dcc_sessions[pName]
            self.notice(nick, "I have now forgotten any DCC offers"
                        " from you.")
        else:
            self.notice(nick,
                        "Valid DCC commands are: "
                        "DCC, DCC PASSTO <nick>, DCC FORGET")
        return


    ### Utility

    def log(self, message, priority=None):
        """I need to give Twisted a prioritized logging facility one of these days.
        """
        if _LOGALL:
            log.msg(message)
        elif not (priority in ('dump',)):
            log.msg(message)

        if priority in ('info', 'NOTICE', 'ERROR'):
            self.words.groupMessage(self.words.errorGroup, message)

TendrilFactory.protocol = TendrilIRC

class TendrilWords(wordsService.WordsClient):
    nickname = 'tl'
    networkSuffix = '@opn'
    perspectiveName = nickname + networkSuffix
    participants = None
    irc = None
    ircFactory = None

    def __init__(self, service, ircFactory,
                 nickname=None, networkSuffix=None, perspectiveName=None,
                 groupList=None, errorGroup=None):
        """
        service -- a twisted.words.service.Service, or at least
        something with a 'serviceName' attribute and 'createParticipant'
        and 'getPerspectiveNamed' methods which work like a
        words..Service.

        groupList -- a list of strings naming groups on the Words
        service to join and bridge to their counterparts on the IRC
        server.

        nickname -- a string to use as my nickname on the IRC network.

        networkSuffix -- a string to append to the nickname of the
        Participants I bring in through IRC, e.g. \"@opn\".

        perspectiveName -- the name of my perspective with this
        service.  Defaults to nickname + networkSuffix.
        """
        self.service = service
        self.ircFactory = ircFactory
        self.participants = {}

        if nickname:
            self.nickname = nickname
        if networkSuffix:
            self.networkSuffix = networkSuffix

        if perspectiveName:
            self.perspectiveName = perspectiveName
        else:
            self.perspectiveName = self.nickname + self.networkSuffix

        if groupList:
            self.groupList = groupList
        else:
            # Copy the class default's list so as to not modify the original.
            self.groupList = self.groupList[:]

        if errorGroup:
            self.errorGroup = errorGroup

        self.attachToWords()

    def setIrc(self, ircProtocol):
        self.irc = ircProtocol
        self.irc.realname =  'Tendril to %s' % (self.service.serviceName,)
        self.irc.words = self

    def setupBot(self, perspective):
        self.perspective = perspective
        self.joinGroup(self.errorGroup)

    def attachToWords(self):
        """Get my perspective on the Words service; attach as a client.
        """

        self.service.addBot(self.perspectiveName, self)

        # XXX: Decide how much of this code belongs in words..Service.addBot
#         try:
#             self.perspective = (
#                 self.service.getPerspectiveNamed(self.perspectiveName))
#         except wordsService.UserNonexistantError:
#             self.perspective = (
#                 self.service.createParticipant(self.perspectiveName))
#             if not self.perspective:
#                 raise RuntimeError, ("service %s won't give me my "
#                                      "perspective named %s"
#                                      % (self.service,
#                                         self.perspectiveName))

#         if self.perspective.client is self:
#             log.msg("I seem to be already attached.")
#             return

#         try:
#             self.attach()
#         except error.Unauthorized:
#             if self.perspective.client:
#                 log.msg("%s is attached to my perspective: "
#                         "kicking it off." % (self.perspective.client,))
#                 self.perspective.detached(self.perspective.client, None)
#                 self.attach()
#             else:
#                 raise



    ### WordsClient methods
    ##      Words.Group --> IRC

    def memberJoined(self, member, group):
        """Tell the IRC Channel when someone joins the Words group.
        """
        if (group == self.errorGroup) or self.isThisMine(member):
            return
        self.irc.say(groupToChannelName(group), "%s joined." % (member,))

    def memberLeft(self, member, group):
        """Tell the IRC Channel when someone leaves the Words group.
        """
        if (group == self.errorGroup) or self.isThisMine(member):
            return
        self.irc.say(groupToChannelName(group), "%s left." % (member,))

    def receiveGroupMessage(self, sender, group, message, metadata=None):
        """Pass a message from the Words group on to IRC.

        Or, if it's in our errorGroup, recognize some debugging commands.
        """
        if not (group == self.errorGroup):
            channel = groupToChannelName(group)
            if not self.isThisMine(sender):
                # Test for Special case:
                # got CTCP, probably through words.ircservice
                #      (you SUCK!)
                # ACTION is the only case we'll support here.
                if message[:8] == irc.X_DELIM + 'ACTION ':
                    c = irc.ctcpExtract(message)
                    for tag, data in c['extended']:
                        if tag == 'ACTION':
                            self.irc.say(channel, "* %s %s" % (sender, data))
                        else:
                            # Not an action.  Repackage the chunk,
                            msg = "%(X)s%(tag)s %(data)s%(X)s" % {
                                'X': irc.X_DELIM,
                                'tag': tag,
                                'data': data
                                }
                            # ctcpQuote it to render it harmless,
                            msg = irc.ctcpQuote(msg)
                            # and let it continue on.
                            c['normal'].append(msg)

                    for msg in c['normal']:
                        self.irc.say(channel, "<%s> %s" % (sender, msg))
                    return

                elif irc.X_DELIM in message:
                    message = irc.ctcpQuote(message)

                if metadata and metadata.has_key('style'):
                    if metadata['style'] == "emote":
                        self.irc.say(channel, "* %s %s" % (sender, message))
                        return

                self.irc.say(channel, "<%s> %s" % (sender, message))
        else:
            # A message in our errorGroup.
            if message == "participants":
                s = map(lambda i: str(i[0]), self.participants.values())
                s = string.join(s, ", ")
            elif message == "groups":
                s = map(str, self.perspective.groups)
                s = string.join(s, ", ")
            elif message == "transport":
                s = "%s connected: %s" %\
                    (self.transport, getattr(self.transport, "connected"))
            else:
                s = None

            if s:
                self.groupMessage(group, s)


    ### My methods as a Participant
    ### (Shortcuts for self.perspective.foo())

    def joinGroup(self, groupName):
        return self.perspective.joinGroup(groupName)

    def leaveGroup(self, groupName):
        return self.perspective.leaveGroup(groupName)

    def groupMessage(self, groupName, message):
        return self.perspective.groupMessage(groupName, message)

    def directMessage(self, recipientName, message):
        return self.perspective.directMessage(recipientName, message)

    ### My methods as a bogus perspective broker
    ### (Since I grab my perspective directly from the service, it hasn't
    ###  been issued by a Perspective Broker.)

    def attach(self):
        self.perspective.attached(self, None)

    def detach(self):
        """Pull everyone off Words, sign off, cut the IRC connection.
        """
        if not (self is getattr(self.perspective,'client')):
            # Not attached.
            return

        for g in self.perspective.groups:
            if g.name != self.errorGroup:
                self.leaveGroup(g.name)
        for nick in self.participants.keys()[:]:
            self.logoutParticipant(nick)
        self.perspective.detached(self, None)
        if self.transport and getattr(self.transport, 'connected'):
            self.ircFactory.doStop()
            self.transport.loseConnection()


    ### Participant event methods
    ##      Words.Participant --> IRC

    def msgFromWords(self, toNick, sender, message, metadata=None):
        """Deliver a directMessage as a privmsg over IRC.
        """
        if message[0] != irc.X_DELIM:
            if metadata and metadata.has_key('style'):
                # Damn.  What am I supposed to do with this?
                message = "[%s] %s" % (metadata['style'], message)

            self.irc.msg(toNick, '<%s> %s' % (sender, message))
        else:
            # If there is a CTCP delimeter at the beginning of the
            # message, let's leave it there to accomidate not-so-
            # tolerant clients.
            dcc_data = None
            if message[1:5] == 'DCC ':
                dcc_query = irc.ctcpExtract(message)['extended'][0]
                dcc_data = dcc_query[1]

            if dcc_data:
                desc = "DCC " + irc.dccDescribe(dcc_data)
            else:
                desc = "CTCP request"

            self.irc.msg(toNick, 'The following %s is from %s'
                     % (desc, sender))
            self.irc.msg(toNick, '%s' % (message,))


    # IRC Participant Management

    def ircConnectionLost(self):
        for nick in self.participants.keys()[:]:
            self.logoutParticipant(nick)

    def ircPartParticipant(self, nick, groupName):
        participant = self._getParticipant(nick)
        try:
            participant.leaveGroup(groupName)
        except wordsService.NotInGroupError:
            pass

        if not participant.groups:
            self.logoutParticipant(nick)

    def ircParticipantMsg(self, nick, groupName, message, emote=False):
        participant = self._getParticipant(nick)
        if emote:
            metadata = {'style': 'emote'}
        else:
            metadata = None
        try:
            participant.groupMessage(groupName, message, metadata)
        except wordsService.NotInGroupError:
            participant.joinGroup(groupName)
            participant.groupMessage(groupName, message, metadata)

    def evacuateGroup(self, groupName):
        """Pull all of my Participants out of this group.
        """
        # XXX: This marks another place where we get a little
        # overly cozy with the words service.
        group = self.service.getGroup(groupName)

        allMyMembers = map(lambda m: m[0], self.participants.values())
        groupMembers = filter(lambda m, a=allMyMembers: m in a,
                              group.members)

        for m in groupMembers:
            m.leaveGroup(groupName)

    def _getParticipant(self, nick):
        """Get a Perspective (words.service.Participant) for a IRC user.

        And if I don't have one around, I'll make one.
        """
        if not self.participants.has_key(nick):
            self._newParticipant(nick)

        return self.participants[nick][0]

    def _getClient(self, nick):
        if not self.participants.has_key(nick):
            self._newParticipant(nick)
        return self.participants[nick][1]

    # TODO: let IRC users authorize themselves and then give them a
    # *real* perspective (one attached to their identity) instead
    # of one of my @networkSuffix-Nobody perspectives.

    def _newParticipant(self, nick):
        try:
            p = self.service.getPerspectiveNamed(nick + self.networkSuffix)
        except wordsService.UserNonexistantError:
            p = self.service.createParticipant(nick + self.networkSuffix)
            if not p:
                raise wordsService.wordsError("Eeek!  Couldn't get OR "
                                              "make a perspective for "
                                              "'%s%s'." %
                                              (nick, self.networkSuffix))

        c = ProxiedParticipant(self, nick)
        p.attached(LocalAsyncForwarder(c, wordsService.IWordsClient, 1),
                   None)
        # p.attached(c, None)

        self.participants[nick] = [p, c]

    def changeParticipantNick(self, old_nick, new_nick):
        if not self.participants.has_key(old_nick):
            return

        (p, c) = self.participants[old_nick]
        c.setNick(new_nick)

        self.participants[new_nick] = self.participants[old_nick]
        del self.participants[old_nick]

    def logoutParticipant(self, nick):
        if not self.participants.has_key(nick):
            return

        (p, c) = self.participants[nick]
        p.detached(c, None)
        c.tendril = None
        # XXX: This must change if we ever start giving people 'real'
        #    perspectives!
        if not p.identityName:
            self.service.uncachePerspective(p)
        del self.participants[nick]

    def isThisMine(self, sender):
        """Returns true if 'sender' is the name of a perspective I'm providing.
        """
        if self.perspectiveName == sender:
            return "That's ME!"

        for (p, c) in self.participants.values():
            if p.name == sender:
                return 1
        return 0


def channelToGroupName(channelName):
    """Map an IRC channel name to a Words group name.

    IRC is case-insensitive, words is not.  Arbitrtarily decree that all
    IRC channels should be lowercase.

    Warning: This prevents me from relaying text from IRC to
    a mixed-case Words group.  That is, any words group I'm
    in should have an all-lowercase name.
    """

    # Normalize case and trim leading '#'
    groupName = string.lower(channelName[1:])
    return groupName

def groupToChannelName(groupName):
    # Don't add a "#" here, because we do so in the outgoing IRC methods.
    channelName = groupName
    return channelName
