# Twisted, the Framework of Your Internet
# Copyright (C) 2001-2002 Matthew W. Lefkowitz
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
#

# Abstract representation of chat "model" classes

from locals import ONLINE, OFFLINE

from twisted.internet.protocol import Protocol

from twisted.python.reflect import prefixedMethods

class AbstractGroup:
    def __init__(self,name,baseClient,chatui):
        self.name = name
        self.client = baseClient
        self.chat = chatui

    def getGroupCommands(self):
        """finds group commands

        these commands are methods on me that start with imgroup_; they are
        called with no arguments
        """
        return prefixedMethods(self, "imgroup_")

    def getTargetCommands(self, target):
        """finds group commands

        these commands are methods on me that start with imgroup_; they are
        called with a user present within this room as an argument

        you may want to override this in your group in order to filter for
        appropriate commands on the given user
        """
        return prefixedMethods(self, "imtarget_")

    def __repr__(self):
        return '<%s %r>' % (self.__class__, self.name)

    def __str__(self):
        return '%s@%s' % (self.name, self.client.account.accountName)

class AbstractPerson:
    def __init__(self, name, baseClient, chatui):
        self.name = name
        self.client = baseClient
        self.status = OFFLINE
        self.chat = chatui

    def getPersonCommands(self):
        """finds person commands

        these commands are methods on me that start with imperson_; they are
        called with no arguments
        """
        return prefixedMethods(self, "imperson_")

    def getIdleTime(self):
        """
        Returns a string.
        """
        return '--'

    def imperson_converse(self):
        self.chat.getConversation(self)

    def __repr__(self):
        return '<%s %r/%s>' % (self.__class__, self.name, self.status)

    def __str__(self):
        return '%s@%s' % (self.name, self.client.account.accountName)

class AbstractClientMixin:
    """Designed to be mixed in to a Protocol implementing class.

    Inherit from me first.
    """
    def __init__(self, account, chatui):
        for base in self.__class__.__bases__:
            if issubclass(base, Protocol):
                self.__class__._protoBase = base
                break
        else:
            pass
        self.account = account
        self.chat = chatui

    def connectionMade(self):
        self.account._isOnline = 1
        self._protoBase.connectionMade(self)

    def connectionLost(self, other):
        self.account._isConnecting = 0
        self.account._isOnline = 0
        self.unregisterAsAccountClient()
        self._protoBase.connectionLost(self, other)

    def registerAsAccountClient(self):
        """Register me with the chat UI as `signed on'.
        """
        self.chat.registerAccountClient(self)

    def unregisterAsAccountClient(self):
        """Tell the chat UI that I have `signed off'.
        """
        self.chat.unregisterAccountClient(self)


class AbstractAccount:
    """

    @type _isConnecting: boolean
    @ivar _isConnecting: Whether I am in the process of establishing a
    connection to the server.
    @type _isOnline: boolean
    @ivar _isOnline: Whether I am currently on-line with the server.
    """
    _isOnline = 0
    _isConnecting = 0

    def __setstate__(self, d):
        if d.has_key('isOnline'):
            del d['isOnline']
        if d.has_key('_isOnline'):
            del d['_isOnline']
        if d.has_key('_isConnecting'):
            del d['_isConnecting']
        self.__dict__ = d
        self.port = int(self.port)

    def __getstate__(self):
        self._isOnline = 0
        self._isConnecting = 0
        return self.__dict__

    def isOnline(self):
        return self._isOnline

    def logOn(self, chatui):
        """Log on to this account.

        Takes care to not start a connection if a connection is
        already in progress.  You will need to implement
        L{_startLogOn} for this to work, and it would be a good idea
        to override L{_loginFailed} too.
        """
        if (not self._isConnecting) and (not self._isOnline):
            self._isConnecting = 1
            self._startLogOn(chatui).addErrback(self._loginFailed)
        else:
            print 'already connecting'

    def _startLogOn(self, chatui):
        """Start the sign on process.

        Factored out of L{logOn}.

        @returns: None
        @returntype: Deferred
        """
        raise NotImplementedError()

    def _loginFailed(self, reason):
        """Errorback for L{logOn}.

        @type reason: Failure
        """
        self._isConnecting = 0
        self._isOnline = 0 # just in case
