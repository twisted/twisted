
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

class AbstractPerson:
    def __init__(self,name,baseClient,chatui):
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

    def startLogOn(self, chatui):
        raise NotImplementedError()

    def logOn(self, chatui):
        if (not self._isConnecting) and (not self._isOnline):
            self._isConnecting = 1
            self.startLogOn(chatui)
        else:
            print 'already connecting'


