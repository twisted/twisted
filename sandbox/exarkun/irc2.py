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
    
    def left(self, channel):
        try:
            d = self._pendingParts[channel.lower()]
        except KeyError:
            pass
        else:
            del self._pendingParts[channel.lower()]
            d.callback(self)

    def irc_ERR_NOSUCHCHANNEL(self, prefix, params):
        print 'No such'
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
