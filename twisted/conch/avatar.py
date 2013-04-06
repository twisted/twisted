# -*- test-case-name: twisted.conch.test.test_conch -*-
from interfaces import IConchUser
from error import ConchError
from ssh.connection import OPEN_UNKNOWN_CHANNEL_TYPE
from twisted.python import log
from zope import interface

class ConchUser:
    interface.implements(IConchUser)

    def __init__(self):
        self.channelLookup = {}
        self.subsystemLookup = {}

    def lookupChannel(self, channelType, windowSize, maxPacket, data):
        klass = self.channelLookup.get(channelType, None)
        if not klass:
            raise ConchError(OPEN_UNKNOWN_CHANNEL_TYPE, "unknown channel")
        else:
            return klass(remoteWindow=windowSize,
                         remoteMaxPacket=maxPacket,
                         data=data, avatar=self)

    def lookupSubsystem(self, subsystem, data):
        log.msg(repr(self.subsystemLookup))
        klass = self.subsystemLookup.get(subsystem, None)
        if not klass:
            return False
        return klass(data, avatar=self)

    def gotGlobalRequest(self, requestType, data):
        # XXX should this use method dispatch?
        requestType = requestType.replace('-','_')
        f = getattr(self, "global_%s" % requestType, None)
        if not f:
            return 0
        return f(data)
