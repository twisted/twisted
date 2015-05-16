# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Demonstration of sending bytes over a TCP connection using sendmsg.
"""

from socket import socketpair

from twisted.python.sendmsg import send1msg, recv1msg

def main():
    foo, bar = socketpair()
    sent = send1msg(foo.fileno(), "Hello, world")
    print "Sent", sent, "bytes"
    (received, flags, ancillary) = recv1msg(bar.fileno(), 1024)
    print "Received", repr(received)
    print "Extra stuff, boring in this case", flags, ancillary

if __name__ == '__main__':
    main()
