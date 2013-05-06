# -*- test-case-name: twisted.web.test.test_web -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

from zope.interface import implements
from twisted.trial import unittest
from twisted.web._newresource import Response, Path, INDEX, _TraversalStep
from twisted.web.http import OK
from twisted.web.http_headers import Headers
from twisted.web.iweb import IBodyProducer, UNKNOWN_LENGTH



class PathTests(unittest.TestCase):
    """
    Tests for L{Path}.
    """

    def test_fromStringNoQuoting(self):
        """
        L{Path.fromString} parses paths without URL quoting into the
        appropriate segments.
        """
        def getSegments(p):
            return Path.fromString(p).segments
        self.assertEqual(getSegments("/"), (INDEX,))
        self.assertEqual(getSegments("/foo"), (u"foo",))
        self.assertEqual(getSegments("/foo/"), (u"foo", INDEX))
        self.assertEqual(getSegments("/foo/bar"), (u"foo", u"bar"))
        self.assertEqual(getSegments("/foo//"), (u"foo", INDEX, INDEX))


    def test_fromStringQuoting(self):
        """
        L{Path.fromString} can do URL unquoting.
        """
    test_fromStringQuoting.todo = "laters"


    def test_leaf(self):
        """
        L{Path.leaf} returns a L{Path} with no segments.
        """
        l = Path.leaf()
        self.assertEqual(l.segments, ())

    # XXX Test child() of leaf raises.

    def test_child(self):
        """
        L{Path.child} consumes one of the segments in the path.
        """
        p = Path.fromString("/foo/bar/baz")
        segment, child = p.child()
        self.assertIsInstance(child, Path)
        self.assertEqual(segment, u"foo")
        self.assertEqual(child.segments, (u"bar", u"baz"))


    def test_traverseUsing(self):
        """
        L{Path.traverseUsing} returns a L{_TraversalStep}.
        """
        p = Path.fromString("/foo/bar/baz")
        step = p.traverseUsing("resource")
        self.assertIsInstance(step, _TraversalStep)
        self.assertEqual(step, (p, "resource"))



class Producer:
    """
    A simple producer.
    """
    implements(IBodyProducer)

    def __init__(self, length):
        self.length = length



class ResponseTests(unittest.TestCase):
    """
    The L{Response} class should allow for easy setup by users.
    """

    def test_defaults(self):
        """
        By default a L{Response} will have empty headers, empty body and a
        response code of OK.
        """
        response = Response()
        self.assertEqual(response.code, OK)
        self.assertIsInstance(response.headers, Headers)
        self.assertEqual(list(response.headers.getAllRawHeaders()), [])
        self.assertEqual(response.body, None)


    def test_setBody(self):
        """
        Setting the body to a string will store it on the response.
        """
        response = Response()
        response.setBody("hello")
        self.assertEqual(response.body, "hello")


    def test_setBodyProducer(self):
        """
        Setting the body to a producer will store it on the body.
        """
        response = Response()
        producer = Producer(200)
        response.setBody(producer)
        self.assertIdentical(response.body, producer)


    def test_cantSetBodyTwice(self):
        """
        Setting the body twice will fail.
        """
        response = Response()
        response.setBody("hello")
        exc = self.assertRaises(RuntimeError, response.setBody, "world")
        self.assertEqual(exc.args[0], "Can't set body twice.")
        self.assertEqual(response.body, "hello")


    def test_nonDefault(self):
        """
        L{Response} instances can be created with non-default values.
        """
        headers = Headers()
        headers.addRawHeader("test", "value")
        response = Response(700, headers, "hello")
        self.assertEqual(response.code, 700)
        # Headers should be copied:
        self.assertNotIdentical(response.headers, headers)
        self.assertEqual(list(response.headers.getAllRawHeaders()),
                         [("Test", ["value"])])
        self.assertEqual(response.body, "hello")
