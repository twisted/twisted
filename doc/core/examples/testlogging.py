# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

"""Test logging.

Message should only be printed second time around.
"""

from twisted.python import log
from twisted.internet import reactor

import sys, warnings

def test(i):
    print "printed", i
    log.msg("message %s" % i)
    warnings.warn("warning %s" % i)
    try:
        raise RuntimeError, "error %s" % i
    except:
        log.err()

def startlog():
    log.startLogging(sys.stdout)

def end():
    reactor.stop()

# pre-reactor run
test(1)

# after reactor run
reactor.callLater(0.1, test, 2)
reactor.callLater(0.2, startlog)

# after startLogging
reactor.callLater(0.3, test, 3)
reactor.callLater(0.4, end)

reactor.run()
