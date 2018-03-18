# -*- test-case-name: twisted.python.test.test_sendmsg -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

import sys, os
from struct import unpack

from twisted.python.sendmsg import recv1msg

def recvfd(socketfd):
    """
    Receive a file descriptor from a L{send1msg} message on the given C{AF_UNIX}
    socket.

    @param socketfd: An C{AF_UNIX} socket, attached to another process waiting
        to send sockets via the ancillary data mechanism in L{send1msg}.

    @param fd: C{int}

    @return: a 2-tuple of (new file descriptor, description).

    @rtype: 2-tuple of (C{int}, C{str})
    """
    data, flags, ancillary = recv1msg(socketfd)
    [(cmsg_level, cmsg_type, packedFD)] = ancillary
    # cmsg_level and cmsg_type really need to be SOL_SOCKET / SCM_RIGHTS, but
    # since those are the *only* standard values, there's not much point in
    # checking.
    [unpackedFD] = unpack("i", packedFD)
    return (unpackedFD, data)


if __name__ == '__main__':
    fd, description = recvfd(int(sys.argv[1]))
    os.write(fd, "Test fixture data: %s.\n" % (description,))
    os.close(fd)
