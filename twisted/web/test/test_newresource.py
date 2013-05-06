# -*- test-case-name: twisted.web.test.test_web -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

from zope.interface import implements
from twisted.internet.defer import succeed
from twisted.trial import unittest
from twisted.web._newresource import Response, Path, INDEX, _TraversalStep, traverse
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
        self.assertEqual(Path.fromString("/I%2FO/a%20b").segments,
            (u"I/O", u"a b"))


    def test_leaf(self):
        """
        L{Path.leaf} returns a L{Path} with no segments.
        """
        l = Path.leaf()
        self.assertEqual(l.segments, ())


    def test_child(self):
        """
        L{Path.child} consumes one of the segments in the path.
        """
        p = Path.fromString("/foo/bar/baz")
        segment, child = p.child()
        self.assertIsInstance(child, Path)
        self.assertEqual(segment, u"foo")
        self.assertEqual(child.segments, (u"bar", u"baz"))


    def test_leafHasNoChild(self):
        """L{Path.child} raises ValueError on leaf nodes."""
        l = Path.leaf()
        self.assertRaises(ValueError, l.child)


    def test_traverseUsing(self):
        """
        L{Path.traverseUsing} returns a L{_TraversalStep}.
        """
        p = Path.fromString("/foo/bar/baz")
        step = p.traverseUsing("resource")
        self.assertIsInstance(step, _TraversalStep)
        self.assertEqual(step, (p, "resource"))


    def test_descend(self):
        """L{Path.descend} consumes multiple segments."""
        p = Path.fromString("/foo/bar/baz")
        consumed, remainder = p.descend(2)
        self.assertEqual(consumed, (u"foo", u"bar"))
        self.assertEqual(remainder, Path((u"baz",)))


    def test_descendAll(self):
        """L{Path.descend}ing through all segments leaves a leaf."""
        p = Path.fromString("/foo/bar/baz")
        consumed, remainder = p.descend(3)
        self.assertEqual(consumed, (u"foo", u"bar", u"baz"))
        self.assertEqual(remainder, Path.leaf())


    def test_descendTooDeepRaises(self):
        p = Path.fromString("sediment/ig.intrusive/metamorphic/ig.extrusive")
        self.assertRaises(ValueError, p.descend, 5)


    def test_eq(self):
        """L{Path}s are equal if their segments are equal."""
        p1 = Path.fromString("/foo/bar/baz")
        p1b = Path.fromString("/foo/bar/baz")
        self.assertTrue(p1 == p1)
        self.assertTrue(p1 == p1b)

        p2 = Path.fromString("/foo/bar/fizz")
        self.assertNot(p1 == p2)


    def test_repr(self):
        """repr contains class and segments."""
        p1 = Path.fromString("/foo/bar/baz")
        self.assertEqual(repr(p1),
            "<twisted.web._newresource.Path (u'foo', u'bar', u'baz')>")



class SingleChildResource(object):
    # implements IResource

    def __init__(self, name, child):
        self.name = name
        self.child = child


    def traverse(self, request, path):
        if not self.child:
            raise RuntimeError("WAT")
        segment, childPath = path.child()
        return childPath.traverseUsing(self.child)


    def __repr__(self):
        return "<%s %r>" % (self.__class__.__name__, self.name)



class SingleChildDeferredResource(SingleChildResource):
    def traverse(self, request, path):
        segment, childPath = path.child()
        return childPath.traverseUsing(succeed(self.child))



class TestTraverse(unittest.TestCase):


    def test_traverseEmptyPath(self):
        """The empty path has a single step: the root resource.

        XXX: Is there ever an empty path, or does a request
            to / result in Path((INDEX,))?
        """
        request = "REQUEST_OBJECT"
        path = Path.leaf()
        rootResource = SingleChildResource("root", None)
        dResource = traverse(request, path, rootResource)

        @dResource.addCallback
        def traverseDone(history):
            self.assertEqual(history, [(path, rootResource)])
        return dResource


    def test_traverse(self):
        """Traverse with resources using one segment at a time."""
        request = "REQUEST_OBJECT"
        path = Path((u"foo", u"bar"))
        leafResource = SingleChildResource("leaf", None)
        middleResource = SingleChildResource("middle", leafResource)
        rootResource = SingleChildResource("root", middleResource)
        dResource = traverse(request, path, rootResource)

        history = self.successResultOf(dResource)

        self.assertEqual(history, [
            (path, rootResource),
            (Path((u"bar",)), middleResource),
            (Path.leaf(), leafResource),
        ])


    def test_traverseDeferred(self):
        """Traverse with resources using one segment at a time."""
        request = "REQUEST_OBJECT"
        path = Path((u"foo",))
        leafResource = SingleChildDeferredResource("leaf", None)
        rootResource = SingleChildDeferredResource("root", leafResource)
        dResource = traverse(request, path, rootResource)

        history = self.successResultOf(dResource)

        self.assertEqual(history, [
            (path, rootResource),
            (Path.leaf(), leafResource),
        ])

    # TODO: Test with resources that consume multiple path segments
    # TODO: Should there be an escape hatch if busted resources send the
    #     traversal into a loop?



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
