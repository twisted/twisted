# Copyright (c) 2001-2007 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Test cases for twisted.words.xish.utility
"""

from twisted.trial import unittest

from twisted.python.util import OrderedDict
from twisted.words.xish import utility
from twisted.words.xish.domish import Element
from twisted.words.xish.utility import EventDispatcher

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

class OrderedCallbackTracker:
    def __init__(self):
        self.callList = []

    def call1(self, object):
        self.callList.append(self.call1)

    def call2(self, object):
        self.callList.append(self.call2)

    def call3(self, object):
        self.callList.append(self.call3)

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

    def test_addObserverTwice(self):
        """
        Test adding two observers for the same query.

        When the event is dispath both of the observers need to be called.
        """
        d = EventDispatcher()
        cb1 = CallbackTracker()
        cb2 = CallbackTracker()

        d.addObserver("//event/testevent", cb1.call)
        d.addObserver("//event/testevent", cb2.call)
        d.dispatch(d, "//event/testevent")

        self.assertEquals(cb1.called, 1)
        self.assertEquals(cb1.object, d)
        self.assertEquals(cb2.called, 1)
        self.assertEquals(cb2.object, d)

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

    def testDispatcherResult(self):
        d = EventDispatcher()
        msg = Element(("ns", "message"))
        pres = Element(("ns", "presence"))
        cb = CallbackTracker()

        d.addObserver("/presence", cb.call)
        result = d.dispatch(msg)
        self.assertEquals(False, result)

        result = d.dispatch(pres)
        self.assertEquals(True, result)

    def testOrderedXPathDispatch(self):
        d = EventDispatcher()
        cb = OrderedCallbackTracker()
        d.addObserver("/message/body", cb.call2)
        d.addObserver("/message", cb.call3, -1)
        d.addObserver("/message/body", cb.call1, 1)

        msg = Element(("ns", "message"))
        msg.addElement("body")
        d.dispatch(msg)
        self.assertEquals(cb.callList, [cb.call1, cb.call2, cb.call3],
                          "Calls out of order: %s" %
                          repr([c.__name__ for c in cb.callList]))

    # Observers are put into CallbackLists that are then put into dictionaries
    # keyed by the event trigger. Upon removal of the last observer for a
    # particular event trigger, the (now empty) CallbackList and corresponding
    # event trigger should be removed from those dictionaries to prevent
    # slowdown and memory leakage.

    def test_cleanUpRemoveEventObserver(self):
        """
        Test observer clean-up after removeObserver for named events.
        """

        d = EventDispatcher()
        cb = CallbackTracker()

        d.addObserver('//event/test', cb.call)
        d.dispatch(None, '//event/test')
        self.assertEqual(1, cb.called)
        d.removeObserver('//event/test', cb.call)
        self.assertEqual(0, len(d._eventObservers.pop(0)))

    def test_cleanUpRemoveXPathObserver(self):
        """
        Test observer clean-up after removeObserver for XPath events.
        """

        d = EventDispatcher()
        cb = CallbackTracker()
        msg = Element((None, "message"))

        d.addObserver('/message', cb.call)
        d.dispatch(msg)
        self.assertEqual(1, cb.called)
        d.removeObserver('/message', cb.call)
        self.assertEqual(0, len(d._xpathObservers.pop(0)))

    def test_cleanUpOnetimeEventObserver(self):
        """
        Test observer clean-up after onetime named events.
        """

        d = EventDispatcher()
        cb = CallbackTracker()

        d.addOnetimeObserver('//event/test', cb.call)
        d.dispatch(None, '//event/test')
        self.assertEqual(1, cb.called)
        self.assertEqual(0, len(d._eventObservers.pop(0)))

    def test_cleanUpOnetimeXPathObserver(self):
        """
        Test observer clean-up after onetime XPath events.
        """

        d = EventDispatcher()
        cb = CallbackTracker()
        msg = Element((None, "message"))

        d.addOnetimeObserver('/message', cb.call)
        d.dispatch(msg)
        self.assertEqual(1, cb.called)
        self.assertEqual(0, len(d._xpathObservers.pop(0)))

    def test_observerRaisingException(self):
        """
        Test that exceptions in observers do not bubble up to dispatch.

        The exceptions raised in observers should be logged and other
        observers should be called as if nothing happened.
        """

        class OrderedCallbackList(utility.CallbackList):
            def __init__(self):
                self.callbacks = OrderedDict()

        class TestError(Exception):
            pass

        def raiseError(_):
            raise TestError()

        d = EventDispatcher()
        cb = CallbackTracker()

        originalCallbackList = utility.CallbackList

        try:
            utility.CallbackList = OrderedCallbackList

            d.addObserver('//event/test', raiseError)
            d.addObserver('//event/test', cb.call)
            try:
                d.dispatch(None, '//event/test')
            except TestError:
                self.fail("TestError raised. Should have been logged instead.")

            self.assertEqual(1, len(self.flushLoggedErrors(TestError)))
            self.assertEqual(1, cb.called)
        finally:
            utility.CallbackList = originalCallbackList
