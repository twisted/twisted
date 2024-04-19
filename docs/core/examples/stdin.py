# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


"""
An example of reading a line at a time from standard input
without blocking the reactor.
"""

from os import linesep

from twisted.internet import stdio
from twisted.protocols import basic


class Echo(basic.LineReceiver):
    delimiter = linesep.encode("ascii")

    def connectionMade(self):
        self.transport.write(b">>> ")

    def lineReceived(self, line):
        self.sendLine(b"Echo: " + line)
        self.transport.write(b">>> ")


def main():
    stdio.StandardIO(Echo())
    from twisted.internet import reactor

    reactor.run()


if __name__ == "__main__":
    main()
