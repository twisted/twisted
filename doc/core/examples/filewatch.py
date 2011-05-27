# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

from twisted.application import internet

def watch(fp):
    fp.seek(fp.tell())
    for line in fp.readlines():
        sys.stdout.write(line) 

import sys
from twisted.internet import reactor
from twisted.python import log
log.startLogging(sys.stdout)

s = internet.TimerService(0.1, watch, file(sys.argv[1]))
s.startService()
reactor.run()
s.stopService()
