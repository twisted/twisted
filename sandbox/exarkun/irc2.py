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
    
    def connectionLost(self, reason):
        if self._pendingQuit:
            d = self._pendingQuit
            self._pendingQuit = None
            d.callback(self)

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
        
        @rtype: C{dict} mapping C{str} to C{list} of C{str}
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
