# -*- test-case-name: twisted.web.test.test_web -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

from zope.interface import implements
from twisted.trial import unittest
from twisted.web._newresource import Response
from twisted.web.http import OK
from twisted.web.http_headers import Headers
from twisted.web.iweb import IBodyProducer, UNKNOWN_LENGTH


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


    def test_setBodyString(self):
        """
        Setting the body to a string will also set a content-length header.
        """
        response = Response()
        response.setBody("hello")
        self.assertEqual(response.body, "hello")
        self.assertEqual(response.headers.getRawHeaders("content-length"), ["5"])


    def test_setBodyProducerWithLength(self):
        """
        Setting the body to a producer that has a length will also set a
        content-length header.
        """
        response = Response()
        producer = Producer(200)
        response.setBody(producer)
        self.assertIdentical(response.body, producer)
        self.assertEqual(response.headers.getRawHeaders("content-length"), ["200"])


    def test_setBodyProducerWithoutLength(self):
        """
        Setting the body to a producer that has an unknown length will not set
        a content-length header.
        """
        response = Response()
        producer = Producer(UNKNOWN_LENGTH)
        response.setBody(producer)
        self.assertIdentical(response.body, producer)
        self.assertEqual(list(response.headers.getAllRawHeaders()), [])


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
        self.assertEqual(sorted(list(response.headers.getAllRawHeaders())),
                         [("Content-Length", ["5"]), ("Test", ["value"])])
        self.assertEqual(response.body, "hello")
