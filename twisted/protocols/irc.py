
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

"""Internet Relay Chat Protocol implementation

References:
 * RFC 1459: Internet Relay Chat Protocol

 * RFC 2812: Internet Relay Chat: Client Protocol

 * The Client-To-Client-Protocol
   http://www.irchelp.org/irchelp/rfc/ctcpspec.html
"""

from twisted.internet import reactor
from twisted.persisted import styles
from twisted.protocols import basic, protocol
from twisted.python import log, reflect

# System Imports

import errno
import operator
import os
import random
import re
import shutil
import stat
import string
import struct
import sys
import time
import tempfile
import types
import traceback

from os import path

NUL = chr(0)
CR = chr(015)
NL = chr(012)
LF = NL
SPC = chr(040)

class IRCBadMessage(Exception):
    pass

def parsemsg(s):
    """Breaks a message from an IRC server into its prefix, command, and arguments.
    """
    prefix = ''
    trailing = []
    if s[0] == ':':
        prefix, s = string.split(s[1:], ' ', 1)
    if string.find(s,':') != -1:
        s, trailing = string.split(s, ':', 1)
        args = string.split(s)
        args.append(trailing)
    else:
        args = string.split(s)
    command = args.pop(0)
    return prefix, command, args


class IRC(protocol.Protocol):
    """Internet Relay Chat server protocol.
    """

    buffer = ""

    def connectionMade(self):
        log.msg("irc connection made")
        self.channels = []

    def sendLine(self, line):
        self.transport.write("%s%s%s" % (line, CR, LF))

    def sendMessage(self, command, *parameter_list, **prefix):
        """Send a line formatted as an IRC message.

        First argument is the command, all subsequent arguments
        are parameters to that command.  If a prefix is desired,
        it may be specified with the keyword argument 'prefix'.
        """

        if not command:
            raise ValueError, "IRC message requires a command."

        if ' ' in command or command[0] == ':':
            # Not the ONLY way to screw up, but provides a little
            # sanity checking to catch likely dumb mistakes.
            raise ValueError, "Somebody screwed up, 'cuz this doesn't" \
                  " look like a command to me: %s" % command

        line = string.join([command] + list(parameter_list))
        if prefix.has_key('prefix'):
            line = ":%s %s" % (prefix['prefix'], line)
        self.sendLine(line)

        if len(parameter_list) > 15:
            log.msg("Message has %d parameters (RFC allows 15):\n%s" %
                    (len(parameter_list), line))

    def dataReceived(self, data):
        """This hack is to support mIRC, which sends LF only,
        even though the RFC says CRLF.  (Also, the flexibility
        of LineReceiver to turn "line mode" on and off was not
        required.)
        """
        self.buffer = self.buffer + data
        lines = string.split(self.buffer, LF)
        # Put the (possibly empty) element after the last LF back in the
        # buffer
        self.buffer = lines.pop()

        for line in lines:
            if len(line) <= 2:
                # This is a blank line, at best.
                continue
            if line[-1] == CR:
                line = line[:-1]
            prefix, command, params = parsemsg(line)
            # mIRC is a big pile of doo-doo
            command = string.upper(command)
            # DEBUG: log.msg( "%s %s %s" % (prefix, command, params))
            method = getattr(self, "irc_%s" % command, None)
            try:
                if method is not None:
                    method(prefix, params)
                else:
                    self.irc_unknown(prefix, command, params)
            except:
                log.deferr()

    def irc_unknown(self, prefix, command, params):
        """Implement me!"""
        raise NotImplementedError


class IRCClient(basic.LineReceiver):
    """Internet Relay Chat client protocol, with sprinkles.

    In addition to providing an interface for an IRC client protocol,
    this class also contains reasonable implementations of many common
    CTCP methods.

    TODO:
     * Login for IRCnets which require a PASS
     * Limit the length of messages sent (because the IRC server probably
       does).
     * Add flood protection/rate limiting for my CTCP replies.
     * NickServ cooperation.  (a mix-in?)
    """

    nickname = 'irc'
    realname = None
    ### Responses to various CTCP queries.

    userinfo = None
    # fingerReply is a callable returning a string, or a str()able object.
    fingerReply = None
    versionName = None
    versionNum = None
    versionEnv = None

    sourceHost = "twistedmatrix.com"
    sourceDir = "/downloads"
    sourceFiles = None

    dcc_sessions = None

    __pychecker__ = 'unusednames=params,prefix,channel'

    ### Interface level client->user output methods
    ###
    ### You'll want to override these.

    def privmsg(self, user, channel, message):
        """Called when I have a message from a user to me or a channel.
        """
        pass

    def joined(self, channel):
        """Called when I finish joining a channel.

        channel has the starting character (# or &) intact.
        """
        pass

    def noticed(self, user, channel, message):
        """Called when I have a notice from a user to me or a channel.

        By default, this is equivalent to IRCClient.privmsg, but if your
        client makes any automated replies, you must override this!
        From the RFC:

            The difference between NOTICE and PRIVMSG is that
            automatic replies MUST NEVER be sent in response to a
            NOTICE message. [...] The object of this rule is to avoid
            loops between clients automatically sending something in
            response to something it received.
        """
        self.privmsg(user, channel, message)

    def action(self, user, channel, data):
        """Called when I see a user perform an ACTION on a channel.
        """
        pass

    def pong(self, user, secs):
        """Called with the results of a CTCP PING query.
        """
        pass

    def signedOn(self):
        """Called after sucessfully signing on to the server.
        """
        pass

    ### user input commands, client->server
    ### Your client will want to invoke these.

    # i have tried to keep backward compatibility with the 0.16
    # way of doings (join('channel') when you really want #channel),
    # however trying to join channels like ##foo and ###foo will
    # work differently now. leave, say and me all have the same issue
    # the old way made it impossible to join &channel's (and IMHO
    # was a little bit annoying :))

    def join(self, channel, key=None):
        if channel[0] not in '&#': channel = '#' + channel
        if key:
            self.sendLine("JOIN %s %s" (channel, key))
        else:
            self.sendLine("JOIN %s" % (channel,))

    def leave(self, channel, reason=None):
        if channel[0] not in '&#': channel = '#' + channel
        if reason:
            self.sendLine("PART %s :%s" % (channel, reason))
        else:
            self.sendLine("PART %s" % (channel,))

    part = leave

    def topic(self, channel, topic):
        # << TOPIC #xtestx :fff
        if channel[0] not in '&#': channel = '#' + channel
        self.sendLine("TOPIC %s :%s" % (channel, topic))

    def say(self, channel, message, split = None):
        if channel[0] not in '&#': channel = '#' + channel
        fmt = "PRIVMSG %s :%%s" % (channel,)

        if split is None:
            self.sendLine(fmt % (message,))
        else:
            i = split - len(fmt) - 2
            if i <= 0:
                self.sendLine(fmt % (message,))
                return
            while len(message):
                s = fmt % message[:i]
                message = message[i:]
                self.sendLine(s)

    def msg(self, user, message):
        self.sendLine("PRIVMSG %s :%s" % (user, message))

    def notice(self, user, message):
        self.sendLine("NOTICE %s :%s" % (user, message))

    def away(self, message=''):
        self.sendLine("AWAY :%s" % message)

    def setNick(self, nickname):
        self.nickname = nickname
        self.sendLine("NICK %s" % nickname)
        self.sendLine("USER %s foo bar :%s" % (nickname, self.realname))

    ### user input commands, client->client

    def me(self, channel, action):
        """Strike a pose.
        """
        if channel[0] not in '&#': channel = '#' + channel
        self.ctcpMakeQuery(channel, [('ACTION', action)])

    _pings = None
    _MAX_PINGRING = 12

    def ping(self, user):
        """Measure round-trip delay to another IRC client.
        """
        if self._pings is None:
            self._pings = {}

        key = []
        for i in xrange(12):
            key.append(random.choice(xrange(33,91)))
        key = string.join(map(chr, key),'')
        self._pings[key] = time.time()
        self.ctcpMakeQuery(user, [('PING', key)])

        if len(self._pings) > self._MAX_PINGRING:
            # Remove some of the oldest entries.
            byValue = map(lambda a: (a[-1], a[0]),
                          self._pings.items())
            byValue.sort()
            excess = self._MAX_PINGRING - len(self._pings)
            for i in xrange(excess):
                del self._pings[byValue[i][1]]

    def dccSend(self, user, file):
        if type(file) == types.StringType:
            file = open(file, 'r')

        size = fileSize(file)

        name = getattr(file, "name", "file@%s" % (id(file),))

        factory = DccSendFactory(file)
        port = reactor.listenTCP(0, factory, 1)

        raise NotImplementedError,(
            "XXX!!! Help!  I need to bind a socket, have it listen, and tell me its address.  "
            "(and stop accepting once we've made a single connection.)")

        my_address = struct.pack("!I", my_address)

        args = ['SEND', name, my_address, str(portNum)]

        if not (size is None):
            args.append(size)

        args = string.join(args, ' ')

        self.ctcpMakeQuery(user, [('DCC', args)])


    ### server->client messages
    ### You might want to fiddle with these,
    ### but it is safe to leave them alone.

    def irc_ERR_NICKNAMEINUSE(self, prefix, params):
        self.setNick(self.nickname+'_')

    def irc_RPL_WELCOME(self, prefix, params):
        self.signedOn()

    def irc_JOIN(self, prefix, params):
        nick = string.split(prefix,'!')[0]
        if nick == self.nickname: self.joined(params[-1]) # whoops! :)

    def irc_PING(self, prefix, params):
        self.sendLine("PONG %s" % params[-1])

    def irc_PRIVMSG(self, prefix, params):
        user = prefix
        channel = params[0]
        message = params[-1]

        if not message: return # don't raise an exception if some idiot sends us a blank message

        if message[0]==X_DELIM:
            m = ctcpExtract(message)
            if m['extended']:
                self.ctcpQuery(user, channel, m['extended'])

            if not m['normal']:
                return

            message = string.join(m['normal'], ' ')

        self.privmsg(user, channel, message)

    def irc_NOTICE(self, prefix, params):
        user = prefix
        channel = params[0]
        message = params[-1]

        if message[0]==X_DELIM:
            m = ctcpExtract(message)
            if m['extended']:
                self.ctcpReply(user, channel, m['extended'])

            if not m['normal']:
                return

            message = string.join(m['normal'], ' ')

        self.noticed(user, channel, message)

    def irc_unknown(self, prefix, command, params):
        pass


    ### Receiving a CTCP query from another party
    ### It is safe to leave these alone.

    def ctcpQuery(self, user, channel, messages):
        """Dispatch method for any CTCP queries received.
        """
        for m in messages:
            method = getattr(self, "ctcpQuery_%s" % m[0], None)
            if method:
                method(user, channel, m[1])
            else:
                self.ctcpUnknownQuery(user, channel, m[0], m[1])

    def ctcpQuery_ACTION(self, user, channel, data):
        self.action(user, channel, data)

    def ctcpQuery_PING(self, user, channel, data):
        nick = string.split(user,"!")[0]
        self.ctcpMakeReply(nick, [("PING", data)])

    def ctcpQuery_FINGER(self, user, channel, data):
        if data is not None:
            self.quirkyMessage("Why did %s send '%s' with a FINGER query?"
                               % (user, data))
        if not self.fingerReply:
            return

        if operator.isCallable(self.fingerReply):
            reply = self.fingerReply()
        else:
            reply = str(self.fingerReply)

        nick = string.split(user,"!")[0]
        self.ctcpMakeReply(nick, [('FINGER', reply)])

    def ctcpQuery_VERSION(self, user, channel, data):
        if data is not None:
            self.quirkyMessage("Why did %s send '%s' with a VERSION query?"
                               % (user, data))

        if self.versionName:
            nick = string.split(user,"!")[0]
            self.ctcpMakeReply(nick, [('VERSION', '%s:%s:%s' %
                                       (self.versionName,
                                        self.versionNum,
                                        self.versionEnv))])

    def ctcpQuery_SOURCE(self, user, channel, data):
        if data is not None:
            self.quirkyMessage("Why did %s send '%s' with a SOURCE query?"
                               % (user, data))
        if self.sourceHost:
            nick = string.split(user,"!")[0]
            if self.sourceFiles:
                sourceFiles = string.join(self.sourceFiles, ' ')
            else:
                sourceFiles = ''
            self.ctcpMakeReply(nick, [('SOURCE', "%s:%s:%s" %
                                       (self.sourceHost,
                                        self.sourceDir,
                                        sourceFiles,
                                        )),
                                      ('SOURCE', None)
                                      ])

    def ctcpQuery_USERINFO(self, user, channel, data):
        if data is not None:
            self.quirkyMessage("Why did %s send '%s' with a USERINFO query?"
                               % (user, data))
        if self.userinfo:
            nick = string.split(user,"!")[0]
            self.ctcpMakeReply(nick, [('USERINFO', self.userinfo)])

    def ctcpQuery_CLIENTINFO(self, user, channel, data):
        """A master index of what CTCP tags this client knows.

        If no arguments are provided, respond with a list of known tags.
        If an argument is provided, provide human-readable help on
        the usage of that tag.
        """

        nick = string.split(user,"!")[0]
        if not data:
            # XXX: prefixedMethodNames gets methods from my *class*,
            # but it's entirely possible that this *instance* has more
            # methods.
            names = reflect.prefixedMethodNames(self.__class__,
                                                'ctcpQuery_')

            self.ctcpMakeReply(nick, [('CLIENTINFO',
                                       string.join(names, ' '))])
        else:
            args = string.split(data)
            method = getattr(self, 'ctcpQuery_%s' % (args[0],), None)
            if not method:
                self.ctcpMakeReply(nick, [('ERRMSG',
                                           "CLIENTINFO %s :"
                                           "Unknown query '%s'"
                                           % (data, args[0]))])
                return
            doc = getattr(method, '__doc__', '')
            self.ctcpMakeReply(nick, [('CLIENTINFO', doc)])


    def ctcpQuery_ERRMSG(self, user, channel, data):
        # Yeah, this seems strange, but that's what the spec says to do
        # when faced with an ERRMSG query (not a reply).
        nick = string.split(user,"!")[0]
        self.ctcpMakeReply(nick, [('ERRMSG',
                                   "%s :No error has occoured." % data)])

    def ctcpQuery_TIME(self, user, channel, data):
        if data is not None:
            self.quirkyMessage("Why did %s send '%s' with a TIME query?"
                               % (user, data))
        nick = string.split(user,"!")[0]
        self.ctcpMakeReply(nick,
                           [('TIME', ':%s' %
                             time.asctime(time.localtime(time.time())))])

    def ctcpQuery_DCC(self, user, channel, data):
        """Initiate a Direct Client Connection

        Supported connection types: SEND, CHAT
        """

        data = string.split(data)
        if len(data) < 4:
            raise IRCBadMessage, "malformed DCC request: %s" % (data,)

        (dcctype, arg, address, port) = data[:4]

        # workaround for clients that send '"file name.ext"' instead of 'file_name.ext'.
        # XXX: What does the standard say? (haw haw)
        if arg[0] == '"':
          dcctype = data[0]
          args = data[1:]
          port = args.pop()
          address = args.pop()
          arg = string.join(args,' ')[1:-1]

        port = int(port)
        if '.' in address:
            pass
        else:
            try:
                address = long(address)
            except ValueError:
                raise IRCBadMessage,\
                      "Indecipherable address '%s'" % (address,)
            else:
                address = (
                    (address >> 24) & 0xFF,
                    (address >> 16) & 0xFF,
                    (address >> 8) & 0xFF,
                    address & 0xFF,
                    )
                # The mapping to 'int' is to get rid of those accursed
                # "L"s which python 1.5.2 puts on the end of longs.
                address = string.join(map(str,map(int,address)), ".")

        if self.dcc_sessions is None:
            self.dcc_sessions = []

        if dcctype == 'SEND':
            size = -1
            if len(data) >= 5:
                try:
                    size = int(data[4])
                except ValueError:
                    pass

            filename = path.basename(arg)
            protocol = DccFileReceive(filename, size,
                                      queryData=(user,channel,data))

            reactor.clientTCP(address, port, protocol)
            self.dcc_sessions.append(protocol)

        elif dcctype == 'CHAT':
            protocol = DccChat(self, queryData=(user, channel, data))
            reactor.clientTCP(address, port, protocol)
            self.dcc_sessions.append(protocol)

        #elif dcctype == 'PERSPECTIVE':
        #    b = self.classDccPbRequest(user, channel, arg)
        #    pb.connect(address, port,
        #               string.split(arg, ':')[0],
        #               string.split(arg, ':')[1],
        #               string.split(arg, ':')[2]).addCallbacks(b.callback, b.errback)
        else:
            nick = string.split(user,"!")[0]
            self.ctcpMakeReply(nick, [('ERRMSG',
                                       "DCC %s :Unknown DCC type '%s'"
                                       % (data, dcctype))])
            self.quirkyMessage("%s offered unknown DCC type %s"
                               % (user, dcctype))

    #def ctcpQuery_SED(self, user, data):
    #    """Simple Encryption Doodoo
    #
    #    Feel free to implement this, but no specification is available.
    #    """
    #    raise NotImplementedError

    def ctcpUnknownQuery(self, user, channel, tag, data):
        nick = string.split(user,"!")[0]
        self.ctcpMakeReply(nick, [('ERRMSG',
                                   "%s %s: Unknown query '%s'"
                                   % (tag, data, tag))])

        log.msg("Unknown CTCP query from %s: %s %s\n"
                 % (user, tag, data))

    def ctcpMakeReply(self, user, messages):
        """Send one or more extended messages as a CTCP reply.

        'messages' takes a list of extended messages.
        An extended message is a (tag, data) tuple, where 'data' may be
        None.
        """
        self.notice(user, ctcpStringify(messages))

    ### client CTCP query commands

    def ctcpMakeQuery(self, user, messages):
        """Send one or more extended messages as a CTCP query.

        'messages' takes a list of extended messages.
        An extended message is a (tag, data) tuple, where 'data' may be
        None.
        """
        self.msg(user, ctcpStringify(messages))

    ### Receiving a response to a CTCP query (presumably to one we made)
    ### You may want to add methods here, or override UnknownReply.

    def ctcpReply(self, user, channel, messages):
        """Dispatch method for any CTCP replies received.
        """
        for m in messages:
            method = getattr(self, "ctcpReply_%s" % m[0], None)
            if method:
                method(user, channel, m[1])
            else:
                self.ctcpUnknownReply(user, channel, m[0], m[1])

    def ctcpReply_PING(self, user, channel, data):
        if (not self._pings) or (not self._pings.has_key(data)):
            raise IRCBadMessage,\
                  "Bogus PING response from %s: %s" % (user, data)

        t0 = self._pings[data]
        self.pong(user, time.time() - t0)

    def ctcpUnknownReply(self, user, channel, tag, data):
        """Called when a fitting ctcpReply_ method is not found.

        XXX: If the client makes arbitrary CTCP queries,
        this method should probably show the responses to
        them instead of treating them as anomolies.
        """
        log.msg("Unknown CTCP reply from %s: %s %s\n"
                 % (user, tag, data))

    ### Error handlers
    ### You may override these with something more appropriate to your UI.

    def badMessage(self, line, excType, excValue, tb):
        """When I get a message that's so broken I can't use it.
        """
        log.msg(line)
        log.msg(string.join(traceback.format_exception(excType,
                                                        excValue,
                                                        tb),''))

    def quirkyMessage(self, s):
        """This is called when I receive a message which is peculiar,
        but not wholly indecipherable.
        """
        log.msg(s + '\n')

    ### Protocool methods

    def connectionMade(self):
        self.sendLine("NICK %s" % (self.nickname,))
        self.sendLine("USER %s %s * :%s" % (self.nickname,
                                            '0', self.realname))

    def lineReceived(self, line):
        # some servers (dalnet!) break RFC and send their first few lines just delimited by \n
        lines = string.split(line,'\n')
        for line in lines:
          line = lowDequote(line)
          try:
              prefix, command, params = parsemsg(line)
              if numeric_to_symbolic.has_key(command):
                  command = numeric_to_symbolic[command]
              method = getattr(self, "irc_%s" % command, None)
              if method is not None:
                  method(prefix, params)
              else:
                  self.irc_unknown(prefix, command, params)
          except IRCBadMessage:
              apply(self.badMessage, (line,) + sys.exc_info())

    def sendLine(self, line):
        basic.LineReceiver.sendLine(self, lowQuote(line))

    def __getstate__(self):
        dct = self.__dict__.copy()
        dct['dcc_sessions'] = None
        dct['_pings'] = None
        return dct


class DccFileReceiveBasic(protocol.Protocol, styles.Ephemeral):
    """Bare protocol to receive a Direct Client Connection SEND stream.

    This does enough to keep the other guy talking, but you'll want to
    extend my dataReceived method to *do* something with the data I get.
    """

    bytesReceived = 0

    def __init__(self):
        self.bytesReceived = 0

    def dataReceived(self, data):
        """Called when data is received.

        Warning: This just acknowledges to the remote host that the
        data has been received; it doesn't *do* anything with the
        data, so you'll want to override this.
        """
        self.bytesReceived = self.bytesReceived + len(data)
        self.transport.write(struct.pack('!i', self.bytesReceived))
        # these two were the wrong way around.


class DccSendProtocol(protocol.Protocol, styles.Ephemeral):
    """Protocol for an outgoing Direct Client Connection SEND.
    """

    blocksize = 1024
    file = None
    bytesSent = 0

    def __init__(self, file):
        if type(file) is types.StringType:
            self.file = open(file, 'r')

    def connectionMade(self):
        self.sendBlock()

    def dataReceived(self, data):
        # XXX: Do we need to check to see if len(data) != fmtsize?

        bytesShesGot = struct.unpack("!I", data)
        if bytesShesGot < self.bytesSent:
            # Wait for her.
            # XXX? Add some checks to see if we've stalled out?
            return
        elif bytesShesGot > self.bytesSent:
            self.transport.log("DCC SEND %s: She says she has %d bytes "
                               "but I've only sent %d.  I'm stopping "
                               "this screwy transfer."
                               % (self.file,
                                  bytesShesGot, self.bytesSent))
            self.transport.loseConnection()
            return

        self.sendBlock()

    def sendBlock(self):
        block = self.file.read(self.blocksize)
        if block:
            self.transport.write(block)
            self.bytesSent = self.bytesSent + len(block)
        else:
            # Nothing more to send, transfer complete.
            self.transport.loseConnection()

    def connectionLost(self):
        if hasattr(self.file, "close"):
            self.file.close()


class DccSendFactory(protocol.Factory):
    protocol = DccSendProtocol
    def __init__(self, file):
        self.file = file

    def buildProtocol(self, connection):
        p = self.protocol(self.file)
        p.factory = self
        return p


def fileSize(file):
    """I'll try my damndest to determine the size of this file object.
    """
    size = None
    if hasattr(file, "fileno"):
        fileno = file.fileno()
        try:
            stat_ = os.fstat(fileno)
            size = stat_[stat.ST_SIZE]
        except:
            pass
        else:
            return size

    if hasattr(file, "name") and path.exists(file.name):
        try:
            size = path.getsize(file.name)
        except:
            pass
        else:
            return size

    if hasattr(file, "seek") and hasattr(file, "tell"):
        try:
            try:
                file.seek(0, 2)
                size = file.tell()
            finally:
                file.seek(0, 0)
        except:
            pass
        else:
            return size

    return size


class DccChat(basic.LineReceiver, styles.Ephemeral):
    """Direct Client Connection protocol type CHAT.

    DCC CHAT is really just your run o' the mill basic.LineReceiver
    protocol.  This class only varies from that slightly, accepting
    either LF or CR LF for a line delimeter for incoming messages
    while always using CR LF for outgoing.

    The lineReceived method implemented here uses the DCC connection's
    'client' attribute (provided upon construction) to deliver incoming
    lines from the DCC chat via IRCClient's normal privmsg interface.
    That's something of a spoof, which you may well want to override.
    """

    queryData = None
    delimiter = CR + NL
    client = None
    remoteParty = None
    buffer = ""

    def __init__(self, client, queryData=None):
        """Initialize a new DCC CHAT session.

        queryData is a 3-tuple of
        (fromUser, targetUserOrChannel, data)
        as received by the CTCP query.

        (To be honest, fromUser is the only thing that's currently
        used here. targetUserOrChannel is potentially useful, while
        the 'data' argument is soley for informational purposes.)
        """
        self.client = client
        if queryData:
            self.queryData = queryData
            self.remoteParty = self.queryData[0]

    def dataReceived(self, data):
        self.buffer = self.buffer + data
        lines = string.split(self.buffer, LF)
        # Put the (possibly empty) element after the last LF back in the
        # buffer
        self.buffer = lines.pop()

        for line in lines:
            if line[-1] == CR:
                line = line[:-1]
            self.lineReceived(line)

    def lineReceived(self, line):
        print "DCC CHAT<%s> %s" % (self.remoteParty, line)
        self.client.privmsg(self.remoteParty,
                            self.client.nickname, line)


def dccDescribe(data):
    """Given the data chunk from a DCC query, return a descriptive string.
    """

    orig_data = data
    data = string.split(data)
    if len(data) < 4:
        return orig_data

    (dcctype, arg, address, port) = data[:4]

    if '.' in address:
        pass
    else:
        try:
            address = long(address)
        except ValueError:
            pass
        else:
            address = (
                (address >> 24) & 0xFF,
                (address >> 16) & 0xFF,
                (address >> 8) & 0xFF,
                address & 0xFF,
                )
            # The mapping to 'int' is to get rid of those accursed
            # "L"s which python 1.5.2 puts on the end of longs.
            address = string.join(map(str,map(int,address)), ".")

    if dcctype == 'SEND':
        filename = arg

        size_txt = ''
        if len(data) >= 5:
            try:
                size = int(data[4])
                size_txt = ' of size %d bytes' % (size,)
            except ValueError:
                pass

        dcc_text = ("SEND for file '%s'%s at host %s, port %s"
                    % (filename, size_txt, address, port))
    elif dcctype == 'CHAT':
        dcc_text = ("CHAT for host %s, port %s"
                    % (address, port))
    else:
        dcc_text = orig_data

    return dcc_text


class DccFileReceive(DccFileReceiveBasic):
    """Higher-level coverage for getting a file from DCC SEND.

    I write the data to a temporary file as it comes in.  I I allow you
    to change the file's name and destination directory.  I move the
    file into place when it's done, but I won't overwrite an existing
    file unless I've been told it's okay to do so.

    XXX: I need to let the client know when I am finished.
    XXX: I need to decide how to keep a progress indicator updated.
    XXX: Client needs a way to tell me \"Do not finish until I say so.\"
    XXX: I need to make sure the client understands if the file cannot be written.
    """

    filename = 'dcc'
    fileSize = -1
    destDir = '.'
    overwrite = 0
    fromUser = None
    queryData = None

    def __init__(self, filename, fileSize=-1, queryData=None):
        DccFileReceiveBasic.__init__(self)
        self.filename = filename
        self.fileSize = fileSize

        if queryData:
            self.queryData = queryData
            self.fromUser = self.queryData[0]

    def set_directory(self, directory):
        """Set the directory where the downloaded file will be placed.

        May raise OSError if the supplied directory path is not suitable.
        """
        if not path.exists(directory):
            raise OSError(errno.ENOENT, "You see no directory there.",
                          directory)
        if not path.isdir(directory):
            raise OSError(errno.ENOTDIR, "You cannot put a file into "
                          "something which is not a directory.",
                          directory)
        if not os.access(directory, os.X_OK | os.W_OK):
            raise OSError(errno.EACCES,
                          "This directory is too hard to write in to.",
                          directory)
        self.destDir = directory

    def set_filename(self, filename):
        """Change the name of the file being transferred.

        This replaces the file name provided by the sender.
        """
        self.filename = filename

    def set_overwrite(self, boolean):
        """May I overwrite existing files?
        """
        self.overwrite = boolean

    def moveFileIn(self):
        """Move the file from its temporary location to its proper name and path.

        Called once the connetion is closed, but you may want to call
        it again in case it does not succeed the first time.

        Will raise OSError with ETXTBSY if called before the file is
        closed.
        """

        if not self.file.closed:
            raise OSError(errno.ETXTBSY,
                          "The receiving socket is still eating.",
                          self.file.name)

        dst = path.abspath(path.join(self.destDir, self.filename))

        if self.overwrite or not path.exists(dst):
            fileMove(self.file.name, dst)
        else:
            raise OSError(errno.EEXIST,
                          "There's a file in the way.  "
                          "Perhaps that's why you cannot move it.",
                          dst)

    # Protocol-level methods.

    def connectionMade(self):
        self.file = open(tempfile.mktemp('DCC-%s' % self.filename), 'w')

    def dataReceived(self, data):
        self.file.write(data)
        DccFileReceiveBasic.dataReceived(self, data)

        # XXX: update a progress indicator here?

    def connectionLost(self):
        """When the connection is lost, I close the file.

        and then I moveFileIn().
        """
        self.connected = 0
        logmsg = ("%s closed." % (self,))
        if self.fileSize > 0:
            logmsg = ("%s  %d/%d bytes received"
                      % (logmsg, self.bytesReceived, self.fileSize))
            if self.bytesReceived == self.fileSize:
                pass # Hooray!
            elif self.bytesReceived < self.fileSize:
                logmsg = ("%s (Warning: %d bytes short)"
                          % (logmsg, self.fileSize - self.bytesReceived))
            else:
                logmsg = ("%s (file larger than expected)"
                          % (logmsg,))
        else:
            logmsg = ("%s  %d bytes received"
                      % (logmsg, self.bytesReceived))

        logmsg = "%s and written to %s.\n" % (logmsg, self.file.name)

        self.transport.log(logmsg)

        self.file.close()
        self.moveFileIn()

    def __str__(self):
        from_ = self.transport.getPeer()
        if self.fromUser:
            from_ = "%s (%s)" % (self.fromUser, from_)

        s = ("DCC transfer of '%s' from %s" % (self.filename, from_))
        return s

    def __repr__(self):
        s = ("<%s at %s: GET %s>"
             % (self.__class__, id(self), self.filename))
        return s


def fileMove(src, dst):
    """Move a file.

    Unlike os.rename, this works even if the source and destination
    paths are on different filesystems.  It does so by falling back to
    copy & remove if a rename fails.
    """
    try:
        os.rename(src, dst)
    except OSError, e:
        if e.errno != errno.EXDEV:
            raise

        try:
            shutil.copy(src, dst)
        except:
            raise
        else:
            os.unlink(src)

# CTCP constants and helper functions

X_DELIM = chr(001)

def ctcpExtract(message):
    """Extract CTCP data from a string.

    Returns a dictionary with two items:
        'extended': a list of CTCP (tag, data) tuples
        'normal': a list of strings which were not inside a CTCP delimeter
    """

    extended_messages = []
    normal_messages = []
    retval = {'extended': extended_messages,
              'normal': normal_messages }

    messages = string.split(message, X_DELIM)
    odd = 0

    # X1 extended data X2 nomal data X3 extended data X4 normal...
    while messages:
        if odd:
            extended_messages.append(messages.pop(0))
        else:
            normal_messages.append(messages.pop(0))
        odd = not odd

    extended_messages[:] = filter(None, extended_messages)
    normal_messages[:] = filter(None, normal_messages)

    extended_messages[:] = map(ctcpDequote, extended_messages)
    for i in xrange(len(extended_messages)):
        m = string.split(extended_messages[i], SPC, 1)
        tag = m[0]
        if len(m) > 1:
            data = m[1]
        else:
            data = None

        extended_messages[i] = (tag, data)

    return retval

# CTCP escaping

M_QUOTE= chr(020)

mQuoteTable = {
    NUL: M_QUOTE + '0',
    NL: M_QUOTE + 'n',
    CR: M_QUOTE + 'r',
    M_QUOTE: M_QUOTE + M_QUOTE
    }

mDequoteTable = {}
for k, v in mQuoteTable.items():
    mDequoteTable[v[-1]] = k

mEscape_re = re.compile('%s.' % (re.escape(M_QUOTE),), re.DOTALL)

def lowQuote(s):
    for c in (M_QUOTE, NUL, NL, CR):
        s = string.replace(s, c, mQuoteTable[c])
    return s

def lowDequote(s):
    def sub(matchobj, mDequoteTable=mDequoteTable):
        s = matchobj.group()[1]
        try:
            s = mDequoteTable[s]
        except KeyError:
            s = s
        return s

    return mEscape_re.sub(sub, s)

X_QUOTE = chr(0134)

xQuoteTable = {
    X_DELIM: X_QUOTE + 'a',
    X_QUOTE: X_QUOTE + X_QUOTE
    }

xDequoteTable = {}

for k, v in xQuoteTable.items():
    xDequoteTable[v[-1]] = k

xEscape_re = re.compile('%s.' % (re.escape(X_QUOTE),), re.DOTALL)

def ctcpQuote(s):
    for c in (X_QUOTE, X_DELIM):
        s = string.replace(s, c, xQuoteTable[c])
    return s

def ctcpDequote(s):
    def sub(matchobj, xDequoteTable=xDequoteTable):
        s = matchobj.group()[1]
        try:
            s = xDequoteTable[s]
        except KeyError:
            s = s
        return s

    return xEscape_re.sub(sub, s)

def ctcpStringify(messages):
    coded_messages = []
    for (tag, data) in messages:
        if data:
            m = "%s %s" % (tag, data)
        else:
            m = tag
        m = ctcpQuote(m)
        m = "%s%s%s" % (X_DELIM, m, X_DELIM)
        coded_messages.append(m)

    line = string.join(coded_messages, '')
    return line


# Constants (from RFC 2812)
RPL_WELCOME = '001'
RPL_YOURHOST = '002'
RPL_CREATED = '003'
RPL_MYINFO = '004'
RPL_BOUNCE = '005'
RPL_USERHOST = '302'
RPL_ISON = '303'
RPL_AWAY = '301'
RPL_UNAWAY = '305'
RPL_NOWAWAY = '306'
RPL_WHOISUSER = '311'
RPL_WHOISSERVER = '312'
RPL_WHOISOPERATOR = '313'
RPL_WHOISIDLE = '317'
RPL_ENDOFWHOIS = '318'
RPL_WHOISCHANNELS = '319'
RPL_WHOWASUSER = '314'
RPL_ENDOFWHOWAS = '369'
RPL_LISTSTART = '321'
RPL_LIST = '322'
RPL_LISTEND = '323'
RPL_UNIQOPIS = '325'
RPL_CHANNELMODEIS = '324'
RPL_NOTOPIC = '331'
RPL_TOPIC = '332'
RPL_INVITING = '341'
RPL_SUMMONING = '342'
RPL_INVITELIST = '346'
RPL_ENDOFINVITELIST = '347'
RPL_EXCEPTLIST = '348'
RPL_ENDOFEXCEPTLIST = '349'
RPL_VERSION = '351'
RPL_WHOREPLY = '352'
RPL_ENDOFWHO = '315'
RPL_NAMREPLY = '353'
RPL_ENDOFNAMES = '366'
RPL_LINKS = '364'
RPL_ENDOFLINKS = '365'
RPL_BANLIST = '367'
RPL_ENDOFBANLIST = '368'
RPL_INFO = '371'
RPL_ENDOFINFO = '374'
RPL_MOTDSTART = '375'
RPL_MOTD = '372'
RPL_ENDOFMOTD = '376'
RPL_YOUREOPER = '381'
RPL_REHASHING = '382'
RPL_YOURESERVICE = '383'
RPL_TIME = '391'
RPL_USERSSTART = '392'
RPL_USERS = '393'
RPL_ENDOFUSERS = '394'
RPL_NOUSERS = '395'
RPL_TRACELINK = '200'
RPL_TRACECONNECTING = '201'
RPL_TRACEHANDSHAKE = '202'
RPL_TRACEUNKNOWN = '203'
RPL_TRACEOPERATOR = '204'
RPL_TRACEUSER = '205'
RPL_TRACESERVER = '206'
RPL_TRACESERVICE = '207'
RPL_TRACENEWTYPE = '208'
RPL_TRACECLASS = '209'
RPL_TRACERECONNECT = '210'
RPL_TRACELOG = '261'
RPL_TRACEEND = '262'
RPL_STATSLINKINFO = '211'
RPL_STATSCOMMANDS = '212'
RPL_ENDOFSTATS = '219'
RPL_STATSUPTIME = '242'
RPL_STATSOLINE = '243'
RPL_UMODEIS = '221'
RPL_SERVLIST = '234'
RPL_SERVLISTEND = '235'
RPL_LUSERCLIENT = '251'
RPL_LUSEROP = '252'
RPL_LUSERUNKNOWN = '253'
RPL_LUSERCHANNELS = '254'
RPL_LUSERME = '255'
RPL_ADMINME = '256'
RPL_ADMINLOC = '257'
RPL_ADMINLOC = '258'
RPL_ADMINEMAIL = '259'
RPL_TRYAGAIN = '263'
ERR_NOSUCHNICK = '401'
ERR_NOSUCHSERVER = '402'
ERR_NOSUCHCHANNEL = '403'
ERR_CANNOTSENDTOCHAN = '404'
ERR_TOOMANYCHANNELS = '405'
ERR_WASNOSUCHNICK = '406'
ERR_TOOMANYTARGETS = '407'
ERR_NOSUCHSERVICE = '408'
ERR_NOORIGIN = '409'
ERR_NORECIPIENT = '411'
ERR_NOTEXTTOSEND = '412'
ERR_NOTOPLEVEL = '413'
ERR_WILDTOPLEVEL = '414'
ERR_BADMASK = '415'
ERR_UNKNOWNCOMMAND = '421'
ERR_NOMOTD = '422'
ERR_NOADMININFO = '423'
ERR_FILEERROR = '424'
ERR_NONICKNAMEGIVEN = '431'
ERR_ERRONEUSNICKNAME = '432'
ERR_NICKNAMEINUSE = '433'
ERR_NICKCOLLISION = '436'
ERR_UNAVAILRESOURCE = '437'
ERR_USERNOTINCHANNEL = '441'
ERR_NOTONCHANNEL = '442'
ERR_USERONCHANNEL = '443'
ERR_NOLOGIN = '444'
ERR_SUMMONDISABLED = '445'
ERR_USERSDISABLED = '446'
ERR_NOTREGISTERED = '451'
ERR_NEEDMOREPARAMS = '461'
ERR_ALREADYREGISTRED = '462'
ERR_NOPERMFORHOST = '463'
ERR_PASSWDMISMATCH = '464'
ERR_YOUREBANNEDCREEP = '465'
ERR_YOUWILLBEBANNED = '466'
ERR_KEYSET = '467'
ERR_CHANNELISFULL = '471'
ERR_UNKNOWNMODE = '472'
ERR_INVITEONLYCHAN = '473'
ERR_BANNEDFROMCHAN = '474'
ERR_BADCHANNELKEY = '475'
ERR_BADCHANMASK = '476'
ERR_NOCHANMODES = '477'
ERR_BANLISTFULL = '478'
ERR_NOPRIVILEGES = '481'
ERR_CHANOPRIVSNEEDED = '482'
ERR_CANTKILLSERVER = '483'
ERR_RESTRICTED = '484'
ERR_UNIQOPPRIVSNEEDED = '485'
ERR_NOOPERHOST = '491'
ERR_NOSERVICEHOST = '492'
ERR_UMODEUNKNOWNFLAG = '501'
ERR_USERSDONTMATCH = '502'

# And hey, as long as the strings are already intern'd...
symbolic_to_numeric = {
    "RPL_WELCOME": '001',
    "RPL_YOURHOST": '002',
    "RPL_CREATED": '003',
    "RPL_MYINFO": '004',
    "RPL_BOUNCE": '005',
    "RPL_USERHOST": '302',
    "RPL_ISON": '303',
    "RPL_AWAY": '301',
    "RPL_UNAWAY": '305',
    "RPL_NOWAWAY": '306',
    "RPL_WHOISUSER": '311',
    "RPL_WHOISSERVER": '312',
    "RPL_WHOISOPERATOR": '313',
    "RPL_WHOISIDLE": '317',
    "RPL_ENDOFWHOIS": '318',
    "RPL_WHOISCHANNELS": '319',
    "RPL_WHOWASUSER": '314',
    "RPL_ENDOFWHOWAS": '369',
    "RPL_LISTSTART": '321',
    "RPL_LIST": '322',
    "RPL_LISTEND": '323',
    "RPL_UNIQOPIS": '325',
    "RPL_CHANNELMODEIS": '324',
    "RPL_NOTOPIC": '331',
    "RPL_TOPIC": '332',
    "RPL_INVITING": '341',
    "RPL_SUMMONING": '342',
    "RPL_INVITELIST": '346',
    "RPL_ENDOFINVITELIST": '347',
    "RPL_EXCEPTLIST": '348',
    "RPL_ENDOFEXCEPTLIST": '349',
    "RPL_VERSION": '351',
    "RPL_WHOREPLY": '352',
    "RPL_ENDOFWHO": '315',
    "RPL_NAMREPLY": '353',
    "RPL_ENDOFNAMES": '366',
    "RPL_LINKS": '364',
    "RPL_ENDOFLINKS": '365',
    "RPL_BANLIST": '367',
    "RPL_ENDOFBANLIST": '368',
    "RPL_INFO": '371',
    "RPL_ENDOFINFO": '374',
    "RPL_MOTDSTART": '375',
    "RPL_MOTD": '372',
    "RPL_ENDOFMOTD": '376',
    "RPL_YOUREOPER": '381',
    "RPL_REHASHING": '382',
    "RPL_YOURESERVICE": '383',
    "RPL_TIME": '391',
    "RPL_USERSSTART": '392',
    "RPL_USERS": '393',
    "RPL_ENDOFUSERS": '394',
    "RPL_NOUSERS": '395',
    "RPL_TRACELINK": '200',
    "RPL_TRACECONNECTING": '201',
    "RPL_TRACEHANDSHAKE": '202',
    "RPL_TRACEUNKNOWN": '203',
    "RPL_TRACEOPERATOR": '204',
    "RPL_TRACEUSER": '205',
    "RPL_TRACESERVER": '206',
    "RPL_TRACESERVICE": '207',
    "RPL_TRACENEWTYPE": '208',
    "RPL_TRACECLASS": '209',
    "RPL_TRACERECONNECT": '210',
    "RPL_TRACELOG": '261',
    "RPL_TRACEEND": '262',
    "RPL_STATSLINKINFO": '211',
    "RPL_STATSCOMMANDS": '212',
    "RPL_ENDOFSTATS": '219',
    "RPL_STATSUPTIME": '242',
    "RPL_STATSOLINE": '243',
    "RPL_UMODEIS": '221',
    "RPL_SERVLIST": '234',
    "RPL_SERVLISTEND": '235',
    "RPL_LUSERCLIENT": '251',
    "RPL_LUSEROP": '252',
    "RPL_LUSERUNKNOWN": '253',
    "RPL_LUSERCHANNELS": '254',
    "RPL_LUSERME": '255',
    "RPL_ADMINME": '256',
    "RPL_ADMINLOC": '257',
    "RPL_ADMINLOC": '258',
    "RPL_ADMINEMAIL": '259',
    "RPL_TRYAGAIN": '263',
    "ERR_NOSUCHNICK": '401',
    "ERR_NOSUCHSERVER": '402',
    "ERR_NOSUCHCHANNEL": '403',
    "ERR_CANNOTSENDTOCHAN": '404',
    "ERR_TOOMANYCHANNELS": '405',
    "ERR_WASNOSUCHNICK": '406',
    "ERR_TOOMANYTARGETS": '407',
    "ERR_NOSUCHSERVICE": '408',
    "ERR_NOORIGIN": '409',
    "ERR_NORECIPIENT": '411',
    "ERR_NOTEXTTOSEND": '412',
    "ERR_NOTOPLEVEL": '413',
    "ERR_WILDTOPLEVEL": '414',
    "ERR_BADMASK": '415',
    "ERR_UNKNOWNCOMMAND": '421',
    "ERR_NOMOTD": '422',
    "ERR_NOADMININFO": '423',
    "ERR_FILEERROR": '424',
    "ERR_NONICKNAMEGIVEN": '431',
    "ERR_ERRONEUSNICKNAME": '432',
    "ERR_NICKNAMEINUSE": '433',
    "ERR_NICKCOLLISION": '436',
    "ERR_UNAVAILRESOURCE": '437',
    "ERR_USERNOTINCHANNEL": '441',
    "ERR_NOTONCHANNEL": '442',
    "ERR_USERONCHANNEL": '443',
    "ERR_NOLOGIN": '444',
    "ERR_SUMMONDISABLED": '445',
    "ERR_USERSDISABLED": '446',
    "ERR_NOTREGISTERED": '451',
    "ERR_NEEDMOREPARAMS": '461',
    "ERR_ALREADYREGISTRED": '462',
    "ERR_NOPERMFORHOST": '463',
    "ERR_PASSWDMISMATCH": '464',
    "ERR_YOUREBANNEDCREEP": '465',
    "ERR_YOUWILLBEBANNED": '466',
    "ERR_KEYSET": '467',
    "ERR_CHANNELISFULL": '471',
    "ERR_UNKNOWNMODE": '472',
    "ERR_INVITEONLYCHAN": '473',
    "ERR_BANNEDFROMCHAN": '474',
    "ERR_BADCHANNELKEY": '475',
    "ERR_BADCHANMASK": '476',
    "ERR_NOCHANMODES": '477',
    "ERR_BANLISTFULL": '478',
    "ERR_NOPRIVILEGES": '481',
    "ERR_CHANOPRIVSNEEDED": '482',
    "ERR_CANTKILLSERVER": '483',
    "ERR_RESTRICTED": '484',
    "ERR_UNIQOPPRIVSNEEDED": '485',
    "ERR_NOOPERHOST": '491',
    "ERR_NOSERVICEHOST": '492',
    "ERR_UMODEUNKNOWNFLAG": '501',
    "ERR_USERSDONTMATCH": '502',
}

numeric_to_symbolic = {}
for k, v in symbolic_to_numeric.items():
    numeric_to_symbolic[v] = k
