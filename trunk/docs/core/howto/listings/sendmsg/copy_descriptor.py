# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Demonstration of copying a file descriptor over an AF_UNIX connection using
sendmsg.
"""

from __future__ import print_function

from os import pipe, read, write
from socket import SOL_SOCKET, socketpair
from struct import unpack, pack

from twisted.python.sendmsg import SCM_RIGHTS, sendmsg, recvmsg

def main():
    foo, bar = socketpair()
    reader, writer = pipe()

    # Send a copy of the descriptor.  Notice that there must be at least one
    # byte of normal data passed in.
    sent = sendmsg(
        foo, b"\x00", [(SOL_SOCKET, SCM_RIGHTS, pack("i", reader))])

    # Receive the copy, including that one byte of normal data.
    data, ancillary, flags = recvmsg(bar, 1024)
    duplicate = unpack("i", ancillary[0][2])[0]

    # Demonstrate that the copy works just like the original
    write(writer, b"Hello, world")
    print("Read from original (%d): %r" % (reader, read(reader, 6)))
    print("Read from duplicate (%d): %r" % (duplicate, read(duplicate, 6)))

if __name__ == '__main__':
    main()
