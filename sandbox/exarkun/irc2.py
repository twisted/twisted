# -*- coding: Latin-1 -*-

from twisted.protocols import irc
from twisted.internet import defer

class IRCError(Exception):
    pass

class ActionInProgress(IRCError):
    pass

class NoSuchChannel(IRCError):
    pass

class AdvancedClient(irc.IRCClient):
    _pendingQuit = None
    
    def __init__(self):
        self._pendingJoins = {}
        self._pendingParts = {}
        self._pendingNames = []
        self._pendingWho = []
        self._pendingWhois = []
        self._unknownHandlers = []
    
    def connectionLost(self, reason):
        if self._pendingQuit:
            d = self._pendingQuit
            self._pendingQuit = None
            d.callback(self)

    def irc_unknown(self, prefix, command, params):
        if self._unknownHandlers:
            self._unknownHandlers[0](prefix, command, params)
        else:
            irc.IRCClient.irc_unknown(self, prefix, command, params)

    def quit(self, message=''):
        """Quit the network
        
        @rtype: C{Deferred}
        @return: A deferred whose callback is invoked when the quit succeeds
        (the connection is lost).
        """
        if self._pendingQuit is not None:
            raise ActionInProgress()
        else:
            d = self._pendingQuit = defer.Deferred()
            irc.IRCClient.quit(self, message)
            return d
    
    def join(self, channel, key=None):
        """Join a channel
        
        @rtype: C{Deferred}
        @return: A deferred whose callback is invoked when the join succeeds or
        whose errback is invoked if it fails.
        """
        if channel.lower() in self._pendingJoins:
            raise ActionInProgress()
        else:
            d = self._pendingJoins[channel.lower()] = defer.Deferred()
            irc.IRCClient.join(self, channel, key)
            return d
    
    def joined(self, channel):
        try:
            d = self._pendingJoins[channel.lower()]
        except KeyError:
            pass
        else:
            del self._pendingJoins[channel.lower()]
            d.callback(self)

    def leave(self, channel, reason=None):
        """Leave a channel
        
        @return: A deferred whose callback is invoked when the part succeeds or
        whose errback is invoked if it fails.
        """
        if channel.lower() in self._pendingParts:
            raise ActionInProgress()
        else:
            d = self._pendingParts[channel.lower()] = defer.Deferred()
            irc.IRCClient.leave(self, channel, reason)
            return d
    part = leave
    
    def left(self, channel):
        try:
            d = self._pendingParts[channel.lower()]
        except KeyError:
            pass
        else:
            del self._pendingParts[channel.lower()]
            d.callback(self)

    def irc_ERR_NOSUCHCHANNEL(self, prefix, params):
        # This whole scheme is probably wrong.
        channel = params[1]
        try:
            d = self._pendingJoins[channel.lower()]
        except KeyError:
            pass
        else:
            del self._pendingJoins[channel.lower()]
            d.errback(NoSuchChannel())
            return
        
        try:
            d = self._pendingParts[channel.lower()]
        except KeyError:
            pass
        else:
            del self._pendingParts[channel.lower()]
            d.errback(NoSuchChannel())
            return

    def names(self, *channels):
        """List names of users visible to this user.
        
        @type channels: C{str}
        @param channels: The channels for which to request names.
        
        @rtype: C{Deferred} of C{dict} mapping C{str} to C{list} of C{str}
        @return: A mapping of channel names to lists of users in those
        channels.
        """
        d = defer.Deferred()
        self._pendingNames.append(({}, d))
        self.sendLine("NAMES " + " ".join(channels))
        return d
    
    def irc_RPL_NAMREPLY(self, prefix, params):
        channel = params[2]
        names = params[3].split()
        self._pendingNames[0][0].setdefault(channel, []).extend(names)
    
    def irc_RPL_ENDOFNAMES(self, prefix, params):
        names, d = self._pendingNames.pop(0)
        d.callback(names)

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
        d = defer.Deferred()
        self._pendingWho.append(([], d))
        if op:
            self.sendLine("WHO " + name)
        else:
            self.sendLine("WHO " + name + " o")
        return d
    
    def irc_RPL_WHOREPLY(self, prefix, params):
        params = params[2:]
        params[-1:] = params[-1].split(None, 1)
        params[-2] = int(params[-2])
        self._pendingWho[0][0].append(tuple(params))
    
    def irc_RPL_ENDOFWHO(self, prefix, params):
        who, d = self._pendingWho.pop(0)
        d.callback(who)

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
        d = defer.Deferred()
        self._pendingWhois.append(({}, d))
        self._unknownHandlers.append(self._whoisHandler)
        self.sendLine("WHOIS " + user)
        return d

    def _whoisHandler(self, prefix, command, params):
        try:
            command = int(command)
        except ValueError:
            pass
        self._pendingWhois[0][0].setdefault(command, []).append(params)
    
    def irc_RPL_WHOISUSER(self, prefix, params):
        self._pendingWhois[0][0]['user'] = params[2], params[3], params[5]
    
    def irc_RPL_WHOISSERVER(self, prefix, params):
        self._pendingWhois[0][0]['server'] = params[2], params[3]
    
    def irc_RPL_WHOISOPERATOR(self, prefix, params):
        self._pendingWhois[0][0]['operator'] = True
    
    def irc_RPL_WHOISIDLE(self, prefix, params):
        self._pendingWhois[0][0]['idle'] = int(params[2])
    
    def irc_RPL_WHOISCHANNELS(self, prefix, params):
        self._pendingWhois[0][0].setdefault('channels', []).append(params[1])
    
    def irc_RPL_ENDOFWHOIS(self, prefix, params):
        whois, d = self._pendingWhois.pop(0)
        del self._unknownHandlers[0]
        d.callback(whois)

    def irc_ERR_NOSUCHNICK(self, prefix, params):
        # See irc_ERR_NOSUCHCHANNEL
        whois, d = self._pendingWhois.pop(0)
        del self._unknownHandlers[0]
        d.errback(NoSuchChannel())
