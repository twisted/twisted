# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Example Shoutcast client. Run with::

    python shoutcast.py localhost 8080
"""

import sys

from twisted.python import log
from twisted.internet import protocol, reactor
from twisted.protocols.shoutcast import ShoutcastClient

log.startLogging(sys.stdout)

class Test(ShoutcastClient):
    def gotMetaData(self, data):
        print "meta:", data

    def gotMP3Data(self, data):
        pass

host = sys.argv[1]
port = int(sys.argv[2])

protocol.ClientCreator(reactor, Test).connectTCP(host, port)
reactor.run()
