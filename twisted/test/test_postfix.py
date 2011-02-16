# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Test cases for twisted.protocols.postfix module.
"""

from twisted.trial import unittest
from twisted.protocols import postfix
from twisted.test.proto_helpers import StringTransport


class PostfixTCPMapQuoteTestCase(unittest.TestCase):
    data = [
        # (raw, quoted, [aliasQuotedForms]),
        ('foo', 'foo'),
        ('foo bar', 'foo%20bar'),
        ('foo\tbar', 'foo%09bar'),
        ('foo\nbar', 'foo%0Abar', 'foo%0abar'),
        ('foo\r\nbar', 'foo%0D%0Abar', 'foo%0D%0abar', 'foo%0d%0Abar', 'foo%0d%0abar'),
        ('foo ', 'foo%20'),
        (' foo', '%20foo'),
        ]

    def testData(self):
        for entry in self.data:
            raw = entry[0]
            quoted = entry[1:]

            self.assertEquals(postfix.quote(raw), quoted[0])
            for q in quoted:
                self.assertEquals(postfix.unquote(q), raw)

class PostfixTCPMapServerTestCase:
    data = {
        # 'key': 'value',
        }

    chat = [
        # (input, expected_output),
        ]

    def test_chat(self):
        """
        Test that I{get} and I{put} commands are responded to correctly by
        L{postfix.PostfixTCPMapServer} when its factory is an instance of
        L{postifx.PostfixTCPMapDictServerFactory}.
        """
        factory = postfix.PostfixTCPMapDictServerFactory(self.data)
        transport = StringTransport()

        protocol = postfix.PostfixTCPMapServer()
        protocol.service = factory
        protocol.factory = factory
        protocol.makeConnection(transport)

        for input, expected_output in self.chat:
            protocol.lineReceived(input)
            self.assertEquals(
                transport.value(), expected_output,
                'For %r, expected %r but got %r' % (
                    input, expected_output, transport.value()))
            transport.clear()
        protocol.setTimeout(None)


    def test_deferredChat(self):
        """
        Test that I{get} and I{put} commands are responded to correctly by
        L{postfix.PostfixTCPMapServer} when its factory is an instance of
        L{postifx.PostfixTCPMapDeferringDictServerFactory}.
        """
        factory = postfix.PostfixTCPMapDeferringDictServerFactory(self.data)
        transport = StringTransport()

        protocol = postfix.PostfixTCPMapServer()
        protocol.service = factory
        protocol.factory = factory
        protocol.makeConnection(transport)

        for input, expected_output in self.chat:
            protocol.lineReceived(input)
            self.assertEquals(
                transport.value(), expected_output,
                'For %r, expected %r but got %r' % (
                    input, expected_output, transport.value()))
            transport.clear()
        protocol.setTimeout(None)



class Valid(PostfixTCPMapServerTestCase, unittest.TestCase):
    data = {
        'foo': 'ThisIs Foo',
        'bar': ' bar really is found\r\n',
        }
    chat = [
        ('get', "400 Command 'get' takes 1 parameters.\n"),
        ('get foo bar', "500 \n"),
        ('put', "400 Command 'put' takes 2 parameters.\n"),
        ('put foo', "400 Command 'put' takes 2 parameters.\n"),
        ('put foo bar baz', "500 put is not implemented yet.\n"),
        ('put foo bar', '500 put is not implemented yet.\n'),
        ('get foo', '200 ThisIs%20Foo\n'),
        ('get bar', '200 %20bar%20really%20is%20found%0D%0A\n'),
        ('get baz', '500 \n'),
        ('foo', '400 unknown command\n'),
        ]
