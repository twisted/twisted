# -*- coding: Latin-1 -*-

"""
Protocol for passing files between processes.
"""

import sys
import struct

from eunuchs.sendmsg import sendmsg

from twisted.internet import protocol
from twisted.internet import unix
from twisted.python import log

SCM_RIGHTS = 0x01

class Port(unix.Port):
    def sendmsg(self, data, flags=0, ancillary=()):
        assert sendmsg(fd=self.fileno(), data=data, flags=flags, ancillary=ancillary) == len(data)

    def sendFileDescriptor(self, fileno):
        s = struct.pack('!I', fileno)
        fmt = '!III'
        cmsg = struct.pack(fmt, struct.calcsize(fmt), socket.SOL_SOCKET, SCM_RIGHTS) + s

class FileDescriptorSendingProtocol(protocol.Protocol):
    """
    Protocol for sending and receiving file descriptors.
    
    Must be used with L{Port} as the transport.
    """

    typeToMethod = {
        SCM_RIGHTS: 'SCM_RIGHTS',
    }

    def messageReceived(self, msg):
        return getattr(self, 'msg_' + self.typeToMethod.get(msg.type, 'UNKNOWN'))(msg)

    def msg_SCM_RIGHTS(self, msg):
        print 'SCM_RIGHTS', repr(msg)

    def msg_UNKNOWN(self, msg):
        print 'UNKNOWN', repr(msg)

def main():
    log.startLogging(sys.stdout)

    from twisted.internet import reactor
    f = protocol.ServerFactory()
    f.protocol = FileDescriptorSendingProtocol
    p = reactor.listenWith(Port, 'fd_control', f)
    reactor.run()

if __name__ == '__main__':
    main()
