# -*- test-case-name: twisted.words.test.test_irc -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Internet Relay Chat Protocol for client and server.

Future Plans
============

The way the IRCClient class works here encourages people to implement
IRC clients by subclassing the ephemeral protocol class, and it tends
to end up with way more state than it should for an object which will
be destroyed as soon as the TCP transport drops.  Someone oughta do
something about that, ya know?

The DCC support needs to have more hooks for the client for it to be
able to ask the user things like "Do you want to accept this session?"
and "Transfer #2 is 67% done." and otherwise manage the DCC sessions.

Test coverage needs to be better.

@var MAX_COMMAND_LENGTH: The maximum length of a command, as defined by RFC
    2812 section 2.3.

@author: Kevin Turner

@see: RFC 1459: Internet Relay Chat Protocol
@see: RFC 2812: Internet Relay Chat: Client Protocol
@see: U{The Client-To-Client-Protocol
<http://www.irchelp.org/irchelp/rfc/ctcpspec.html>}
"""

import errno, os, random, re, stat, struct, sys, time, types, traceback
import string, socket
import warnings
import textwrap
from os import path

from twisted.internet import reactor, protocol, task
from twisted.persisted import styles
from twisted.protocols import basic
from twisted.python import log, reflect, text
from twisted.python.compat import set

NUL = chr(0)
CR = chr(015)
NL = chr(012)
LF = NL
SPC = chr(040)

# This includes the CRLF terminator characters.
MAX_COMMAND_LENGTH = 512

CHANNEL_PREFIXES = '&#!+'

class IRCBadMessage(Exception):
    pass

class IRCPasswordMismatch(Exception):
    pass



class IRCBadModes(ValueError):
    """
    A malformed mode was encountered while attempting to parse a mode string.
    """



def parsemsg(s):
    """Breaks a message from an IRC server into its prefix, command, and arguments.
    """
    prefix = ''
    trailing = []
    if not s:
        raise IRCBadMessage("Empty line.")
    if s[0] == ':':
        prefix, s = s[1:].split(' ', 1)
    if s.find(' :') != -1:
        s, trailing = s.split(' :', 1)
        args = s.split()
        args.append(trailing)
    else:
        args = s.split()
    command = args.pop(0)
    return prefix, command, args



def split(str, length=80):
    """
    Split a string into multiple lines.

    Whitespace near C{str[length]} will be preferred as a breaking point.
    C{"\\n"} will also be used as a breaking point.

    @param str: The string to split.
    @type str: C{str}

    @param length: The maximum length which will be allowed for any string in
        the result.
    @type length: C{int}

    @return: C{list} of C{str}
    """
    return [chunk
            for line in str.split('\n')
            for chunk in textwrap.wrap(line, length)]


def _intOrDefault(value, default=None):
    """
    Convert a value to an integer if possible.

    @rtype: C{int} or type of L{default}
    @return: An integer when C{value} can be converted to an integer,
        otherwise return C{default}
    """
    if value:
        try:
            return int(value)
        except (TypeError, ValueError):
            pass
    return default



class UnhandledCommand(RuntimeError):
    """
    A command dispatcher could not locate an appropriate command handler.
    """



class _CommandDispatcherMixin(object):
    """
    Dispatch commands to handlers based on their name.

    Command handler names should be of the form C{prefix_commandName},
    where C{prefix} is the value specified by L{prefix}, and must
    accept the parameters as given to L{dispatch}.

    Attempting to mix this in more than once for a single class will cause
    strange behaviour, due to L{prefix} being overwritten.

    @type prefix: C{str}
    @ivar prefix: Command handler prefix, used to locate handler attributes
    """
    prefix = None

    def dispatch(self, commandName, *args):
        """
        Perform actual command dispatch.
        """
        def _getMethodName(command):
            return '%s_%s' % (self.prefix, command)

        def _getMethod(name):
            return getattr(self, _getMethodName(name), None)

        method = _getMethod(commandName)
        if method is not None:
            return method(*args)

        method = _getMethod('unknown')
        if method is None:
            raise UnhandledCommand("No handler for %r could be found" % (_getMethodName(commandName),))
        return method(commandName, *args)





def parseModes(modes, params, paramModes=('', '')):
    """
    Parse an IRC mode string.

    The mode string is parsed into two lists of mode changes (added and
    removed), with each mode change represented as C{(mode, param)} where mode
    is the mode character, and param is the parameter passed for that mode, or
    C{None} if no parameter is required.

    @type modes: C{str}
    @param modes: Modes string to parse.

    @type params: C{list}
    @param params: Parameters specified along with L{modes}.

    @type paramModes: C{(str, str)}
    @param paramModes: A pair of strings (C{(add, remove)}) that indicate which modes take
        parameters when added or removed.

    @returns: Two lists of mode changes, one for modes added and the other for
        modes removed respectively, mode changes in each list are represented as
        C{(mode, param)}.
    """
    if len(modes) == 0:
        raise IRCBadModes('Empty mode string')

    if modes[0] not in '+-':
        raise IRCBadModes('Malformed modes string: %r' % (modes,))

    changes = ([], [])

    direction = None
    count = -1
    for ch in modes:
        if ch in '+-':
            if count == 0:
                raise IRCBadModes('Empty mode sequence: %r' % (modes,))
            direction = '+-'.index(ch)
            count = 0
        else:
            param = None
            if ch in paramModes[direction]:
                try:
                    param = params.pop(0)
                except IndexError:
                    raise IRCBadModes('Not enough parameters: %r' % (ch,))
            changes[direction].append((ch, param))
            count += 1

    if len(params) > 0:
        raise IRCBadModes('Too many parameters: %r %r' % (modes, params))

    if count == 0:
        raise IRCBadModes('Empty mode sequence: %r' % (modes,))

    return changes



class IRC(protocol.Protocol):
    """
    Internet Relay Chat server protocol.
    """

    buffer = ""
    hostname = None

    encoding = None

    def connectionMade(self):
        self.channels = []
        if self.hostname is None:
            self.hostname = socket.getfqdn()


    def sendLine(self, line):
        if self.encoding is not None:
            if isinstance(line, unicode):
                line = line.encode(self.encoding)
        self.transport.write("%s%s%s" % (line, CR, LF))


    def sendMessage(self, command, *parameter_list, **prefix):
        """
        Send a line formatted as an IRC message.

        First argument is the command, all subsequent arguments are parameters
        to that command.  If a prefix is desired, it may be specified with the
        keyword argument 'prefix'.
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
        """
        This hack is to support mIRC, which sends LF only, even though the RFC
        says CRLF.  (Also, the flexibility of LineReceiver to turn "line mode"
        on and off was not required.)
        """
        lines = (self.buffer + data).split(LF)
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
            command = command.upper()
            # DEBUG: log.msg( "%s %s %s" % (prefix, command, params))

            self.handleCommand(command, prefix, params)


    def handleCommand(self, command, prefix, params):
        """
        Determine the function to call for the given command and call it with
        the given arguments.
        """
        method = getattr(self, "irc_%s" % command, None)
        try:
            if method is not None:
                method(prefix, params)
            else:
                self.irc_unknown(prefix, command, params)
        except:
            log.deferr()


    def irc_unknown(self, prefix, command, params):
        """
        Called by L{handleCommand} on a command that doesn't have a defined
        handler. Subclasses should override this method.
        """
        raise NotImplementedError(command, prefix, params)


    # Helper methods
    def privmsg(self, sender, recip, message):
        """
        Send a message to a channel or user

        @type sender: C{str} or C{unicode}
        @param sender: Who is sending this message.  Should be of the form
            username!ident@hostmask (unless you know better!).

        @type recip: C{str} or C{unicode}
        @param recip: The recipient of this message.  If a channel, it must
            start with a channel prefix.

        @type message: C{str} or C{unicode}
        @param message: The message being sent.
        """
        self.sendLine(":%s PRIVMSG %s :%s" % (sender, recip, lowQuote(message)))


    def notice(self, sender, recip, message):
        """
        Send a "notice" to a channel or user.

        Notices differ from privmsgs in that the RFC claims they are different.
        Robots are supposed to send notices and not respond to them.  Clients
        typically display notices differently from privmsgs.

        @type sender: C{str} or C{unicode}
        @param sender: Who is sending this message.  Should be of the form
            username!ident@hostmask (unless you know better!).

        @type recip: C{str} or C{unicode}
        @param recip: The recipient of this message.  If a channel, it must
            start with a channel prefix.

        @type message: C{str} or C{unicode}
        @param message: The message being sent.
        """
        self.sendLine(":%s NOTICE %s :%s" % (sender, recip, message))


    def action(self, sender, recip, message):
        """
        Send an action to a channel or user.

        @type sender: C{str} or C{unicode}
        @param sender: Who is sending this message.  Should be of the form
            username!ident@hostmask (unless you know better!).

        @type recip: C{str} or C{unicode}
        @param recip: The recipient of this message.  If a channel, it must
            start with a channel prefix.

        @type message: C{str} or C{unicode}
        @param message: The action being sent.
        """
        self.sendLine(":%s ACTION %s :%s" % (sender, recip, message))


    def topic(self, user, channel, topic, author=None):
        """
        Send the topic to a user.

        @type user: C{str} or C{unicode}
        @param user: The user receiving the topic.  Only their nick name, not
            the full hostmask.

        @type channel: C{str} or C{unicode}
        @param channel: The channel for which this is the topic.

        @type topic: C{str} or C{unicode} or C{None}
        @param topic: The topic string, unquoted, or None if there is no topic.

        @type author: C{str} or C{unicode}
        @param author: If the topic is being changed, the full username and
            hostmask of the person changing it.
        """
        if author is None:
            if topic is None:
                self.sendLine(':%s %s %s %s :%s' % (
                    self.hostname, RPL_NOTOPIC, user, channel, 'No topic is set.'))
            else:
                self.sendLine(":%s %s %s %s :%s" % (
                    self.hostname, RPL_TOPIC, user, channel, lowQuote(topic)))
        else:
            self.sendLine(":%s TOPIC %s :%s" % (author, channel, lowQuote(topic)))


    def topicAuthor(self, user, channel, author, date):
        """
        Send the author of and time at which a topic was set for the given
        channel.

        This sends a 333 reply message, which is not part of the IRC RFC.

        @type user: C{str} or C{unicode}
        @param user: The user receiving the topic.  Only their nick name, not
            the full hostmask.

        @type channel: C{str} or C{unicode}
        @param channel: The channel for which this information is relevant.

        @type author: C{str} or C{unicode}
        @param author: The nickname (without hostmask) of the user who last set
            the topic.

        @type date: C{int}
        @param date: A POSIX timestamp (number of seconds since the epoch) at
            which the topic was last set.
        """
        self.sendLine(':%s %d %s %s %s %d' % (
            self.hostname, 333, user, channel, author, date))


    def names(self, user, channel, names):
        """
        Send the names of a channel's participants to a user.

        @type user: C{str} or C{unicode}
        @param user: The user receiving the name list.  Only their nick name,
            not the full hostmask.

        @type channel: C{str} or C{unicode}
        @param channel: The channel for which this is the namelist.

        @type names: C{list} of C{str} or C{unicode}
        @param names: The names to send.
        """
        # XXX If unicode is given, these limits are not quite correct
        prefixLength = len(channel) + len(user) + 10
        namesLength = 512 - prefixLength

        L = []
        count = 0
        for n in names:
            if count + len(n) + 1 > namesLength:
                self.sendLine(":%s %s %s = %s :%s" % (
                    self.hostname, RPL_NAMREPLY, user, channel, ' '.join(L)))
                L = [n]
                count = len(n)
            else:
                L.append(n)
                count += len(n) + 1
        if L:
            self.sendLine(":%s %s %s = %s :%s" % (
                self.hostname, RPL_NAMREPLY, user, channel, ' '.join(L)))
        self.sendLine(":%s %s %s %s :End of /NAMES list" % (
            self.hostname, RPL_ENDOFNAMES, user, channel))


    def who(self, user, channel, memberInfo):
        """
        Send a list of users participating in a channel.

        @type user: C{str} or C{unicode}
        @param user: The user receiving this member information.  Only their
            nick name, not the full hostmask.

        @type channel: C{str} or C{unicode}
        @param channel: The channel for which this is the member information.

        @type memberInfo: C{list} of C{tuples}
        @param memberInfo: For each member of the given channel, a 7-tuple
            containing their username, their hostmask, the server to which they
            are connected, their nickname, the letter "H" or "G" (standing for
            "Here" or "Gone"), the hopcount from C{user} to this member, and
            this member's real name.
        """
        for info in memberInfo:
            (username, hostmask, server, nickname, flag, hops, realName) = info
            assert flag in ("H", "G")
            self.sendLine(":%s %s %s %s %s %s %s %s %s :%d %s" % (
                self.hostname, RPL_WHOREPLY, user, channel,
                username, hostmask, server, nickname, flag, hops, realName))

        self.sendLine(":%s %s %s %s :End of /WHO list." % (
            self.hostname, RPL_ENDOFWHO, user, channel))


    def whois(self, user, nick, username, hostname, realName, server, serverInfo, oper, idle, signOn, channels):
        """
        Send information about the state of a particular user.

        @type user: C{str} or C{unicode}
        @param user: The user receiving this information.  Only their nick name,
            not the full hostmask.

        @type nick: C{str} or C{unicode}
        @param nick: The nickname of the user this information describes.

        @type username: C{str} or C{unicode}
        @param username: The user's username (eg, ident response)

        @type hostname: C{str}
        @param hostname: The user's hostmask

        @type realName: C{str} or C{unicode}
        @param realName: The user's real name

        @type server: C{str} or C{unicode}
        @param server: The name of the server to which the user is connected

        @type serverInfo: C{str} or C{unicode}
        @param serverInfo: A descriptive string about that server

        @type oper: C{bool}
        @param oper: Indicates whether the user is an IRC operator

        @type idle: C{int}
        @param idle: The number of seconds since the user last sent a message

        @type signOn: C{int}
        @param signOn: A POSIX timestamp (number of seconds since the epoch)
            indicating the time the user signed on

        @type channels: C{list} of C{str} or C{unicode}
        @param channels: A list of the channels which the user is participating in
        """
        self.sendLine(":%s %s %s %s %s %s * :%s" % (
            self.hostname, RPL_WHOISUSER, user, nick, username, hostname, realName))
        self.sendLine(":%s %s %s %s %s :%s" % (
            self.hostname, RPL_WHOISSERVER, user, nick, server, serverInfo))
        if oper:
            self.sendLine(":%s %s %s %s :is an IRC operator" % (
                self.hostname, RPL_WHOISOPERATOR, user, nick))
        self.sendLine(":%s %s %s %s %d %d :seconds idle, signon time" % (
            self.hostname, RPL_WHOISIDLE, user, nick, idle, signOn))
        self.sendLine(":%s %s %s %s :%s" % (
            self.hostname, RPL_WHOISCHANNELS, user, nick, ' '.join(channels)))
        self.sendLine(":%s %s %s %s :End of WHOIS list." % (
            self.hostname, RPL_ENDOFWHOIS, user, nick))


    def join(self, who, where):
        """
        Send a join message.

        @type who: C{str} or C{unicode}
        @param who: The name of the user joining.  Should be of the form
            username!ident@hostmask (unless you know better!).

        @type where: C{str} or C{unicode}
        @param where: The channel the user is joining.
        """
        self.sendLine(":%s JOIN %s" % (who, where))


    def part(self, who, where, reason=None):
        """
        Send a part message.

        @type who: C{str} or C{unicode}
        @param who: The name of the user joining.  Should be of the form
            username!ident@hostmask (unless you know better!).

        @type where: C{str} or C{unicode}
        @param where: The channel the user is joining.

        @type reason: C{str} or C{unicode}
        @param reason: A string describing the misery which caused this poor
            soul to depart.
        """
        if reason:
            self.sendLine(":%s PART %s :%s" % (who, where, reason))
        else:
            self.sendLine(":%s PART %s" % (who, where))


    def channelMode(self, user, channel, mode, *args):
        """
        Send information about the mode of a channel.

        @type user: C{str} or C{unicode}
        @param user: The user receiving the name list.  Only their nick name,
            not the full hostmask.

        @type channel: C{str} or C{unicode}
        @param channel: The channel for which this is the namelist.

        @type mode: C{str}
        @param mode: A string describing this channel's modes.

        @param args: Any additional arguments required by the modes.
        """
        self.sendLine(":%s %s %s %s %s %s" % (
            self.hostname, RPL_CHANNELMODEIS, user, channel, mode, ' '.join(args)))



class ServerSupportedFeatures(_CommandDispatcherMixin):
    """
    Handle ISUPPORT messages.

    Feature names match those in the ISUPPORT RFC draft identically.

    Information regarding the specifics of ISUPPORT was gleaned from
    <http://www.irc.org/tech_docs/draft-brocklesby-irc-isupport-03.txt>.
    """
    prefix = 'isupport'

    def __init__(self):
        self._features = {
            'CHANNELLEN': 200,
            'CHANTYPES': tuple('#&'),
            'MODES': 3,
            'NICKLEN': 9,
            'PREFIX': self._parsePrefixParam('(ovh)@+%'),
            # The ISUPPORT draft explicitly says that there is no default for
            # CHANMODES, but we're defaulting it here to handle the case where
            # the IRC server doesn't send us any ISUPPORT information, since
            # IRCClient.getChannelModeParams relies on this value.
            'CHANMODES': self._parseChanModesParam(['b', '', 'lk'])}


    def _splitParamArgs(cls, params, valueProcessor=None):
        """
        Split ISUPPORT parameter arguments.

        Values can optionally be processed by C{valueProcessor}.

        For example::

            >>> ServerSupportedFeatures._splitParamArgs(['A:1', 'B:2'])
            (('A', '1'), ('B', '2'))

        @type params: C{iterable} of C{str}

        @type valueProcessor: C{callable} taking {str}
        @param valueProcessor: Callable to process argument values, or C{None}
            to perform no processing

        @rtype: C{list} of C{(str, object)}
        @return: Sequence of C{(name, processedValue)}
        """
        if valueProcessor is None:
            valueProcessor = lambda x: x

        def _parse():
            for param in params:
                if ':' not in param:
                    param += ':'
                a, b = param.split(':', 1)
                yield a, valueProcessor(b)
        return list(_parse())
    _splitParamArgs = classmethod(_splitParamArgs)


    def _unescapeParamValue(cls, value):
        """
        Unescape an ISUPPORT parameter.

        The only form of supported escape is C{\\xHH}, where HH must be a valid
        2-digit hexadecimal number.

        @rtype: C{str}
        """
        def _unescape():
            parts = value.split('\\x')
            # The first part can never be preceeded by the escape.
            yield parts.pop(0)
            for s in parts:
                octet, rest = s[:2], s[2:]
                try:
                    octet = int(octet, 16)
                except ValueError:
                    raise ValueError('Invalid hex octet: %r' % (octet,))
                yield chr(octet) + rest

        if '\\x' not in value:
            return value
        return ''.join(_unescape())
    _unescapeParamValue = classmethod(_unescapeParamValue)


    def _splitParam(cls, param):
        """
        Split an ISUPPORT parameter.

        @type param: C{str}

        @rtype: C{(str, list)}
        @return C{(key, arguments)}
        """
        if '=' not in param:
            param += '='
        key, value = param.split('=', 1)
        return key, map(cls._unescapeParamValue, value.split(','))
    _splitParam = classmethod(_splitParam)


    def _parsePrefixParam(cls, prefix):
        """
        Parse the ISUPPORT "PREFIX" parameter.

        The order in which the parameter arguments appear is significant, the
        earlier a mode appears the more privileges it gives.

        @rtype: C{dict} mapping C{str} to C{(str, int)}
        @return: A dictionary mapping a mode character to a two-tuple of
            C({symbol, priority)}, the lower a priority (the lowest being
            C{0}) the more privileges it gives
        """
        if not prefix:
            return None
        if prefix[0] != '(' and ')' not in prefix:
            raise ValueError('Malformed PREFIX parameter')
        modes, symbols = prefix.split(')', 1)
        symbols = zip(symbols, xrange(len(symbols)))
        modes = modes[1:]
        return dict(zip(modes, symbols))
    _parsePrefixParam = classmethod(_parsePrefixParam)


    def _parseChanModesParam(self, params):
        """
        Parse the ISUPPORT "CHANMODES" parameter.

        See L{isupport_CHANMODES} for a detailed explanation of this parameter.
        """
        names = ('addressModes', 'param', 'setParam', 'noParam')
        if len(params) > len(names):
            raise ValueError(
                'Expecting a maximum of %d channel mode parameters, got %d' % (
                    len(names), len(params)))
        items = map(lambda key, value: (key, value or ''), names, params)
        return dict(items)
    _parseChanModesParam = classmethod(_parseChanModesParam)


    def getFeature(self, feature, default=None):
        """
        Get a server supported feature's value.

        A feature with the value C{None} is equivalent to the feature being
        unsupported.

        @type feature: C{str}
        @param feature: Feature name

        @type default: C{object}
        @param default: The value to default to, assuming that C{feature}
            is not supported

        @return: Feature value
        """
        return self._features.get(feature, default)


    def hasFeature(self, feature):
        """
        Determine whether a feature is supported or not.

        @rtype: C{bool}
        """
        return self.getFeature(feature) is not None


    def parse(self, params):
        """
        Parse ISUPPORT parameters.

        If an unknown parameter is encountered, it is simply added to the
        dictionary, keyed by its name, as a tuple of the parameters provided.

        @type params: C{iterable} of C{str}
        @param params: Iterable of ISUPPORT parameters to parse
        """
        for param in params:
            key, value = self._splitParam(param)
            if key.startswith('-'):
                self._features.pop(key[1:], None)
            else:
                self._features[key] = self.dispatch(key, value)


    def isupport_unknown(self, command, params):
        """
        Unknown ISUPPORT parameter.
        """
        return tuple(params)


    def isupport_CHANLIMIT(self, params):
        """
        The maximum number of each channel type a user may join.
        """
        return self._splitParamArgs(params, _intOrDefault)


    def isupport_CHANMODES(self, params):
        """
        Available channel modes.

        There are 4 categories of channel mode::

            addressModes - Modes that add or remove an address to or from a
            list, these modes always take a parameter.

            param - Modes that change a setting on a channel, these modes
            always take a parameter.

            setParam - Modes that change a setting on a channel, these modes
            only take a parameter when being set.

            noParam - Modes that change a setting on a channel, these modes
            never take a parameter.
        """
        try:
            return self._parseChanModesParam(params)
        except ValueError:
            return self.getFeature('CHANMODES')


    def isupport_CHANNELLEN(self, params):
        """
        Maximum length of a channel name a client may create.
        """
        return _intOrDefault(params[0], self.getFeature('CHANNELLEN'))


    def isupport_CHANTYPES(self, params):
        """
        Valid channel prefixes.
        """
        return tuple(params[0])


    def isupport_EXCEPTS(self, params):
        """
        Mode character for "ban exceptions".

        The presence of this parameter indicates that the server supports
        this functionality.
        """
        return params[0] or 'e'


    def isupport_IDCHAN(self, params):
        """
        Safe channel identifiers.

        The presence of this parameter indicates that the server supports
        this functionality.
        """
        return self._splitParamArgs(params)


    def isupport_INVEX(self, params):
        """
        Mode character for "invite exceptions".

        The presence of this parameter indicates that the server supports
        this functionality.
        """
        return params[0] or 'I'


    def isupport_KICKLEN(self, params):
        """
        Maximum length of a kick message a client may provide.
        """
        return _intOrDefault(params[0])


    def isupport_MAXLIST(self, params):
        """
        Maximum number of "list modes" a client may set on a channel at once.

        List modes are identified by the "addressModes" key in CHANMODES.
        """
        return self._splitParamArgs(params, _intOrDefault)


    def isupport_MODES(self, params):
        """
        Maximum number of modes accepting parameters that may be sent, by a
        client, in a single MODE command.
        """
        return _intOrDefault(params[0])


    def isupport_NETWORK(self, params):
        """
        IRC network name.
        """
        return params[0]


    def isupport_NICKLEN(self, params):
        """
        Maximum length of a nickname the client may use.
        """
        return _intOrDefault(params[0], self.getFeature('NICKLEN'))


    def isupport_PREFIX(self, params):
        """
        Mapping of channel modes that clients may have to status flags.
        """
        try:
            return self._parsePrefixParam(params[0])
        except ValueError:
            return self.getFeature('PREFIX')


    def isupport_SAFELIST(self, params):
        """
        Flag indicating that a client may request a LIST without being
        disconnected due to the large amount of data generated.
        """
        return True


    def isupport_STATUSMSG(self, params):
        """
        The server supports sending messages to only to clients on a channel
        with a specific status.
        """
        return params[0]


    def isupport_TARGMAX(self, params):
        """
        Maximum number of targets allowable for commands that accept multiple
        targets.
        """
        return dict(self._splitParamArgs(params, _intOrDefault))


    def isupport_TOPICLEN(self, params):
        """
        Maximum length of a topic that may be set.
        """
        return _intOrDefault(params[0])



class IRCClient(basic.LineReceiver):
    """
    Internet Relay Chat client protocol, with sprinkles.

    In addition to providing an interface for an IRC client protocol,
    this class also contains reasonable implementations of many common
    CTCP methods.

    TODO
    ====
     - Limit the length of messages sent (because the IRC server probably
       does).
     - Add flood protection/rate limiting for my CTCP replies.
     - NickServ cooperation.  (a mix-in?)

    @ivar nickname: Nickname the client will use.
    @ivar password: Password used to log on to the server.  May be C{None}.
    @ivar realname: Supplied to the server during login as the "Real name"
        or "ircname".  May be C{None}.
    @ivar username: Supplied to the server during login as the "User name".
        May be C{None}

    @ivar userinfo: Sent in reply to a C{USERINFO} CTCP query.  If C{None}, no
        USERINFO reply will be sent.
        "This is used to transmit a string which is settable by
        the user (and never should be set by the client)."
    @ivar fingerReply: Sent in reply to a C{FINGER} CTCP query.  If C{None}, no
        FINGER reply will be sent.
    @type fingerReply: Callable or String

    @ivar versionName: CTCP VERSION reply, client name.  If C{None}, no VERSION
        reply will be sent.
    @type versionName: C{str}, or None.
    @ivar versionNum: CTCP VERSION reply, client version.
    @type versionNum: C{str}, or None.
    @ivar versionEnv: CTCP VERSION reply, environment the client is running in.
    @type versionEnv: C{str}, or None.

    @ivar sourceURL: CTCP SOURCE reply, a URL where the source code of this
        client may be found.  If C{None}, no SOURCE reply will be sent.

    @ivar lineRate: Minimum delay between lines sent to the server.  If
        C{None}, no delay will be imposed.
    @type lineRate: Number of Seconds.

    @ivar motd: Either L{None} or, between receipt of I{RPL_MOTDSTART} and
        I{RPL_ENDOFMOTD}, a L{list} of L{str}, each of which is the content
        of an I{RPL_MOTD} message.

    @ivar erroneousNickFallback: Default nickname assigned when an unregistered
        client triggers an C{ERR_ERRONEUSNICKNAME} while trying to register
        with an illegal nickname.
    @type erroneousNickFallback: C{str}

    @ivar _registered: Whether or not the user is registered. It becomes True
        once a welcome has been received from the server.
    @type _registered: C{bool}

    @ivar _attemptedNick: The nickname that will try to get registered. It may
        change if it is illegal or already taken. L{nickname} becomes the
        L{_attemptedNick} that is successfully registered.
    @type _attemptedNick:  C{str}

    @type supported: L{ServerSupportedFeatures}
    @ivar supported: Available ISUPPORT features on the server

    @type hostname: C{str}
    @ivar hostname: Host name of the IRC server the client is connected to.
        Initially the host name is C{None} and later is set to the host name
        from which the I{RPL_WELCOME} message is received.

    @type _heartbeat: L{task.LoopingCall}
    @ivar _heartbeat: Looping call to perform the keepalive by calling
        L{IRCClient._sendHeartbeat} every L{heartbeatInterval} seconds, or
        C{None} if there is no heartbeat.

    @type heartbeatInterval: C{float}
    @ivar heartbeatInterval: Interval, in seconds, to send I{PING} messages to
        the server as a form of keepalive, defaults to 120 seconds. Use C{None}
        to disable the heartbeat.
    """
    hostname = None
    motd = None
    nickname = 'irc'
    password = None
    realname = None
    username = None
    ### Responses to various CTCP queries.

    userinfo = None
    # fingerReply is a callable returning a string, or a str()able object.
    fingerReply = None
    versionName = None
    versionNum = None
    versionEnv = None

    sourceURL = "http://twistedmatrix.com/downloads/"

    dcc_destdir = '.'
    dcc_sessions = None

    # If this is false, no attempt will be made to identify
    # ourself to the server.
    performLogin = 1

    lineRate = None
    _queue = None
    _queueEmptying = None

    delimiter = '\n' # '\r\n' will also work (see dataReceived)

    __pychecker__ = 'unusednames=params,prefix,channel'

    _registered = False
    _attemptedNick = ''
    erroneousNickFallback = 'defaultnick'

    _heartbeat = None
    heartbeatInterval = 120


    def _reallySendLine(self, line):
        return basic.LineReceiver.sendLine(self, lowQuote(line) + '\r')

    def sendLine(self, line):
        if self.lineRate is None:
            self._reallySendLine(line)
        else:
            self._queue.append(line)
            if not self._queueEmptying:
                self._sendLine()

    def _sendLine(self):
        if self._queue:
            self._reallySendLine(self._queue.pop(0))
            self._queueEmptying = reactor.callLater(self.lineRate,
                                                    self._sendLine)
        else:
            self._queueEmptying = None


    def connectionLost(self, reason):
        basic.LineReceiver.connectionLost(self, reason)
        self.stopHeartbeat()


    def _createHeartbeat(self):
        """
        Create the heartbeat L{LoopingCall}.
        """
        return task.LoopingCall(self._sendHeartbeat)


    def _sendHeartbeat(self):
        """
        Send a I{PING} message to the IRC server as a form of keepalive.
        """
        self.sendLine('PING ' + self.hostname)


    def stopHeartbeat(self):
        """
        Stop sending I{PING} messages to keep the connection to the server
        alive.

        @since: 11.1
        """
        if self._heartbeat is not None:
            self._heartbeat.stop()
            self._heartbeat = None


    def startHeartbeat(self):
        """
        Start sending I{PING} messages every L{IRCClient.heartbeatInterval}
        seconds to keep the connection to the server alive during periods of no
        activity.

        @since: 11.1
        """
        self.stopHeartbeat()
        if self.heartbeatInterval is None:
            return
        self._heartbeat = self._createHeartbeat()
        self._heartbeat.start(self.heartbeatInterval, now=False)


    ### Interface level client->user output methods
    ###
    ### You'll want to override these.

    ### Methods relating to the server itself

    def created(self, when):
        """
        Called with creation date information about the server, usually at logon.

        @type when: C{str}
        @param when: A string describing when the server was created, probably.
        """

    def yourHost(self, info):
        """
        Called with daemon information about the server, usually at logon.

        @type info: C{str}
        @param when: A string describing what software the server is running, probably.
        """

    def myInfo(self, servername, version, umodes, cmodes):
        """
        Called with information about the server, usually at logon.

        @type servername: C{str}
        @param servername: The hostname of this server.

        @type version: C{str}
        @param version: A description of what software this server runs.

        @type umodes: C{str}
        @param umodes: All the available user modes.

        @type cmodes: C{str}
        @param cmodes: All the available channel modes.
        """

    def luserClient(self, info):
        """
        Called with information about the number of connections, usually at logon.

        @type info: C{str}
        @param info: A description of the number of clients and servers
        connected to the network, probably.
        """

    def bounce(self, info):
        """
        Called with information about where the client should reconnect.

        @type info: C{str}
        @param info: A plaintext description of the address that should be
        connected to.
        """

    def isupport(self, options):
        """
        Called with various information about what the server supports.

        @type options: C{list} of C{str}
        @param options: Descriptions of features or limits of the server, possibly
        in the form "NAME=VALUE".
        """

    def luserChannels(self, channels):
        """
        Called with the number of channels existant on the server.

        @type channels: C{int}
        """

    def luserOp(self, ops):
        """
        Called with the number of ops logged on to the server.

        @type ops: C{int}
        """

    def luserMe(self, info):
        """
        Called with information about the server connected to.

        @type info: C{str}
        @param info: A plaintext string describing the number of users and servers
        connected to this server.
        """

    ### Methods involving me directly

    def privmsg(self, user, channel, message):
        """
        Called when I have a message from a user to me or a channel.
        """
        pass

    def joined(self, channel):
        """
        Called when I finish joining a channel.

        channel has the starting character (C{'#'}, C{'&'}, C{'!'}, or C{'+'})
        intact.
        """

    def left(self, channel):
        """
        Called when I have left a channel.

        channel has the starting character (C{'#'}, C{'&'}, C{'!'}, or C{'+'})
        intact.
        """


    def noticed(self, user, channel, message):
        """
        Called when I have a notice from a user to me or a channel.

        If the client makes any automated replies, it must not do so in
        response to a NOTICE message, per the RFC::

            The difference between NOTICE and PRIVMSG is that
            automatic replies MUST NEVER be sent in response to a
            NOTICE message. [...] The object of this rule is to avoid
            loops between clients automatically sending something in
            response to something it received.
        """


    def modeChanged(self, user, channel, set, modes, args):
        """
        Called when users or channel's modes are changed.

        @type user: C{str}
        @param user: The user and hostmask which instigated this change.

        @type channel: C{str}
        @param channel: The channel where the modes are changed. If args is
        empty the channel for which the modes are changing. If the changes are
        at server level it could be equal to C{user}.

        @type set: C{bool} or C{int}
        @param set: True if the mode(s) is being added, False if it is being
        removed. If some modes are added and others removed at the same time
        this function will be called twice, the first time with all the added
        modes, the second with the removed ones. (To change this behaviour
        override the irc_MODE method)

        @type modes: C{str}
        @param modes: The mode or modes which are being changed.

        @type args: C{tuple}
        @param args: Any additional information required for the mode
        change.
        """

    def pong(self, user, secs):
        """
        Called with the results of a CTCP PING query.
        """
        pass

    def signedOn(self):
        """
        Called after sucessfully signing on to the server.
        """
        pass

    def kickedFrom(self, channel, kicker, message):
        """
        Called when I am kicked from a channel.
        """
        pass

    def nickChanged(self, nick):
        """
        Called when my nick has been changed.
        """
        self.nickname = nick


    ### Things I observe other people doing in a channel.

    def userJoined(self, user, channel):
        """
        Called when I see another user joining a channel.
        """
        pass

    def userLeft(self, user, channel):
        """
        Called when I see another user leaving a channel.
        """
        pass

    def userQuit(self, user, quitMessage):
        """
        Called when I see another user disconnect from the network.
        """
        pass

    def userKicked(self, kickee, channel, kicker, message):
        """
        Called when I observe someone else being kicked from a channel.
        """
        pass

    def action(self, user, channel, data):
        """
        Called when I see a user perform an ACTION on a channel.
        """
        pass

    def topicUpdated(self, user, channel, newTopic):
        """
        In channel, user changed the topic to newTopic.

        Also called when first joining a channel.
        """
        pass

    def userRenamed(self, oldname, newname):
        """
        A user changed their name from oldname to newname.
        """
        pass

    ### Information from the server.

    def receivedMOTD(self, motd):
        """
        I received a message-of-the-day banner from the server.

        motd is a list of strings, where each string was sent as a seperate
        message from the server. To display, you might want to use::

            '\\n'.join(motd)

        to get a nicely formatted string.
        """
        pass

    ### user input commands, client->server
    ### Your client will want to invoke these.

    def join(self, channel, key=None):
        """
        Join a channel.

        @type channel: C{str}
        @param channel: The name of the channel to join. If it has no prefix,
            C{'#'} will be prepended to it.
        @type key: C{str}
        @param key: If specified, the key used to join the channel.
        """
        if channel[0] not in CHANNEL_PREFIXES:
            channel = '#' + channel
        if key:
            self.sendLine("JOIN %s %s" % (channel, key))
        else:
            self.sendLine("JOIN %s" % (channel,))

    def leave(self, channel, reason=None):
        """
        Leave a channel.

        @type channel: C{str}
        @param channel: The name of the channel to leave. If it has no prefix,
            C{'#'} will be prepended to it.
        @type reason: C{str}
        @param reason: If given, the reason for leaving.
        """
        if channel[0] not in CHANNEL_PREFIXES:
            channel = '#' + channel
        if reason:
            self.sendLine("PART %s :%s" % (channel, reason))
        else:
            self.sendLine("PART %s" % (channel,))

    def kick(self, channel, user, reason=None):
        """
        Attempt to kick a user from a channel.

        @type channel: C{str}
        @param channel: The name of the channel to kick the user from. If it has
            no prefix, C{'#'} will be prepended to it.
        @type user: C{str}
        @param user: The nick of the user to kick.
        @type reason: C{str}
        @param reason: If given, the reason for kicking the user.
        """
        if channel[0] not in CHANNEL_PREFIXES:
            channel = '#' + channel
        if reason:
            self.sendLine("KICK %s %s :%s" % (channel, user, reason))
        else:
            self.sendLine("KICK %s %s" % (channel, user))

    part = leave


    def invite(self, user, channel):
        """
        Attempt to invite user to channel

        @type user: C{str}
        @param user: The user to invite
        @type channel: C{str}
        @param channel: The channel to invite the user too

        @since: 11.0
        """
        if channel[0] not in CHANNEL_PREFIXES:
            channel = '#' + channel
        self.sendLine("INVITE %s %s" % (user, channel))


    def topic(self, channel, topic=None):
        """
        Attempt to set the topic of the given channel, or ask what it is.

        If topic is None, then I sent a topic query instead of trying to set the
        topic. The server should respond with a TOPIC message containing the
        current topic of the given channel.

        @type channel: C{str}
        @param channel: The name of the channel to change the topic on. If it
            has no prefix, C{'#'} will be prepended to it.
        @type topic: C{str}
        @param topic: If specified, what to set the topic to.
        """
        # << TOPIC #xtestx :fff
        if channel[0] not in CHANNEL_PREFIXES:
            channel = '#' + channel
        if topic != None:
            self.sendLine("TOPIC %s :%s" % (channel, topic))
        else:
            self.sendLine("TOPIC %s" % (channel,))


    def mode(self, chan, set, modes, limit = None, user = None, mask = None):
        """
        Change the modes on a user or channel.

        The C{limit}, C{user}, and C{mask} parameters are mutually exclusive.

        @type chan: C{str}
        @param chan: The name of the channel to operate on.
        @type set: C{bool}
        @param set: True to give the user or channel permissions and False to
            remove them.
        @type modes: C{str}
        @param modes: The mode flags to set on the user or channel.
        @type limit: C{int}
        @param limit: In conjuction with the C{'l'} mode flag, limits the
             number of users on the channel.
        @type user: C{str}
        @param user: The user to change the mode on.
        @type mask: C{str}
        @param mask: In conjuction with the C{'b'} mode flag, sets a mask of
            users to be banned from the channel.
        """
        if set:
            line = 'MODE %s +%s' % (chan, modes)
        else:
            line = 'MODE %s -%s' % (chan, modes)
        if limit is not None:
            line = '%s %d' % (line, limit)
        elif user is not None:
            line = '%s %s' % (line, user)
        elif mask is not None:
            line = '%s %s' % (line, mask)
        self.sendLine(line)


    def say(self, channel, message, length=None):
        """
        Send a message to a channel

        @type channel: C{str}
        @param channel: The channel to say the message on. If it has no prefix,
            C{'#'} will be prepended to it.
        @type message: C{str}
        @param message: The message to say.
        @type length: C{int}
        @param length: The maximum number of octets to send at a time.  This has
            the effect of turning a single call to C{msg()} into multiple
            commands to the server.  This is useful when long messages may be
            sent that would otherwise cause the server to kick us off or
            silently truncate the text we are sending.  If None is passed, the
            entire message is always send in one command.
        """
        if channel[0] not in CHANNEL_PREFIXES:
            channel = '#' + channel
        self.msg(channel, message, length)


    def _safeMaximumLineLength(self, command):
        """
        Estimate a safe maximum line length for the given command.

        This is done by assuming the maximum values for nickname length,
        realname and hostname combined with the command that needs to be sent
        and some guessing. A theoretical maximum value is used because it is
        possible that our nickname, username or hostname changes (on the server
        side) while the length is still being calculated.
        """
        # :nickname!realname@hostname COMMAND ...
        theoretical = ':%s!%s@%s %s' % (
            'a' * self.supported.getFeature('NICKLEN'),
            # This value is based on observation.
            'b' * 10,
            # See <http://tools.ietf.org/html/rfc2812#section-2.3.1>.
            'c' * 63,
            command)
        # Fingers crossed.
        fudge = 10
        return MAX_COMMAND_LENGTH - len(theoretical) - fudge


    def msg(self, user, message, length=None):
        """
        Send a message to a user or channel.

        The message will be split into multiple commands to the server if:
         - The message contains any newline characters
         - Any span between newline characters is longer than the given
           line-length.

        @param user: Username or channel name to which to direct the
            message.
        @type user: C{str}

        @param message: Text to send.
        @type message: C{str}

        @param length: Maximum number of octets to send in a single
            command, including the IRC protocol framing. If C{None} is given
            then L{IRCClient._safeMaximumLineLength} is used to determine a
            value.
        @type length: C{int}
        """
        fmt = 'PRIVMSG %s :' % (user,)

        if length is None:
            length = self._safeMaximumLineLength(fmt)

        # Account for the line terminator.
        minimumLength = len(fmt) + 2
        if length <= minimumLength:
            raise ValueError("Maximum length must exceed %d for message "
                             "to %s" % (minimumLength, user))
        for line in split(message, length - minimumLength):
            self.sendLine(fmt + line)


    def notice(self, user, message):
        """
        Send a notice to a user.

        Notices are like normal message, but should never get automated
        replies.

        @type user: C{str}
        @param user: The user to send a notice to.
        @type message: C{str}
        @param message: The contents of the notice to send.
        """
        self.sendLine("NOTICE %s :%s" % (user, message))


    def away(self, message=''):
        """
        Mark this client as away.

        @type message: C{str}
        @param message: If specified, the away message.
        """
        self.sendLine("AWAY :%s" % message)


    def back(self):
        """
        Clear the away status.
        """
        # An empty away marks us as back
        self.away()


    def whois(self, nickname, server=None):
        """
        Retrieve user information about the given nick name.

        @type nickname: C{str}
        @param nickname: The nick name about which to retrieve information.

        @since: 8.2
        """
        if server is None:
            self.sendLine('WHOIS ' + nickname)
        else:
            self.sendLine('WHOIS %s %s' % (server, nickname))


    def register(self, nickname, hostname='foo', servername='bar'):
        """
        Login to the server.

        @type nickname: C{str}
        @param nickname: The nickname to register.
        @type hostname: C{str}
        @param hostname: If specified, the hostname to logon as.
        @type servername: C{str}
        @param servername: If specified, the servername to logon as.
        """
        if self.password is not None:
            self.sendLine("PASS %s" % self.password)
        self.setNick(nickname)
        if self.username is None:
            self.username = nickname
        self.sendLine("USER %s %s %s :%s" % (self.username, hostname, servername, self.realname))


    def setNick(self, nickname):
        """
        Set this client's nickname.

        @type nickname: C{str}
        @param nickname: The nickname to change to.
        """
        self._attemptedNick = nickname
        self.sendLine("NICK %s" % nickname)


    def quit(self, message = ''):
        """
        Disconnect from the server

        @type message: C{str}

        @param message: If specified, the message to give when quitting the
            server.
        """
        self.sendLine("QUIT :%s" % message)

    ### user input commands, client->client

    def describe(self, channel, action):
        """
        Strike a pose.

        @type channel: C{str}
        @param channel: The name of the channel to have an action on. If it
            has no prefix, it is sent to the user of that name.
        @type action: C{str}
        @param action: The action to preform.
        @since: 9.0
        """
        self.ctcpMakeQuery(channel, [('ACTION', action)])


    _pings = None
    _MAX_PINGRING = 12

    def ping(self, user, text = None):
        """
        Measure round-trip delay to another IRC client.
        """
        if self._pings is None:
            self._pings = {}

        if text is None:
            chars = string.letters + string.digits + string.punctuation
            key = ''.join([random.choice(chars) for i in range(12)])
        else:
            key = str(text)
        self._pings[(user, key)] = time.time()
        self.ctcpMakeQuery(user, [('PING', key)])

        if len(self._pings) > self._MAX_PINGRING:
            # Remove some of the oldest entries.
            byValue = [(v, k) for (k, v) in self._pings.items()]
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

        args = ['SEND', name, my_address, str(port)]

        if not (size is None):
            args.append(size)

        args = string.join(args, ' ')

        self.ctcpMakeQuery(user, [('DCC', args)])


    def dccResume(self, user, fileName, port, resumePos):
        """
        Send a DCC RESUME request to another user.
        """
        self.ctcpMakeQuery(user, [
            ('DCC', ['RESUME', fileName, port, resumePos])])


    def dccAcceptResume(self, user, fileName, port, resumePos):
        """
        Send a DCC ACCEPT response to clients who have requested a resume.
        """
        self.ctcpMakeQuery(user, [
            ('DCC', ['ACCEPT', fileName, port, resumePos])])

    ### server->client messages
    ### You might want to fiddle with these,
    ### but it is safe to leave them alone.

    def irc_ERR_NICKNAMEINUSE(self, prefix, params):
        """
        Called when we try to register or change to a nickname that is already
        taken.
        """
        self._attemptedNick = self.alterCollidedNick(self._attemptedNick)
        self.setNick(self._attemptedNick)


    def alterCollidedNick(self, nickname):
        """
        Generate an altered version of a nickname that caused a collision in an
        effort to create an unused related name for subsequent registration.

        @param nickname: The nickname a user is attempting to register.
        @type nickname: C{str}

        @returns: A string that is in some way different from the nickname.
        @rtype: C{str}
        """
        return nickname + '_'


    def irc_ERR_ERRONEUSNICKNAME(self, prefix, params):
        """
        Called when we try to register or change to an illegal nickname.

        The server should send this reply when the nickname contains any
        disallowed characters.  The bot will stall, waiting for RPL_WELCOME, if
        we don't handle this during sign-on.

        @note: The method uses the spelling I{erroneus}, as it appears in
            the RFC, section 6.1.
        """
        if not self._registered:
            self.setNick(self.erroneousNickFallback)


    def irc_ERR_PASSWDMISMATCH(self, prefix, params):
        """
        Called when the login was incorrect.
        """
        raise IRCPasswordMismatch("Password Incorrect.")


    def irc_RPL_WELCOME(self, prefix, params):
        """
        Called when we have received the welcome from the server.
        """
        self.hostname = prefix
        self._registered = True
        self.nickname = self._attemptedNick
        self.signedOn()
        self.startHeartbeat()


    def irc_JOIN(self, prefix, params):
        """
        Called when a user joins a channel.
        """
        nick = string.split(prefix,'!')[0]
        channel = params[-1]
        if nick == self.nickname:
            self.joined(channel)
        else:
            self.userJoined(nick, channel)

    def irc_PART(self, prefix, params):
        """
        Called when a user leaves a channel.
        """
        nick = string.split(prefix,'!')[0]
        channel = params[0]
        if nick == self.nickname:
            self.left(channel)
        else:
            self.userLeft(nick, channel)

    def irc_QUIT(self, prefix, params):
        """
        Called when a user has quit.
        """
        nick = string.split(prefix,'!')[0]
        self.userQuit(nick, params[0])


    def irc_MODE(self, user, params):
        """
        Parse a server mode change message.
        """
        channel, modes, args = params[0], params[1], params[2:]

        if modes[0] not in '-+':
            modes = '+' + modes

        if channel == self.nickname:
            # This is a mode change to our individual user, not a channel mode
            # that involves us.
            paramModes = self.getUserModeParams()
        else:
            paramModes = self.getChannelModeParams()

        try:
            added, removed = parseModes(modes, args, paramModes)
        except IRCBadModes:
            log.err(None, 'An error occured while parsing the following '
                          'MODE message: MODE %s' % (' '.join(params),))
        else:
            if added:
                modes, params = zip(*added)
                self.modeChanged(user, channel, True, ''.join(modes), params)

            if removed:
                modes, params = zip(*removed)
                self.modeChanged(user, channel, False, ''.join(modes), params)


    def irc_PING(self, prefix, params):
        """
        Called when some has pinged us.
        """
        self.sendLine("PONG %s" % params[-1])

    def irc_PRIVMSG(self, prefix, params):
        """
        Called when we get a message.
        """
        user = prefix
        channel = params[0]
        message = params[-1]

        if not message:
            # Don't raise an exception if we get blank message.
            return

        if message[0] == X_DELIM:
            m = ctcpExtract(message)
            if m['extended']:
                self.ctcpQuery(user, channel, m['extended'])

            if not m['normal']:
                return

            message = string.join(m['normal'], ' ')

        self.privmsg(user, channel, message)

    def irc_NOTICE(self, prefix, params):
        """
        Called when a user gets a notice.
        """
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

    def irc_NICK(self, prefix, params):
        """
        Called when a user changes their nickname.
        """
        nick = string.split(prefix,'!', 1)[0]
        if nick == self.nickname:
            self.nickChanged(params[0])
        else:
            self.userRenamed(nick, params[0])

    def irc_KICK(self, prefix, params):
        """
        Called when a user is kicked from a channel.
        """
        kicker = string.split(prefix,'!')[0]
        channel = params[0]
        kicked = params[1]
        message = params[-1]
        if string.lower(kicked) == string.lower(self.nickname):
            # Yikes!
            self.kickedFrom(channel, kicker, message)
        else:
            self.userKicked(kicked, channel, kicker, message)

    def irc_TOPIC(self, prefix, params):
        """
        Someone in the channel set the topic.
        """
        user = string.split(prefix, '!')[0]
        channel = params[0]
        newtopic = params[1]
        self.topicUpdated(user, channel, newtopic)

    def irc_RPL_TOPIC(self, prefix, params):
        """
        Called when the topic for a channel is initially reported or when it
        subsequently changes.
        """
        user = string.split(prefix, '!')[0]
        channel = params[1]
        newtopic = params[2]
        self.topicUpdated(user, channel, newtopic)

    def irc_RPL_NOTOPIC(self, prefix, params):
        user = string.split(prefix, '!')[0]
        channel = params[1]
        newtopic = ""
        self.topicUpdated(user, channel, newtopic)

    def irc_RPL_MOTDSTART(self, prefix, params):
        if params[-1].startswith("- "):
            params[-1] = params[-1][2:]
        self.motd = [params[-1]]

    def irc_RPL_MOTD(self, prefix, params):
        if params[-1].startswith("- "):
            params[-1] = params[-1][2:]
        if self.motd is None:
            self.motd = []
        self.motd.append(params[-1])


    def irc_RPL_ENDOFMOTD(self, prefix, params):
        """
        I{RPL_ENDOFMOTD} indicates the end of the message of the day
        messages.  Deliver the accumulated lines to C{receivedMOTD}.
        """
        motd = self.motd
        self.motd = None
        self.receivedMOTD(motd)


    def irc_RPL_CREATED(self, prefix, params):
        self.created(params[1])

    def irc_RPL_YOURHOST(self, prefix, params):
        self.yourHost(params[1])

    def irc_RPL_MYINFO(self, prefix, params):
        info = params[1].split(None, 3)
        while len(info) < 4:
            info.append(None)
        self.myInfo(*info)

    def irc_RPL_BOUNCE(self, prefix, params):
        self.bounce(params[1])

    def irc_RPL_ISUPPORT(self, prefix, params):
        args = params[1:-1]
        # Several ISUPPORT messages, in no particular order, may be sent
        # to the client at any given point in time (usually only on connect,
        # though.) For this reason, ServerSupportedFeatures.parse is intended
        # to mutate the supported feature list.
        self.supported.parse(args)
        self.isupport(args)

    def irc_RPL_LUSERCLIENT(self, prefix, params):
        self.luserClient(params[1])

    def irc_RPL_LUSEROP(self, prefix, params):
        try:
            self.luserOp(int(params[1]))
        except ValueError:
            pass

    def irc_RPL_LUSERCHANNELS(self, prefix, params):
        try:
            self.luserChannels(int(params[1]))
        except ValueError:
            pass

    def irc_RPL_LUSERME(self, prefix, params):
        self.luserMe(params[1])

    def irc_unknown(self, prefix, command, params):
        pass

    ### Receiving a CTCP query from another party
    ### It is safe to leave these alone.


    def ctcpQuery(self, user, channel, messages):
        """
        Dispatch method for any CTCP queries received.

        Duplicated CTCP queries are ignored and no dispatch is
        made. Unrecognized CTCP queries invoke L{IRCClient.ctcpUnknownQuery}.
        """
        seen = set()
        for tag, data in messages:
            method = getattr(self, 'ctcpQuery_%s' % tag, None)
            if tag not in seen:
                if method is not None:
                    method(user, channel, data)
                else:
                    self.ctcpUnknownQuery(user, channel, tag, data)
            seen.add(tag)


    def ctcpUnknownQuery(self, user, channel, tag, data):
        """
        Fallback handler for unrecognized CTCP queries.

        No CTCP I{ERRMSG} reply is made to remove a potential denial of service
        avenue.
        """
        log.msg('Unknown CTCP query from %r: %r %r' % (user, tag, data))


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

        if callable(self.fingerReply):
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
                                        self.versionNum or '',
                                        self.versionEnv or ''))])

    def ctcpQuery_SOURCE(self, user, channel, data):
        if data is not None:
            self.quirkyMessage("Why did %s send '%s' with a SOURCE query?"
                               % (user, data))
        if self.sourceURL:
            nick = string.split(user,"!")[0]
            # The CTCP document (Zeuge, Rollo, Mesander 1994) says that SOURCE
            # replies should be responded to with the location of an anonymous
            # FTP server in host:directory:file format.  I'm taking the liberty
            # of bringing it into the 21st century by sending a URL instead.
            self.ctcpMakeReply(nick, [('SOURCE', self.sourceURL),
                                      ('SOURCE', None)])

    def ctcpQuery_USERINFO(self, user, channel, data):
        if data is not None:
            self.quirkyMessage("Why did %s send '%s' with a USERINFO query?"
                               % (user, data))
        if self.userinfo:
            nick = string.split(user,"!")[0]
            self.ctcpMakeReply(nick, [('USERINFO', self.userinfo)])

    def ctcpQuery_CLIENTINFO(self, user, channel, data):
        """
        A master index of what CTCP tags this client knows.

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
        """

        if not data: return
        dcctype = data.split(None, 1)[0].upper()
        handler = getattr(self, "dcc_" + dcctype, None)
        if handler:
            if self.dcc_sessions is None:
                self.dcc_sessions = []
            data = data[len(dcctype)+1:]
            handler(user, channel, data)
        else:
            nick = string.split(user,"!")[0]
            self.ctcpMakeReply(nick, [('ERRMSG',
                                       "DCC %s :Unknown DCC type '%s'"
                                       % (data, dcctype))])
            self.quirkyMessage("%s offered unknown DCC type %s"
                               % (user, dcctype))

    def dcc_SEND(self, user, channel, data):
        # Use splitQuoted for those who send files with spaces in the names.
        data = text.splitQuoted(data)
        if len(data) < 3:
            raise IRCBadMessage, "malformed DCC SEND request: %r" % (data,)

        (filename, address, port) = data[:3]

        address = dccParseAddress(address)
        try:
            port = int(port)
        except ValueError:
            raise IRCBadMessage, "Indecipherable port %r" % (port,)

        size = -1
        if len(data) >= 4:
            try:
                size = int(data[3])
            except ValueError:
                pass

        # XXX Should we bother passing this data?
        self.dccDoSend(user, address, port, filename, size, data)

    def dcc_ACCEPT(self, user, channel, data):
        data = text.splitQuoted(data)
        if len(data) < 3:
            raise IRCBadMessage, "malformed DCC SEND ACCEPT request: %r" % (data,)
        (filename, port, resumePos) = data[:3]
        try:
            port = int(port)
            resumePos = int(resumePos)
        except ValueError:
            return

        self.dccDoAcceptResume(user, filename, port, resumePos)

    def dcc_RESUME(self, user, channel, data):
        data = text.splitQuoted(data)
        if len(data) < 3:
            raise IRCBadMessage, "malformed DCC SEND RESUME request: %r" % (data,)
        (filename, port, resumePos) = data[:3]
        try:
            port = int(port)
            resumePos = int(resumePos)
        except ValueError:
            return
        self.dccDoResume(user, filename, port, resumePos)

    def dcc_CHAT(self, user, channel, data):
        data = text.splitQuoted(data)
        if len(data) < 3:
            raise IRCBadMessage, "malformed DCC CHAT request: %r" % (data,)

        (filename, address, port) = data[:3]

        address = dccParseAddress(address)
        try:
            port = int(port)
        except ValueError:
            raise IRCBadMessage, "Indecipherable port %r" % (port,)

        self.dccDoChat(user, channel, address, port, data)

    ### The dccDo methods are the slightly higher-level siblings of
    ### common dcc_ methods; the arguments have been parsed for them.

    def dccDoSend(self, user, address, port, fileName, size, data):
        """Called when I receive a DCC SEND offer from a client.

        By default, I do nothing here."""
        ## filename = path.basename(arg)
        ## protocol = DccFileReceive(filename, size,
        ##                           (user,channel,data),self.dcc_destdir)
        ## reactor.clientTCP(address, port, protocol)
        ## self.dcc_sessions.append(protocol)
        pass

    def dccDoResume(self, user, file, port, resumePos):
        """Called when a client is trying to resume an offered file
        via DCC send.  It should be either replied to with a DCC
        ACCEPT or ignored (default)."""
        pass

    def dccDoAcceptResume(self, user, file, port, resumePos):
        """Called when a client has verified and accepted a DCC resume
        request made by us.  By default it will do nothing."""
        pass

    def dccDoChat(self, user, channel, address, port, data):
        pass
        #factory = DccChatFactory(self, queryData=(user, channel, data))
        #reactor.connectTCP(address, port, factory)
        #self.dcc_sessions.append(factory)

    #def ctcpQuery_SED(self, user, data):
    #    """Simple Encryption Doodoo
    #
    #    Feel free to implement this, but no specification is available.
    #    """
    #    raise NotImplementedError


    def ctcpMakeReply(self, user, messages):
        """
        Send one or more C{extended messages} as a CTCP reply.

        @type messages: a list of extended messages.  An extended
        message is a (tag, data) tuple, where 'data' may be C{None}.
        """
        self.notice(user, ctcpStringify(messages))

    ### client CTCP query commands

    def ctcpMakeQuery(self, user, messages):
        """
        Send one or more C{extended messages} as a CTCP query.

        @type messages: a list of extended messages.  An extended
        message is a (tag, data) tuple, where 'data' may be C{None}.
        """
        self.msg(user, ctcpStringify(messages))

    ### Receiving a response to a CTCP query (presumably to one we made)
    ### You may want to add methods here, or override UnknownReply.

    def ctcpReply(self, user, channel, messages):
        """
        Dispatch method for any CTCP replies received.
        """
        for m in messages:
            method = getattr(self, "ctcpReply_%s" % m[0], None)
            if method:
                method(user, channel, m[1])
            else:
                self.ctcpUnknownReply(user, channel, m[0], m[1])

    def ctcpReply_PING(self, user, channel, data):
        nick = user.split('!', 1)[0]
        if (not self._pings) or (not self._pings.has_key((nick, data))):
            raise IRCBadMessage,\
                  "Bogus PING response from %s: %s" % (user, data)

        t0 = self._pings[(nick, data)]
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
        self.supported = ServerSupportedFeatures()
        self._queue = []
        if self.performLogin:
            self.register(self.nickname)

    def dataReceived(self, data):
        basic.LineReceiver.dataReceived(self, data.replace('\r', ''))

    def lineReceived(self, line):
        line = lowDequote(line)
        try:
            prefix, command, params = parsemsg(line)
            if numeric_to_symbolic.has_key(command):
                command = numeric_to_symbolic[command]
            self.handleCommand(command, prefix, params)
        except IRCBadMessage:
            self.badMessage(line, *sys.exc_info())


    def getUserModeParams(self):
        """
        Get user modes that require parameters for correct parsing.

        @rtype: C{[str, str]}
        @return C{[add, remove]}
        """
        return ['', '']


    def getChannelModeParams(self):
        """
        Get channel modes that require parameters for correct parsing.

        @rtype: C{[str, str]}
        @return C{[add, remove]}
        """
        # PREFIX modes are treated as "type B" CHANMODES, they always take
        # parameter.
        params = ['', '']
        prefixes = self.supported.getFeature('PREFIX', {})
        params[0] = params[1] = ''.join(prefixes.iterkeys())

        chanmodes = self.supported.getFeature('CHANMODES')
        if chanmodes is not None:
            params[0] += chanmodes.get('addressModes', '')
            params[0] += chanmodes.get('param', '')
            params[1] = params[0]
            params[0] += chanmodes.get('setParam', '')
        return params


    def handleCommand(self, command, prefix, params):
        """Determine the function to call for the given command and call
        it with the given arguments.
        """
        method = getattr(self, "irc_%s" % command, None)
        try:
            if method is not None:
                method(prefix, params)
            else:
                self.irc_unknown(prefix, command, params)
        except:
            log.deferr()


    def __getstate__(self):
        dct = self.__dict__.copy()
        dct['dcc_sessions'] = None
        dct['_pings'] = None
        return dct


def dccParseAddress(address):
    if '.' in address:
        pass
    else:
        try:
            address = long(address)
        except ValueError:
            raise IRCBadMessage,\
                  "Indecipherable address %r" % (address,)
        else:
            address = (
                (address >> 24) & 0xFF,
                (address >> 16) & 0xFF,
                (address >> 8) & 0xFF,
                address & 0xFF,
                )
            address = '.'.join(map(str,address))
    return address


class DccFileReceiveBasic(protocol.Protocol, styles.Ephemeral):
    """Bare protocol to receive a Direct Client Connection SEND stream.

    This does enough to keep the other guy talking, but you'll want to
    extend my dataReceived method to *do* something with the data I get.
    """

    bytesReceived = 0

    def __init__(self, resumeOffset=0):
        self.bytesReceived = resumeOffset
        self.resume = (resumeOffset != 0)

    def dataReceived(self, data):
        """Called when data is received.

        Warning: This just acknowledges to the remote host that the
        data has been received; it doesn't *do* anything with the
        data, so you'll want to override this.
        """
        self.bytesReceived = self.bytesReceived + len(data)
        self.transport.write(struct.pack('!i', self.bytesReceived))


class DccSendProtocol(protocol.Protocol, styles.Ephemeral):
    """Protocol for an outgoing Direct Client Connection SEND.
    """

    blocksize = 1024
    file = None
    bytesSent = 0
    completed = 0
    connected = 0

    def __init__(self, file):
        if type(file) is types.StringType:
            self.file = open(file, 'r')

    def connectionMade(self):
        self.connected = 1
        self.sendBlock()

    def dataReceived(self, data):
        # XXX: Do we need to check to see if len(data) != fmtsize?

        bytesShesGot = struct.unpack("!I", data)
        if bytesShesGot < self.bytesSent:
            # Wait for her.
            # XXX? Add some checks to see if we've stalled out?
            return
        elif bytesShesGot > self.bytesSent:
            # self.transport.log("DCC SEND %s: She says she has %d bytes "
            #                    "but I've only sent %d.  I'm stopping "
            #                    "this screwy transfer."
            #                    % (self.file,
            #                       bytesShesGot, self.bytesSent))
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
            self.completed = 1

    def connectionLost(self, reason):
        self.connected = 0
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
        log.msg("DCC CHAT<%s> %s" % (self.remoteParty, line))
        self.client.privmsg(self.remoteParty,
                            self.client.nickname, line)


class DccChatFactory(protocol.ClientFactory):
    protocol = DccChat
    noisy = 0
    def __init__(self, client, queryData):
        self.client = client
        self.queryData = queryData

    def buildProtocol(self, addr):
        p = self.protocol(client=self.client, queryData=self.queryData)
        p.factory = self

    def clientConnectionFailed(self, unused_connector, unused_reason):
        self.client.dcc_sessions.remove(self)

    def clientConnectionLost(self, unused_connector, unused_reason):
        self.client.dcc_sessions.remove(self)


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

    I allow you to change the file's name and destination directory.
    I won't overwrite an existing file unless I've been told it's okay
    to do so. If passed the resumeOffset keyword argument I will attempt to
    resume the file from that amount of bytes.

    XXX: I need to let the client know when I am finished.
    XXX: I need to decide how to keep a progress indicator updated.
    XXX: Client needs a way to tell me "Do not finish until I say so."
    XXX: I need to make sure the client understands if the file cannot be written.
    """

    filename = 'dcc'
    fileSize = -1
    destDir = '.'
    overwrite = 0
    fromUser = None
    queryData = None

    def __init__(self, filename, fileSize=-1, queryData=None,
                 destDir='.', resumeOffset=0):
        DccFileReceiveBasic.__init__(self, resumeOffset=resumeOffset)
        self.filename = filename
        self.destDir = destDir
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


    # Protocol-level methods.

    def connectionMade(self):
        dst = path.abspath(path.join(self.destDir,self.filename))
        exists = path.exists(dst)
        if self.resume and exists:
            # I have been told I want to resume, and a file already
            # exists - Here we go
            self.file = open(dst, 'ab')
            log.msg("Attempting to resume %s - starting from %d bytes" %
                    (self.file, self.file.tell()))
        elif self.overwrite or not exists:
            self.file = open(dst, 'wb')
        else:
            raise OSError(errno.EEXIST,
                          "There's a file in the way.  "
                          "Perhaps that's why you cannot open it.",
                          dst)

    def dataReceived(self, data):
        self.file.write(data)
        DccFileReceiveBasic.dataReceived(self, data)

        # XXX: update a progress indicator here?

    def connectionLost(self, reason):
        """When the connection is lost, I close the file.
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

        if hasattr(self, 'file'):
            logmsg = "%s and written to %s.\n" % (logmsg, self.file.name)
            if hasattr(self.file, 'close'): self.file.close()

        # self.transport.log(logmsg)

    def __str__(self):
        if not self.connected:
            return "<Unconnected DccFileReceive object at %x>" % (id(self),)
        from_ = self.transport.getPeer()
        if self.fromUser:
            from_ = "%s (%s)" % (self.fromUser, from_)

        s = ("DCC transfer of '%s' from %s" % (self.filename, from_))
        return s

    def __repr__(self):
        s = ("<%s at %x: GET %s>"
             % (self.__class__, id(self), self.filename))
        return s


# CTCP constants and helper functions

X_DELIM = chr(001)

def ctcpExtract(message):
    """
    Extract CTCP data from a string.

    @return: A C{dict} containing two keys:
       - C{'extended'}: A list of CTCP (tag, data) tuples.
       - C{'normal'}: A list of strings which were not inside a CTCP delimiter.
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
del k, v

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

X_QUOTE = '\\'

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
    """
    @type messages: a list of extended messages.  An extended
    message is a (tag, data) tuple, where 'data' may be C{None}, a
    string, or a list of strings to be joined with whitespace.

    @returns: String
    """
    coded_messages = []
    for (tag, data) in messages:
        if data:
            if not isinstance(data, types.StringType):
                try:
                    # data as list-of-strings
                    data = " ".join(map(str, data))
                except TypeError:
                    # No?  Then use it's %s representation.
                    pass
            m = "%s %s" % (tag, data)
        else:
            m = str(tag)
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
RPL_ISUPPORT = '005'
RPL_BOUNCE = '010'
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
    "RPL_ISUPPORT": '005',
    "RPL_BOUNCE": '010',
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
