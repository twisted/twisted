#
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

import sys, os
from twisted.trial import unittest

from twisted.xish.domish import Element
from twisted.xish.utility import EventDispatcher

class CallbackTracker:
    def __init__(self):
        self.called = 0
        self.object = None

    def call(self, object):
        self.called = self.called + 1
        self.object = object

class CallbackTracker2 (CallbackTracker):
    def __init__(self, dispatcher):
        CallbackTracker.__init__(self)
        self.dispatcher = dispatcher

    def call2(self, _):
        self.dispatcher.addObserver("/presence", self.call)

class EventDispatcherTest(unittest.TestCase):
    def testStuff(self):
        d = EventDispatcher()
        cb1 = CallbackTracker()
        cb2 = CallbackTracker()
        cb3 = CallbackTracker()

        d.addObserver("/message/body", cb1.call)
        d.addObserver("/message", cb1.call)
        d.addObserver("/presence", cb2.call)
        d.addObserver("//event/testevent", cb3.call)

        msg = Element(("ns", "message"))
        msg.addElement("body")

        pres = Element(("ns", "presence"))
        pres.addElement("presence")

        d.dispatch(msg)
        self.assertEquals(cb1.called, 2)
        self.assertEquals(cb1.object, msg)
        self.assertEquals(cb2.called, 0)

        d.dispatch(pres)
        self.assertEquals(cb1.called, 2)
        self.assertEquals(cb2.called, 1)
        self.assertEquals(cb2.object, pres)

        self.assertEquals(cb3.called, 0)
        d.dispatch(d, "//event/testevent")
        self.assertEquals(cb3.called, 1)
        self.assertEquals(cb3.object, d)
        
        d.removeObserver("/presence", cb2.call)
        d.dispatch(pres)
        self.assertEquals(cb2.called, 1)

    def testAddObserverInDispatch(self):
        # Test for registration of events during dispatch
        d = EventDispatcher()
        msg = Element(("ns", "message"))
        pres = Element(("ns", "presence"))
        cb = CallbackTracker2(d)
        
        d.addObserver("/message", cb.call2)
        d.dispatch(msg)
        self.assertEquals(cb.called, 0)
        d.dispatch(pres)
        self.assertEquals(cb.called, 1)

    def testOnetimeDispatch(self):
        d = EventDispatcher()
        msg = Element(("ns", "message"))
        cb = CallbackTracker()

        d.addOnetimeObserver("/message", cb.call)
        d.dispatch(msg)
        self.assertEquals(cb.called, 1)
        d.dispatch(msg)
        self.assertEquals(cb.called, 1)
        

