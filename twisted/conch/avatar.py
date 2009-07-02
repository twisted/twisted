# -*- test-case-name: twisted.conch.test.test_conch -*-
# Copyright (c) 2008-2009 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
This module contains a default implementation of the IConchUser avatar
interface.

For more information, see the IConchUser interface.
"""

from zope import interface
from twisted.conch.interfaces import IConchUser
from twisted.conch.error import ConchError
from twisted.conch.ssh.connection import OPEN_UNKNOWN_CHANNEL_TYPE

class ConchUser:
    interface.implements(IConchUser)

    def __init__(self):
        self.channelLookup = {}
        self.subsystemLookup = {}

    def lookupChannel(self, channelType, windowSize, maxPacket, data):
        """
        The client has requested a channel of channelType.  We try to look it
        up in our channelLookup dictionary and return an instantiated channel.
        If the channel isn't found, raise an UNKNOWN_CHANNEL_TYPE error.

        @param channelType: the type of channel the client requested
        @type channelType: C{str}
        @param windowSize: the initial size of the client window
        @type windowSize: C{int}
        @param maxPacket: the maximum packet the client will accept
        @type maxPacket: C{int}
        @param data: any additional data to be passed to the channel
        @type data: C{str}

        @returns: an instance of C{twisted.conch.ssh.channel.SSHChannel}
        @rtype: C{twisted.conch.ssh.channel.SSHChannel}
        @raises: C{ConchError} if the channel wasn't found
        """
        klass = self.channelLookup.get(channelType, None)
        if not klass:
            raise ConchError(OPEN_UNKNOWN_CHANNEL_TYPE, "unknown channel")
        else:
            return klass(remoteWindow=windowSize,
                         remoteMaxPacket=maxPacket,
                         data=data, avatar=self)

    def lookupSubsystem(self, subsystem, data):
        """
        This is deprecated in favor of ISession.lookupSubsystem.  However,
        because there is already a warning in SSHSession.request_subsystem,
        we do not warn again here.

        For documentation about the arguments, see l{ISession.lookupSubsystem}
        """
        klass = self.subsystemLookup.get(subsystem, None)
        if not klass:
            return False
        return klass(data, avatar=self)

    def gotGlobalRequest(self, requestType, data):
        """
        The client maded a global request.

        @param requestType: the type of the global request
        @type requestType: C{str}
        @param data: any additional data
        @type data: C{str}

        @returns: a boolean indicating whether the request failed or succeeded
        @rtype: C{bool}
        """
        # XXX should this use method dispatch?
        requestType = requestType.replace('-','_')
        f = getattr(self, "global_%s" % requestType, None)
        if not f:
            return 0
        return f(data)
