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

from twisted.cred import portal
from twisted.python import components, log
from twisted.conch.ssh.connection import OPEN_UNKNOWN_CHANNEL_TYPE

from twisted.conch.ssh import session, forwarding, filetransfer

class UnixSSHRealm:
    __implements__ = portal.IRealm

    def requestAvatar(self, username, mind, *interfaces):
        user = UnixConchUser(username)
        return interfaces[0], user, user.logout


class IConchUser(components.Interface):
    """A user who has been authenticated to Cred through Conch.  This is 
    the interface between the SSH connection and the user.

    @ivar conn: The SSHConnection object for this user.
    """

    def lookupChannel(self, channelType, windowSize, maxPacket, data):
        """
        The other side requested a channel of some sort.
        channelType is the type of channel being requested,
        windowSize is the initial size of the remote window,
        maxPacket is the largest packet we should send,
        data is any other packet data (often nothing).

        We return a subclass of SSHChannel.  If an appropriate
        channel can not be found, an exception will be raised.
        If a ConchError is raised, the .value will be the message,
        and the .data will be the error code.

        @type channelType:  C{str}
        @type windowSize:   C{int}
        @type maxPacket:    C{int}
        @type data:         C{str}
        @rtype:             subclass of C{SSHChannel}/C{tuple}
        """

    def lookupSubsystem(self, subsystem, data):
        """
        The other side requested a subsystem.
        subsystem is the name of the subsystem being requested.
        data is any other packet data (often nothing).
        
        We return
        """
        pass

    def gotGlobalRequest(self, requestType, data):
        pass


"""
        By default, this dispatches to a method 'channel_channelType' with any
        non-alphanumerics in the channelType replace with _'s.  If it cannot 
        find a suitable method, it returns an OPEN_UNKNOWN_CHANNEL_TYPE error. 
        The method is called with arguments of windowSize, maxPacket, data.
"""

class ConchUser:
    __implements__ = IConchUser

    def __init__(self):
        self.channelLookup = {}
        self.subsystemLookup = {}

    def lookupChannel(self, channelType, windowSize, maxPacket, data):
        klass = self.channelLookup.get(channelType, None)
        if not klass:
            return ConchError("unknown channel type", OPEN_UNKNOWN_CHANNEL_TYPE)
        else:
            return klass(remoteWindow = windowSize, 
                         remoteMaxPacket = maxPacket, 
                         data=data, avatar=self)

    def lookupSubsystem(self, subsystem, data):
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


class UnixConchUser(ConchUser):
    __implements__ = IConchUser

    def __init__(self, username):
        ConchUser.__init__(self)
        self.username = username
        import pwd
        self.pwdData = pwd.getpwnam(self.username)
        self.listeners = {}  # dict mapping (interface, port) -> listener
        self.channelLookup.update(
                {"session": session.SSHSession,
                 "direct-tcpip": forwarding.openConnectForwardingClient})

        self.subsystemLookup.update(
                {"sftp": filetransfer.FileTransferServer})

    def getUserGroupId(self):
        return self.pwdData[2:4]

    def getHomeDir(self):
        return self.pwdData[5]

    def getShell(self):
        return self.pwdData[6]

    def global_tcpip_forward(self, data):
        hostToBind, portToBind = forwarding.unpackGlobal_tcpip_forward(data)
        from twisted.internet import reactor
        try: listener = self._runAsUser(
                            reactor.listenTCP, portToBind, 
                            forwarding.SSHListenForwardingFactory(self.conn,
                                (hostToBind, portToBind),
                                forwarding.SSHListenServerForwardingChannel), 
                            interface = hostToBind)
        except:
            return 0
        else:
            self.listeners[(hostToBind, portToBind)] = listener
            if portToBind == 0:
                portToBind = listener.getHost()[2] # the port
                return 1, struct.pack('>L', portToBind)
            else:
                return 1

    def global_cancel_tcpip_forward(self, data):
        hostToBind, portToBind = forwarding.unpackGlobal_tcpip_forward(data)
        listener = self.listeners.get((hostToBind, portToBind), None)
        if not listener:
            return 0
        del self.listeners[(hostToBind, portToBind)]
        self._runAsUser(listener.stopListening)
        return 1

    def logout(self):
        # remove all listeners
        for listener in self.listeners.itervalues():
            self._runAsUser(listener.stopListening)
        log.msg('avatar %s logging out (%i)' % (self.username, len(self.listeners)))

    def _runAsUser(self, f, *args, **kw):
        import os
        euid = os.geteuid()
        egid = os.getegid()
        uid, gid = self.getUserGroupId()
        os.setegid(0)
        os.seteuid(0)
        os.setegid(gid)
        os.seteuid(uid)
        try:
            if not hasattr(f,'__iter__'):
                f = [(f, args, kw)]
            for i in f:
                func = i[0]
                args = len(i)>1 and i[1] or ()
                kw = len(i)>2 and i[2] or {}
                r = func(*args, **kw)
        finally:
            os.setegid(0)
            os.seteuid(0)
            os.setegid(egid)
            os.seteuid(euid)
        return r


components.registerAdapter(filetransfer.SFTPServerForUnixConchUser, UnixConchUser, filetransfer.ISFTPServer)
components.registerAdapter(session.SSHSessionForUnixConchUser, UnixConchUser, session.ISession)
