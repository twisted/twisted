"""
Test cases for twisted.observable module.
"""

# System Imports
from operator import setitem

# Twisted Imports
from pyunit import unittest
from twisted.python import observable

class DummyEvent:
    pass

class SubscriberTestCase(unittest.TestCase):
    def setUp(self):
        self.publisher = observable.Publisher()
        self.subscriber = observable.Subscriber()

    def tearDown(self):
        del self.publisher
        del self.subscriber

    def testAttributeSubscription(self):
        def foo(publisher, channel, data):
            data.called = 1
            
        d = DummyEvent()
        d.called = 0
        self.subscriber.subscribeToAttribute('bar', 'baz', foo)
        self.subscriber.x = self.publisher
        self.publisher.publish('baz',d)
        assert not d.called, "Fired on wrong attribute."
        self.subscriber.bar = self.publisher
        self.publisher.publish('baz',d)
        assert d.called, "Foo should have been called now."
        d.called = 0
        self.subscriber.unsubscribeFromAttribute('bar','baz',foo)
        self.publisher.publish('baz',d)
        assert not d.called, "Should have been unsubscribed"

    def testWhenMethod(self):
        class WhenTest(observable.Subscriber):
            def when_foo_baz(self, foo, bazChannel, data):
                data.called = 1
        observable.registerWhenMethods(WhenTest)
        d = DummyEvent()
        d.called = 0
        w = WhenTest()
        w.foo = self.publisher
        self.publisher.publish('baz',d)
        assert d.called, "This method should have been called."
        d.called = 0
        self.publisher.publish('baz',d)
        assert d.called, "This method should have been called again."
        d.called = 0
        w.foo = None
        self.publisher.publish('baz',d)
        assert not d.called, "This method should not have been called"

class PublisherTestCase(unittest.TestCase):
    def setUp(self):
        self.publisher = observable.Publisher()
        
    def tearDown(self):
        del self.publisher
        
    def testDefaultSubscriber(self):
        class Foo(observable.Publisher):
            test = None
            def on_bar(self, data):
                self.test = data
        f = Foo()
        f.publish('bar',1)
        assert f.test == 1, 'default not called'
            
    def testBasicPublish(self):
        class Foo:
            def run(self, pub, chan, data):
                self.pub  = pub
                self.chan = chan
                self.test = data
        f = Foo()
        p = self.publisher
        p.subscribe('foo', f.run)
        testData = 'blah blah'
        p.publish('foo',testData)
        assert f.test == testData, 'variable not changed by publish'

        
testCases = [PublisherTestCase, SubscriberTestCase]
