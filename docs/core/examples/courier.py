#!/usr/bin/env python

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Example of an interface to Courier's mail filter.
"""

LOGFILE = '/tmp/filter.log'

# Setup log file
from twisted.python import log
log.startLogging(open(LOGFILE, 'a'))
import sys
sys.stderr = log.logfile

# Twisted imports
from twisted.internet import reactor, stdio
from twisted.internet.protocol import Protocol, Factory
from twisted.protocols import basic

FILTERS='/var/lib/courier/filters'
ALLFILTERS='/var/lib/courier/allfilters'
FILTERNAME='twistedfilter'

import email.parser
import email.message
import os, os.path
from syslog import syslog, openlog, LOG_MAIL

def trace_dump():
    t,v,tb = sys.exc_info()
    openlog(FILTERNAME, 0, LOG_MAIL)
    syslog('Unhandled exception: %s - %s' % (v, t))
    while tb:
        syslog('Trace: %s:%s %s' % (tb.tb_frame.f_code.co_filename,tb.tb_frame.f_code.co_name,tb.tb_lineno))
        tb = tb.tb_next
    # just to be safe
    del tb


def safe_del(file):
    try:
        if os.path.isdir(file):
            os.removedirs(file)
        else:
            os.remove(file)
    except OSError:
        pass



class DieWhenLost(Protocol):
    def connectionLost(self, reason=None):
        reactor.stop()



class MailProcessor(basic.LineReceiver):
    """
    I process a mail message.

    Override filterMessage to do any filtering you want.
    """
    messageFilename = None
    delimiter = '\n'

    def connectionMade(self):
        log.msg('Connection from %r' % self.transport)
        self.state = 'connected'
        self.metaInfo = []


    def lineReceived(self, line):
        if self.state == 'connected':
            self.messageFilename = line
            self.state = 'gotMessageFilename'
        if self.state == 'gotMessageFilename':
            if line:
                self.metaInfo.append(line)
            else:
                if not self.metaInfo:
                    self.transport.loseConnection()
                    return
                self.filterMessage()


    def filterMessage(self):
        """Override this.

        A trivial example is included.
        """
        try:
            emailParser = email.parser.Parser()
            with open(self.messageFilename) as f:
                emailParser.parse(f)
            self.sendLine('200 Ok')
        except:
            trace_dump()
            self.sendLine('435 %s processing error' % FILTERNAME)


def main():
    # Listen on the UNIX socket
    f = Factory()
    f.protocol = MailProcessor
    safe_del('%s/%s' % (ALLFILTERS, FILTERNAME))
    reactor.listenUNIX('%s/%s' % (ALLFILTERS, FILTERNAME), f, 10)

    # Once started, close fd 3 to let Courier know we're ready
    reactor.callLater(0, os.close, 3)

    # When stdin is closed, it's time to exit.
    stdio.StandardIO(DieWhenLost())

    # Go!
    reactor.run()

if __name__ == '__main__':
    main()
