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

from pyunit import unittest
from twisted.internet import default
from twisted.python.defer import Deferred
import sys

class InterfaceTestCase(unittest.TestCase):

    def testTriggerSystemEvent(self):
        l = []
        l2 = []
        d = Deferred()
        d2 = Deferred()
        def _returnDeferred(d=d):
            return d
        def _returnDeferred2(d2=d2):
            return d2
        def _appendToList(l=l):
            l.append(1)
        def _appendToList2(l2=l2):
            l2.append(1)
        ##         d.addCallback(lambda x: sys.stdout.write("firing d\n"))
        ##         d2.addCallback(lambda x: sys.stdout.write("firing d2\n"))
        r = default.SelectReactor()
        r.addSystemEventTrigger("before", "test", _appendToList)
        r.addSystemEventTrigger("during", "test", _appendToList)
        r.addSystemEventTrigger("after", "test", _appendToList)
        self.assertEquals(len(l), 0, "Nothing happened yet.")
        r.fireSystemEvent("test")
        self.assertEquals(len(l), 3, "Should have filled the list.")
        l[:]=[]
        r.addSystemEventTrigger("before", "defer", _returnDeferred)
        r.addSystemEventTrigger("before", "defer", _returnDeferred2)
        r.addSystemEventTrigger("during", "defer", _appendToList)
        r.addSystemEventTrigger("after", "defer", _appendToList)
        r.fireSystemEvent("defer")
        self.assertEquals(len(l), 0, "Event should not have fired yet.")
        d.callback(None)
        self.assertEquals(len(l), 0, "Event still should not have fired yet.")
        d2.callback(None)
        self.assertEquals(len(l), 2)
        l[:]=[]
        a = r.addSystemEventTrigger("before", "remove", _appendToList)
        b = r.addSystemEventTrigger("before", "remove", _appendToList2)
        r.removeSystemEventTrigger(b)
        r.fireSystemEvent("remove")
        self.assertEquals(len(l), 1)
        self.assertEquals(len(l2), 0)
        
