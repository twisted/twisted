# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Demonstration of sending bytes over a TCP connection using sendmsg.
"""


from socket import socketpair

from twisted.python.sendmsg import recvmsg, sendmsg


def main():
    foo, bar = socketpair()
    sent = sendmsg(foo, b"Hello, world")
    print("Sent", sent, "bytes")
    (received, ancillary, flags) = recvmsg(bar, 1024)
    print("Received", repr(received))
    print("Extra stuff, boring in this case", flags, ancillary)


if __name__ == "__main__":
    main()
