# -*- coding: Latin-1 -*-

from twisted.protocols import irc
from twisted.internet import defer
from twisted.python.log import msg as logmsg

class IRCError(Exception):
    pass

class NoSuchChannel(IRCError):
    pass

class NoSuchNickname(IRCError):
    pass

class NicknameError(IRCError):
    pass

class ErroneousNickname(NicknameError):
    pass

class NicknameMissing(NicknameError):
    pass

class NicknameCollision(NicknameError):
    """A nickname is already in use on some server on the network
    """

class NicknameInUse(NicknameError):
    """A nickname is already in use on this server
    """

def log(msg, protocol="irc", channel="info", level="protocol"):
    logmsg(msg, protocol=protocol, channel=channel, level=level)

class AdvancedClient(irc.IRCClient):
    _pendingQuit = None
    
    def __init__(self):
        self._pending = []
    
    def _makeCommand(self, name, additional=None, unknownHandler=None):
        self._pending.append((name, defer.Deferred(), additional, unknownHandler))
        return self._pending[-1][1]

    def _getHandler(self):
        if not self._pending:
            raise ValueError("No current command")
        f = self._pending[0][3]
        if f is None:
            raise ValueError("Current unknown-handler is None")
        return f

    def _getAdd(self, command=None, possible=()):
        if not self._pending:
            raise ValueError("No current command")
        if command is not None:
            if self._pending[0][0] == command:
                return self._pending[0][2]
            else:
                raise ValueError("Current command not %r" % (command,))
        else:
            if self._pending[0][0] in possible:
                return self._pending[0][2]
            else:
                raise ValueError("Current command not in %r" % (command,))

    def _getDeferred(self, command=None, possible=()):
        # We can prevent offset errors induced by the receipt of unexpected
        # messages in addition to those we do expect, but I see no way to
        # prevent those induced by the omission of expected messages or the
        # receipt of expected messages in an unexpected order (that is, any
        # order other than that in which we send the associated commands). 
        # Therefore, if a server fails to respond in the manner which we
        # expected, client code using this class will likely become hung and
        # remain so forever.
        if not self._pending:
            raise ValueError("No commands pending")
        if command is not None:
            if self._pending[0][0] == command:
                return self._pending.pop(0)[1]
            else:
                raise ValueError("Next command is not %r" % (command,))
        else:
            if self._pending[0][0] in possible:
                return self._pending.pop(0)[1]
            else:
                raise ValueError("Next command not in %r" % (command,))

    def _callback(self, command=None, possible=(), args=None, additional=False):
        if additional:
            try:
                args = self._getAdd(command)
            except ValueError:
                log("Unexpected callback for %r" % (command,))
                return
        try:
            d = self._getDeferred(command=command, possible=possible)
        except ValueError, e:
            log("Unexpected callback: %s" % (e,))
        else:
            d.callback(args)

    def _errback(self, command=None, possible=(), failure=None):
        try:
            d = self._getDeferred(command=command, possible=possible)
        except ValueError, e:
            log("Unexpected errback: %s" % (e,))
        else:
            d.errback(failure)

    def connectionLost(self, reason):
        self._callback("QUIT", args=self)

    def irc_unknown(self, prefix, command, params):
        try:
            f = self._getHandler()
        except ValueError:
            irc.IRCClient.irc_unknown(self, prefix, command, params)
        else:
            f(prefix, command, params)

    def quit(self, message=''):
        """Quit the network
        
        @rtype: C{Deferred}
        @return: A deferred whose callback is invoked when the quit succeeds
        (the connection is lost).
        """
        irc.IRCClient.quit(self, message)
        return self._makeCommand("QUIT")
    
    def join(self, channel, key=None):
        """Join a channel
        
        @rtype: C{Deferred}
        @return: A deferred whose callback is invoked when the join succeeds or
        whose errback is invoked if it fails.
        """
        irc.IRCClient.join(self, channel, key)
        return self._makeCommand("JOIN")
    
    def joined(self, channel):
        self._callback("JOIN", args=self)

    def leave(self, channel, reason=None):
        """Leave a channel
        
        @return: A deferred whose callback is invoked when the part succeeds or
        whose errback is invoked if it fails.
        """
        irc.IRCClient.leave(self, channel, reason)
        return self._makeCommand("PART")
    part = leave
    
    def left(self, channel):
        self._callback("PART", args=self)

    def irc_ERR_NOSUCHCHANNEL(self, prefix, params):
        channel = params[1]
        try:
            # I can do better than this.  Give me time.
            d = self._getDeferred(possible=("JOIN", "PART", "TOPIC"))
        except ValueError:
            log("Unexpected no-such-channel")
        else:
            d.errback(NoSuchChannel(channel))

    def names(self, *channels):
        """List names of users visible to this user.
        
        @type channels: C{str}
        @param channels: The channels for which to request names.
        
        @rtype: C{Deferred} of C{dict} mapping C{str} to C{list} of C{str}
        @return: A mapping of channel names to lists of users in those
        channels.
        """
        self.sendLine("NAMES " + " ".join(channels))
        return self._makeCommand("NAMES", {})
    
    def irc_RPL_NAMREPLY(self, prefix, params):
        channel = params[2]
        names = params[3].split()
        self._getAdd("NAMES").setdefault(channel, []).extend(names)
    
    def irc_RPL_ENDOFNAMES(self, prefix, params):
        self._callback("NAMES", additional=True)

    def who(self, name, op=False):
        """List names of users who match a particular pattern.
        
        @type name: C{str}
        @param name: The pattern against which to match.
        
        @type op: C{bool}
        @param op: If true, only request operators who match the given
        pattern.
        
        @rtype: C{Deferred} of C{list} of C{tuples}
        @return: A list of 8-tuples consisting of
        
            channel, user, host, server, nick, flags, hopcount, real name
        
        all of which are strings, except hopcount, which is an integer.
        """
        if op:
            self.sendLine("WHO " + name)
        else:
            self.sendLine("WHO " + name + " o")
        return self._makeCommand("WHO", [])
    
    def irc_RPL_WHOREPLY(self, prefix, params):
        params = params[2:]
        params[-1:] = params[-1].split(None, 1)
        params[-2] = int(params[-2])
        self._getAdd("WHO").append(tuple(params))
    
    def irc_RPL_ENDOFWHO(self, prefix, params):
        self._callback("WHO", additional=True)

    def whois(self, user):
        """Retrieve information about the specified user.
        
        @type user: C{str}
        @param user: The user about whom to retrieve information.
        
        @rtype: C{Deferred} of C{dict} mapping information tags to
        received information.  The items of this dict are as follows:
        
            'user':      (ident, hostmask, real name)
            'server':    (server, server info)
            'operator':  True
            'idle':      idle time, in seconds, as an integer
            'channels':  list of strings indicating the channels to which
                            the user belongs
        
        Other keys may exist if the server responds with non-standard
        information.
        """
        self.sendLine("WHOIS " + user)
        return self._makeCommand("WHOIS", {}, unknownHandler=self._whoisHandler)

    def _whoisHandler(self, prefix, command, params):
        try:
            command = int(command)
        except ValueError:
            pass
        self._getAdd("WHOIS").setdefault(command, []).append(params)
    
    def irc_RPL_WHOISUSER(self, prefix, params):
        self._getAdd("WHOIS")['user'] = params[2], params[3], params[5]
    
    def irc_RPL_WHOISSERVER(self, prefix, params):
        self._getAdd("WHOIS")['server'] = params[2], params[3]
    
    def irc_RPL_WHOISOPERATOR(self, prefix, params):
        self._getAdd("WHOIS")['operator'] = True
    
    def irc_RPL_WHOISIDLE(self, prefix, params):
        self._getAdd("WHOIS")['idle'] = int(params[2])
    
    def irc_RPL_WHOISCHANNELS(self, prefix, params):
        self._getAdd("WHOIS").setdefault('channels', []).append(params[1])
    
    def irc_RPL_ENDOFWHOIS(self, prefix, params):
        self._callback("WHOIS", additional=True)

    def irc_ERR_NOSUCHNICK(self, prefix, params):
        self._errback(possible=("WHOIS",), failure=NoSuchNickname())

    def topic(self, channel, topic=None):
        """Retrieve the topic for the given channel.
        
        @type channel C{str}
        @param channel: The channel for which to retrieve the topic.
        
        @type topic: C{str}
        @param topic: The topic to set, or None to just retrieve the
        current topic.
        
        @rtype: C{Deferred} of C{str} or C{None}
        @return: A Deferred of the topic, or of None if no topic is set.
        """
        irc.IRCClient.topic(self, channel, topic)
        return self._makeCommand("TOPIC")
    
    def irc_RPL_TOPIC(self, prefix, params):
        channel, topic = params[1:]
        self._callback("TOPIC", args=topic)
    
    def irc_RPL_NOTOPIC(self, prefix, params):
        channel = params[1]
        self._callback("TOPIC", args=None)

    def nick(self, newnick):
        """Change this user's nickname.
        
        @type newnick: C{str}

        @return: C{Deferred} that fires with the nick when it has been
        changed, or whose errback is called if the nick name cannot be
        changed.

        @raise NicknameError: Raised asynchronously if the server reports
        an error in changing the nickname.  Any one of the four
        NicknameError subclasses may be raised: NicknameMissing,
        NicknameInUse, ErroneousNickname, or NicknameCollision.
        """
        self.sendLine("NICK " + newnick)
        return self._makeCommand("NICK")

    def nickChanged(self, nick):
        irc.IRCClient.nickChanged(self, nick)
        self._callback("NICK", args=nick)

    def irc_ERR_NONICKNAMEGIVEN(self, prefix, params):
        self._errback("NICK", failure=NicknameMissing())
    
    def irc_ERR_NICKNAMEINUSE(self, prefix, params):
        self._errback("NICK", failure=NicknameInUse())
    
    def irc_ERR_ERRONEUSNICKNAME(self, prefix, params):
        self._errback("NICK", failure=ErroneousNickname())
    
    def irc_ERR_NICKCOLLISION(self, prefix, params):
        self._errback("NICK", failure=NicknameCollision())
