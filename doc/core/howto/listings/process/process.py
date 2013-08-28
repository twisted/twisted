#!/usr/bin/env python

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

import re

from twisted.internet import reactor, protocol, error


class MyPP(protocol.ProcessProtocol):
    def __init__(self, verses):
        self.verses = verses
        self.data = ""

    def connectionMade(self):
        print "connectionMade!"
        for i in range(self.verses):
            self.transport.write("Aleph-null bottles of beer on the wall,\n" +
                                 "Aleph-null bottles of beer,\n" +
                                 "Take one down and pass it around,\n" +
                                 "Aleph-null bottles of beer on the wall.\n")
        self.transport.closeStdin() # tell them we're done

    def outReceived(self, data):
        print "outReceived! with %d bytes!" % len(data)
        self.data = self.data + data

    def errReceived(self, data):
        print "errReceived! with %d bytes!" % len(data)

    def inConnectionLost(self):
        print "inConnectionLost! stdin is closed! (we probably did it)"

    def outConnectionLost(self):
        print "outConnectionLost! The child closed their stdout!"
        # now is the time to examine what they wrote
        #print "I saw them write:", self.data
        (dummy, lines, words, chars, file) = re.split(r'\s+', self.data)
        print "I saw %s lines" % lines

    def errConnectionLost(self):
        print "errConnectionLost! The child closed their stderr."

    def _reportEnd(self, which, reason):
        if reason.check(error.ProcessTerminated, error.ProcessDone):
            exc = reason.value
            print "%s, status %d" % (which, exc.status)
            print "\texit code %s; termination signal %s" % (exc.exitCode, exc.signal)
        else:
            print which, reason.getErrorMessage()

    def processExited(self, reason):
        self._reportEnd("processExited", reason)

    def processEnded(self, reason):
        self._reportEnd("processEnded", reason)
        print "quitting"
        reactor.stop()

pp = MyPP(10)
reactor.spawnProcess(pp, "wc", ["wc"], {})
reactor.run()
