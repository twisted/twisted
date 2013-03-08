# -*- test-case-name: twisted.mail.test.test_imap -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


"""
Test case for twisted.mail.imap4
"""

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

import codecs
import locale
import os
import types

from zope.interface import implements

from twisted.mail.imap4 import MessageSet
from twisted.mail import imap4
from twisted.protocols import loopback
from twisted.internet import defer
from twisted.internet import error
from twisted.internet import reactor
from twisted.internet import interfaces
from twisted.internet.task import Clock
from twisted.trial import unittest
from twisted.python import util, log
from twisted.python import failure

from twisted import cred
import twisted.cred.error
import twisted.cred.checkers
import twisted.cred.credentials
import twisted.cred.portal

from twisted.test.proto_helpers import StringTransport, StringTransportWithDisconnection

try:
    from twisted.test.ssl_helpers import ClientTLSContext, ServerTLSContext
except ImportError:
    ClientTLSContext = ServerTLSContext = None

def strip(f):
    return lambda result, f=f: f()

def sortNest(l):
    l = l[:]
    l.sort()
    for i in range(len(l)):
        if isinstance(l[i], types.ListType):
            l[i] = sortNest(l[i])
        elif isinstance(l[i], types.TupleType):
            l[i] = tuple(sortNest(list(l[i])))
    return l

class IMAP4UTF7TestCase(unittest.TestCase):
    tests = [
        [u'Hello world', 'Hello world'],
        [u'Hello & world', 'Hello &- world'],
        [u'Hello\xffworld', 'Hello&AP8-world'],
        [u'\xff\xfe\xfd\xfc', '&AP8A,gD9APw-'],
        [u'~peter/mail/\u65e5\u672c\u8a9e/\u53f0\u5317',
         '~peter/mail/&ZeVnLIqe-/&U,BTFw-'], # example from RFC 2060
    ]

    def test_encodeWithErrors(self):
        """
        Specifying an error policy to C{unicode.encode} with the
        I{imap4-utf-7} codec should produce the same result as not
        specifying the error policy.
        """
        text = u'Hello world'
        self.assertEqual(
            text.encode('imap4-utf-7', 'strict'),
            text.encode('imap4-utf-7'))


    def test_decodeWithErrors(self):
        """
        Similar to L{test_encodeWithErrors}, but for C{str.decode}.
        """
        bytes = 'Hello world'
        self.assertEqual(
            bytes.decode('imap4-utf-7', 'strict'),
            bytes.decode('imap4-utf-7'))


    def test_getreader(self):
        """
        C{codecs.getreader('imap4-utf-7')} returns the I{imap4-utf-7} stream
        reader class.
        """
        reader = codecs.getreader('imap4-utf-7')(StringIO('Hello&AP8-world'))
        self.assertEqual(reader.read(), u'Hello\xffworld')


    def test_getwriter(self):
        """
        C{codecs.getwriter('imap4-utf-7')} returns the I{imap4-utf-7} stream
        writer class.
        """
        output = StringIO()
        writer = codecs.getwriter('imap4-utf-7')(output)
        writer.write(u'Hello\xffworld')
        self.assertEqual(output.getvalue(), 'Hello&AP8-world')


    def test_encode(self):
        """
        The I{imap4-utf-7} can be used to encode a unicode string into a byte
        string according to the IMAP4 modified UTF-7 encoding rules.
        """
        for (input, output) in self.tests:
            self.assertEqual(input.encode('imap4-utf-7'), output)


    def test_decode(self):
        """
        The I{imap4-utf-7} can be used to decode a byte string into a unicode
        string according to the IMAP4 modified UTF-7 encoding rules.
        """
        for (input, output) in self.tests:
            self.assertEqual(input, output.decode('imap4-utf-7'))


    def test_printableSingletons(self):
        """
        The IMAP4 modified UTF-7 implementation encodes all printable
        characters which are in ASCII using the corresponding ASCII byte.
        """
        # All printables represent themselves
        for o in range(0x20, 0x26) + range(0x27, 0x7f):
            self.assertEqual(chr(o), chr(o).encode('imap4-utf-7'))
            self.assertEqual(chr(o), chr(o).decode('imap4-utf-7'))
        self.assertEqual('&'.encode('imap4-utf-7'), '&-')
        self.assertEqual('&-'.decode('imap4-utf-7'), '&')



class BufferingConsumer:
    def __init__(self):
        self.buffer = []

    def write(self, bytes):
        self.buffer.append(bytes)
        if self.consumer:
            self.consumer.resumeProducing()

    def registerProducer(self, consumer, streaming):
        self.consumer = consumer
        self.consumer.resumeProducing()

    def unregisterProducer(self):
        self.consumer = None

class MessageProducerTestCase(unittest.TestCase):
    def testSinglePart(self):
        body = 'This is body text.  Rar.'
        headers = util.OrderedDict()
        headers['from'] = 'sender@host'
        headers['to'] = 'recipient@domain'
        headers['subject'] = 'booga booga boo'
        headers['content-type'] = 'text/plain'

        msg = FakeyMessage(headers, (), None, body, 123, None )

        c = BufferingConsumer()
        p = imap4.MessageProducer(msg)
        d = p.beginProducing(c)

        def cbProduced(result):
            self.assertIdentical(result, p)
            self.assertEqual(
                ''.join(c.buffer),

                '{119}\r\n'
                'From: sender@host\r\n'
                'To: recipient@domain\r\n'
                'Subject: booga booga boo\r\n'
                'Content-Type: text/plain\r\n'
                '\r\n'
                + body)
        return d.addCallback(cbProduced)


    def testSingleMultiPart(self):
        outerBody = ''
        innerBody = 'Contained body message text.  Squarge.'
        headers = util.OrderedDict()
        headers['from'] = 'sender@host'
        headers['to'] = 'recipient@domain'
        headers['subject'] = 'booga booga boo'
        headers['content-type'] = 'multipart/alternative; boundary="xyz"'

        innerHeaders = util.OrderedDict()
        innerHeaders['subject'] = 'this is subject text'
        innerHeaders['content-type'] = 'text/plain'
        msg = FakeyMessage(headers, (), None, outerBody, 123,
                           [FakeyMessage(innerHeaders, (), None, innerBody,
                                         None, None)],
                           )

        c = BufferingConsumer()
        p = imap4.MessageProducer(msg)
        d = p.beginProducing(c)

        def cbProduced(result):
            self.failUnlessIdentical(result, p)

            self.assertEqual(
                ''.join(c.buffer),

                '{239}\r\n'
                'From: sender@host\r\n'
                'To: recipient@domain\r\n'
                'Subject: booga booga boo\r\n'
                'Content-Type: multipart/alternative; boundary="xyz"\r\n'
                '\r\n'
                '\r\n'
                '--xyz\r\n'
                'Subject: this is subject text\r\n'
                'Content-Type: text/plain\r\n'
                '\r\n'
                + innerBody
                + '\r\n--xyz--\r\n')

        return d.addCallback(cbProduced)


    def testMultipleMultiPart(self):
        outerBody = ''
        innerBody1 = 'Contained body message text.  Squarge.'
        innerBody2 = 'Secondary <i>message</i> text of squarge body.'
        headers = util.OrderedDict()
        headers['from'] = 'sender@host'
        headers['to'] = 'recipient@domain'
        headers['subject'] = 'booga booga boo'
        headers['content-type'] = 'multipart/alternative; boundary="xyz"'
        innerHeaders = util.OrderedDict()
        innerHeaders['subject'] = 'this is subject text'
        innerHeaders['content-type'] = 'text/plain'
        innerHeaders2 = util.OrderedDict()
        innerHeaders2['subject'] = '<b>this is subject</b>'
        innerHeaders2['content-type'] = 'text/html'
        msg = FakeyMessage(headers, (), None, outerBody, 123, [
            FakeyMessage(innerHeaders, (), None, innerBody1, None, None),
            FakeyMessage(innerHeaders2, (), None, innerBody2, None, None)
            ],
        )

        c = BufferingConsumer()
        p = imap4.MessageProducer(msg)
        d = p.beginProducing(c)

        def cbProduced(result):
            self.failUnlessIdentical(result, p)

            self.assertEqual(
                ''.join(c.buffer),

                '{354}\r\n'
                'From: sender@host\r\n'
                'To: recipient@domain\r\n'
                'Subject: booga booga boo\r\n'
                'Content-Type: multipart/alternative; boundary="xyz"\r\n'
                '\r\n'
                '\r\n'
                '--xyz\r\n'
                'Subject: this is subject text\r\n'
                'Content-Type: text/plain\r\n'
                '\r\n'
                + innerBody1
                + '\r\n--xyz\r\n'
                'Subject: <b>this is subject</b>\r\n'
                'Content-Type: text/html\r\n'
                '\r\n'
                + innerBody2
                + '\r\n--xyz--\r\n')
        return d.addCallback(cbProduced)



class IMAP4HelperTestCase(unittest.TestCase):
    """
    Tests for various helper utilities in the IMAP4 module.
    """

    def test_fileProducer(self):
        b = (('x' * 1) + ('y' * 1) + ('z' * 1)) * 10
        c = BufferingConsumer()
        f = StringIO(b)
        p = imap4.FileProducer(f)
        d = p.beginProducing(c)

        def cbProduced(result):
            self.failUnlessIdentical(result, p)
            self.assertEqual(
                ('{%d}\r\n' % len(b))+ b,
                ''.join(c.buffer))
        return d.addCallback(cbProduced)


    def test_wildcard(self):
        cases = [
            ['foo/%gum/bar',
                ['foo/bar', 'oo/lalagum/bar', 'foo/gumx/bar', 'foo/gum/baz'],
                ['foo/xgum/bar', 'foo/gum/bar'],
            ], ['foo/x%x/bar',
                ['foo', 'bar', 'fuz fuz fuz', 'foo/*/bar', 'foo/xyz/bar', 'foo/xx/baz'],
                ['foo/xyx/bar', 'foo/xx/bar', 'foo/xxxxxxxxxxxxxx/bar'],
            ], ['foo/xyz*abc/bar',
                ['foo/xyz/bar', 'foo/abc/bar', 'foo/xyzab/cbar', 'foo/xyza/bcbar'],
                ['foo/xyzabc/bar', 'foo/xyz/abc/bar', 'foo/xyz/123/abc/bar'],
            ]
        ]

        for (wildcard, fail, succeed) in cases:
            wildcard = imap4.wildcardToRegexp(wildcard, '/')
            for x in fail:
                self.failIf(wildcard.match(x))
            for x in succeed:
                self.failUnless(wildcard.match(x))


    def test_wildcardNoDelim(self):
        cases = [
            ['foo/%gum/bar',
                ['foo/bar', 'oo/lalagum/bar', 'foo/gumx/bar', 'foo/gum/baz'],
                ['foo/xgum/bar', 'foo/gum/bar', 'foo/x/gum/bar'],
            ], ['foo/x%x/bar',
                ['foo', 'bar', 'fuz fuz fuz', 'foo/*/bar', 'foo/xyz/bar', 'foo/xx/baz'],
                ['foo/xyx/bar', 'foo/xx/bar', 'foo/xxxxxxxxxxxxxx/bar', 'foo/x/x/bar'],
            ], ['foo/xyz*abc/bar',
                ['foo/xyz/bar', 'foo/abc/bar', 'foo/xyzab/cbar', 'foo/xyza/bcbar'],
                ['foo/xyzabc/bar', 'foo/xyz/abc/bar', 'foo/xyz/123/abc/bar'],
            ]
        ]

        for (wildcard, fail, succeed) in cases:
            wildcard = imap4.wildcardToRegexp(wildcard, None)
            for x in fail:
                self.failIf(wildcard.match(x), x)
            for x in succeed:
                self.failUnless(wildcard.match(x), x)


    def test_headerFormatter(self):
        """
        L{imap4._formatHeaders} accepts a C{dict} of header name/value pairs and
        returns a string representing those headers in the standard multiline,
        C{":"}-separated format.
        """
        cases = [
            ({'Header1': 'Value1', 'Header2': 'Value2'}, 'Header2: Value2\r\nHeader1: Value1\r\n'),
        ]

        for (input, expected) in cases:
            output = imap4._formatHeaders(input)
            self.assertEqual(sorted(output.splitlines(True)),
                             sorted(expected.splitlines(True)))


    def test_messageSet(self):
        m1 = MessageSet()
        m2 = MessageSet()

        self.assertEqual(m1, m2)

        m1 = m1 + (1, 3)
        self.assertEqual(len(m1), 3)
        self.assertEqual(list(m1), [1, 2, 3])

        m2 = m2 + (1, 3)
        self.assertEqual(m1, m2)
        self.assertEqual(list(m1 + m2), [1, 2, 3])


    def test_messageSetStringRepresentationWithWildcards(self):
        """
        In a L{MessageSet}, in the presence of wildcards, if the highest message
        id is known, the wildcard should get replaced by that high value.
        """
        inputs = [
            MessageSet(imap4.parseIdList('*')),
            MessageSet(imap4.parseIdList('3:*', 6)),
            MessageSet(imap4.parseIdList('*:2', 6)),
        ]

        outputs = [
            "*",
            "3:6",
            "2:6",
        ]

        for i, o in zip(inputs, outputs):
            self.assertEqual(str(i), o)


    def test_messageSetStringRepresentationWithInversion(self):
        """
        In a L{MessageSet}, inverting the high and low numbers in a range
        doesn't affect the meaning of the range. For example, 3:2 displays just
        like 2:3, because according to the RFC they have the same meaning.
        """
        inputs = [
            MessageSet(imap4.parseIdList('2:3')),
            MessageSet(imap4.parseIdList('3:2')),
        ]

        outputs = [
            "2:3",
            "2:3",
        ]

        for i, o in zip(inputs, outputs):
            self.assertEqual(str(i), o)


    def test_quotedSplitter(self):
        cases = [
            '''Hello World''',
            '''Hello "World!"''',
            '''World "Hello" "How are you?"''',
            '''"Hello world" How "are you?"''',
            '''foo bar "baz buz" NIL''',
            '''foo bar "baz buz" "NIL"''',
            '''foo NIL "baz buz" bar''',
            '''foo "NIL" "baz buz" bar''',
            '''"NIL" bar "baz buz" foo''',
            'oo \\"oo\\" oo',
            '"oo \\"oo\\" oo"',
            'oo \t oo',
            '"oo \t oo"',
            'oo \\t oo',
            '"oo \\t oo"',
            'oo \o oo',
            '"oo \o oo"',
            'oo \\o oo',
            '"oo \\o oo"',
        ]

        answers = [
            ['Hello', 'World'],
            ['Hello', 'World!'],
            ['World', 'Hello', 'How are you?'],
            ['Hello world', 'How', 'are you?'],
            ['foo', 'bar', 'baz buz', None],
            ['foo', 'bar', 'baz buz', 'NIL'],
            ['foo', None, 'baz buz', 'bar'],
            ['foo', 'NIL', 'baz buz', 'bar'],
            ['NIL', 'bar', 'baz buz', 'foo'],
            ['oo', '"oo"', 'oo'],
            ['oo "oo" oo'],
            ['oo', 'oo'],
            ['oo \t oo'],
            ['oo', '\\t', 'oo'],
            ['oo \\t oo'],
            ['oo', '\o', 'oo'],
            ['oo \o oo'],
            ['oo', '\\o', 'oo'],
            ['oo \\o oo'],

        ]

        errors = [
            '"mismatched quote',
            'mismatched quote"',
            'mismatched"quote',
            '"oops here is" another"',
        ]

        for s in errors:
            self.assertRaises(imap4.MismatchedQuoting, imap4.splitQuoted, s)

        for (case, expected) in zip(cases, answers):
            self.assertEqual(imap4.splitQuoted(case), expected)


    def test_stringCollapser(self):
        cases = [
            ['a', 'b', 'c', 'd', 'e'],
            ['a', ' ', '"', 'b', 'c', ' ', '"', ' ', 'd', 'e'],
            [['a', 'b', 'c'], 'd', 'e'],
            ['a', ['b', 'c', 'd'], 'e'],
            ['a', 'b', ['c', 'd', 'e']],
            ['"', 'a', ' ', '"', ['b', 'c', 'd'], '"', ' ', 'e', '"'],
            ['a', ['"', ' ', 'b', 'c', ' ', ' ', '"'], 'd', 'e'],
        ]

        answers = [
            ['abcde'],
            ['a', 'bc ', 'de'],
            [['abc'], 'de'],
            ['a', ['bcd'], 'e'],
            ['ab', ['cde']],
            ['a ', ['bcd'], ' e'],
            ['a', [' bc  '], 'de'],
        ]

        for (case, expected) in zip(cases, answers):
            self.assertEqual(imap4.collapseStrings(case), expected)


    def test_parenParser(self):
        s = '\r\n'.join(['xx'] * 4)
        cases = [
            '(BODY.PEEK[HEADER.FIELDS.NOT (subject bcc cc)] {%d}\r\n%s)' % (len(s), s,),

#            '(FLAGS (\Seen) INTERNALDATE "17-Jul-1996 02:44:25 -0700" '
#            'RFC822.SIZE 4286 ENVELOPE ("Wed, 17 Jul 1996 02:23:25 -0700 (PDT)" '
#            '"IMAP4rev1 WG mtg summary and minutes" '
#            '(("Terry Gray" NIL "gray" "cac.washington.edu")) '
#            '(("Terry Gray" NIL "gray" "cac.washington.edu")) '
#            '(("Terry Gray" NIL "gray" "cac.washington.edu")) '
#            '((NIL NIL "imap" "cac.washington.edu")) '
#            '((NIL NIL "minutes" "CNRI.Reston.VA.US") '
#            '("John Klensin" NIL "KLENSIN" "INFOODS.MIT.EDU")) NIL NIL '
#            '"<B27397-0100000@cac.washington.edu>") '
#            'BODY ("TEXT" "PLAIN" ("CHARSET" "US-ASCII") NIL NIL "7BIT" 3028 92))',

            '(FLAGS (\Seen) INTERNALDATE "17-Jul-1996 02:44:25 -0700" '
            'RFC822.SIZE 4286 ENVELOPE ("Wed, 17 Jul 1996 02:23:25 -0700 (PDT)" '
            '"IMAP4rev1 WG mtg summary and minutes" '
            '(("Terry Gray" NIL gray cac.washington.edu)) '
            '(("Terry Gray" NIL gray cac.washington.edu)) '
            '(("Terry Gray" NIL gray cac.washington.edu)) '
            '((NIL NIL imap cac.washington.edu)) '
            '((NIL NIL minutes CNRI.Reston.VA.US) '
            '("John Klensin" NIL KLENSIN INFOODS.MIT.EDU)) NIL NIL '
            '<B27397-0100000@cac.washington.edu>) '
            'BODY (TEXT PLAIN (CHARSET US-ASCII) NIL NIL 7BIT 3028 92))',
            '("oo \\"oo\\" oo")',
            '("oo \\\\ oo")',
            '("oo \\ oo")',
            '("oo \\o")',
            '("oo \o")',
            '(oo \o)',
            '(oo \\o)',

        ]

        answers = [
            ['BODY.PEEK', ['HEADER.FIELDS.NOT', ['subject', 'bcc', 'cc']], s],

            ['FLAGS', [r'\Seen'], 'INTERNALDATE',
            '17-Jul-1996 02:44:25 -0700', 'RFC822.SIZE', '4286', 'ENVELOPE',
            ['Wed, 17 Jul 1996 02:23:25 -0700 (PDT)',
            'IMAP4rev1 WG mtg summary and minutes', [["Terry Gray", None,
            "gray", "cac.washington.edu"]], [["Terry Gray", None,
            "gray", "cac.washington.edu"]], [["Terry Gray", None,
            "gray", "cac.washington.edu"]], [[None, None, "imap",
            "cac.washington.edu"]], [[None, None, "minutes",
            "CNRI.Reston.VA.US"], ["John Klensin", None, "KLENSIN",
            "INFOODS.MIT.EDU"]], None, None,
            "<B27397-0100000@cac.washington.edu>"], "BODY", ["TEXT", "PLAIN",
            ["CHARSET", "US-ASCII"], None, None, "7BIT", "3028", "92"]],
            ['oo "oo" oo'],
            ['oo \\\\ oo'],
            ['oo \\ oo'],
            ['oo \\o'],
            ['oo \o'],
            ['oo', '\o'],
            ['oo', '\\o'],
        ]

        for (case, expected) in zip(cases, answers):
            self.assertEqual(imap4.parseNestedParens(case), [expected])

        # XXX This code used to work, but changes occurred within the
        # imap4.py module which made it no longer necessary for *all* of it
        # to work.  In particular, only the part that makes
        # 'BODY.PEEK[HEADER.FIELDS.NOT (Subject Bcc Cc)]' come out correctly
        # no longer needs to work.  So, I am loathe to delete the entire
        # section of the test. --exarkun
        #

#        for (case, expected) in zip(answers, cases):
#            self.assertEqual('(' + imap4.collapseNestedLists(case) + ')', expected)


    def test_fetchParserSimple(self):
        cases = [
            ['ENVELOPE', 'Envelope'],
            ['FLAGS', 'Flags'],
            ['INTERNALDATE', 'InternalDate'],
            ['RFC822.HEADER', 'RFC822Header'],
            ['RFC822.SIZE', 'RFC822Size'],
            ['RFC822.TEXT', 'RFC822Text'],
            ['RFC822', 'RFC822'],
            ['UID', 'UID'],
            ['BODYSTRUCTURE', 'BodyStructure'],
        ]

        for (inp, outp) in cases:
            p = imap4._FetchParser()
            p.parseString(inp)
            self.assertEqual(len(p.result), 1)
            self.failUnless(isinstance(p.result[0], getattr(p, outp)))


    def test_fetchParserMacros(self):
        cases = [
            ['ALL', (4, ['flags', 'internaldate', 'rfc822.size', 'envelope'])],
            ['FULL', (5, ['flags', 'internaldate', 'rfc822.size', 'envelope', 'body'])],
            ['FAST', (3, ['flags', 'internaldate', 'rfc822.size'])],
        ]

        for (inp, outp) in cases:
            p = imap4._FetchParser()
            p.parseString(inp)
            self.assertEqual(len(p.result), outp[0])
            p = [str(p).lower() for p in p.result]
            p.sort()
            outp[1].sort()
            self.assertEqual(p, outp[1])


    def test_fetchParserBody(self):
        P = imap4._FetchParser

        p = P()
        p.parseString('BODY')
        self.assertEqual(len(p.result), 1)
        self.failUnless(isinstance(p.result[0], p.Body))
        self.assertEqual(p.result[0].peek, False)
        self.assertEqual(p.result[0].header, None)
        self.assertEqual(str(p.result[0]), 'BODY')

        p = P()
        p.parseString('BODY.PEEK')
        self.assertEqual(len(p.result), 1)
        self.failUnless(isinstance(p.result[0], p.Body))
        self.assertEqual(p.result[0].peek, True)
        self.assertEqual(str(p.result[0]), 'BODY')

        p = P()
        p.parseString('BODY[]')
        self.assertEqual(len(p.result), 1)
        self.failUnless(isinstance(p.result[0], p.Body))
        self.assertEqual(p.result[0].empty, True)
        self.assertEqual(str(p.result[0]), 'BODY[]')

        p = P()
        p.parseString('BODY[HEADER]')
        self.assertEqual(len(p.result), 1)
        self.failUnless(isinstance(p.result[0], p.Body))
        self.assertEqual(p.result[0].peek, False)
        self.failUnless(isinstance(p.result[0].header, p.Header))
        self.assertEqual(p.result[0].header.negate, True)
        self.assertEqual(p.result[0].header.fields, ())
        self.assertEqual(p.result[0].empty, False)
        self.assertEqual(str(p.result[0]), 'BODY[HEADER]')

        p = P()
        p.parseString('BODY.PEEK[HEADER]')
        self.assertEqual(len(p.result), 1)
        self.failUnless(isinstance(p.result[0], p.Body))
        self.assertEqual(p.result[0].peek, True)
        self.failUnless(isinstance(p.result[0].header, p.Header))
        self.assertEqual(p.result[0].header.negate, True)
        self.assertEqual(p.result[0].header.fields, ())
        self.assertEqual(p.result[0].empty, False)
        self.assertEqual(str(p.result[0]), 'BODY[HEADER]')

        p = P()
        p.parseString('BODY[HEADER.FIELDS (Subject Cc Message-Id)]')
        self.assertEqual(len(p.result), 1)
        self.failUnless(isinstance(p.result[0], p.Body))
        self.assertEqual(p.result[0].peek, False)
        self.failUnless(isinstance(p.result[0].header, p.Header))
        self.assertEqual(p.result[0].header.negate, False)
        self.assertEqual(p.result[0].header.fields, ['SUBJECT', 'CC', 'MESSAGE-ID'])
        self.assertEqual(p.result[0].empty, False)
        self.assertEqual(str(p.result[0]), 'BODY[HEADER.FIELDS (Subject Cc Message-Id)]')

        p = P()
        p.parseString('BODY.PEEK[HEADER.FIELDS (Subject Cc Message-Id)]')
        self.assertEqual(len(p.result), 1)
        self.failUnless(isinstance(p.result[0], p.Body))
        self.assertEqual(p.result[0].peek, True)
        self.failUnless(isinstance(p.result[0].header, p.Header))
        self.assertEqual(p.result[0].header.negate, False)
        self.assertEqual(p.result[0].header.fields, ['SUBJECT', 'CC', 'MESSAGE-ID'])
        self.assertEqual(p.result[0].empty, False)
        self.assertEqual(str(p.result[0]), 'BODY[HEADER.FIELDS (Subject Cc Message-Id)]')

        p = P()
        p.parseString('BODY.PEEK[HEADER.FIELDS.NOT (Subject Cc Message-Id)]')
        self.assertEqual(len(p.result), 1)
        self.failUnless(isinstance(p.result[0], p.Body))
        self.assertEqual(p.result[0].peek, True)
        self.failUnless(isinstance(p.result[0].header, p.Header))
        self.assertEqual(p.result[0].header.negate, True)
        self.assertEqual(p.result[0].header.fields, ['SUBJECT', 'CC', 'MESSAGE-ID'])
        self.assertEqual(p.result[0].empty, False)
        self.assertEqual(str(p.result[0]), 'BODY[HEADER.FIELDS.NOT (Subject Cc Message-Id)]')

        p = P()
        p.parseString('BODY[1.MIME]<10.50>')
        self.assertEqual(len(p.result), 1)
        self.failUnless(isinstance(p.result[0], p.Body))
        self.assertEqual(p.result[0].peek, False)
        self.failUnless(isinstance(p.result[0].mime, p.MIME))
        self.assertEqual(p.result[0].part, (0,))
        self.assertEqual(p.result[0].partialBegin, 10)
        self.assertEqual(p.result[0].partialLength, 50)
        self.assertEqual(p.result[0].empty, False)
        self.assertEqual(str(p.result[0]), 'BODY[1.MIME]<10.50>')

        p = P()
        p.parseString('BODY.PEEK[1.3.9.11.HEADER.FIELDS.NOT (Message-Id Date)]<103.69>')
        self.assertEqual(len(p.result), 1)
        self.failUnless(isinstance(p.result[0], p.Body))
        self.assertEqual(p.result[0].peek, True)
        self.failUnless(isinstance(p.result[0].header, p.Header))
        self.assertEqual(p.result[0].part, (0, 2, 8, 10))
        self.assertEqual(p.result[0].header.fields, ['MESSAGE-ID', 'DATE'])
        self.assertEqual(p.result[0].partialBegin, 103)
        self.assertEqual(p.result[0].partialLength, 69)
        self.assertEqual(p.result[0].empty, False)
        self.assertEqual(str(p.result[0]), 'BODY[1.3.9.11.HEADER.FIELDS.NOT (Message-Id Date)]<103.69>')


    def test_files(self):
        inputStructure = [
            'foo', 'bar', 'baz', StringIO('this is a file\r\n'), 'buz'
        ]

        output = '"foo" "bar" "baz" {16}\r\nthis is a file\r\n "buz"'

        self.assertEqual(imap4.collapseNestedLists(inputStructure), output)


    def test_quoteAvoider(self):
        input = [
            'foo', imap4.DontQuoteMe('bar'), "baz", StringIO('this is a file\r\n'),
            imap4.DontQuoteMe('buz'), ""
        ]

        output = '"foo" bar "baz" {16}\r\nthis is a file\r\n buz ""'

        self.assertEqual(imap4.collapseNestedLists(input), output)


    def test_literals(self):
        cases = [
            ('({10}\r\n0123456789)', [['0123456789']]),
        ]

        for (case, expected) in cases:
            self.assertEqual(imap4.parseNestedParens(case), expected)


    def test_queryBuilder(self):
        inputs = [
            imap4.Query(flagged=1),
            imap4.Query(sorted=1, unflagged=1, deleted=1),
            imap4.Or(imap4.Query(flagged=1), imap4.Query(deleted=1)),
            imap4.Query(before='today'),
            imap4.Or(
                imap4.Query(deleted=1),
                imap4.Query(unseen=1),
                imap4.Query(new=1)
            ),
            imap4.Or(
                imap4.Not(
                    imap4.Or(
                        imap4.Query(sorted=1, since='yesterday', smaller=1000),
                        imap4.Query(sorted=1, before='tuesday', larger=10000),
                        imap4.Query(sorted=1, unseen=1, deleted=1, before='today'),
                        imap4.Not(
                            imap4.Query(subject='spam')
                        ),
                    ),
                ),
                imap4.Not(
                    imap4.Query(uid='1:5')
                ),
            )
        ]

        outputs = [
            'FLAGGED',
            '(DELETED UNFLAGGED)',
            '(OR FLAGGED DELETED)',
            '(BEFORE "today")',
            '(OR DELETED (OR UNSEEN NEW))',
            '(OR (NOT (OR (SINCE "yesterday" SMALLER 1000) ' # Continuing
            '(OR (BEFORE "tuesday" LARGER 10000) (OR (BEFORE ' # Some more
            '"today" DELETED UNSEEN) (NOT (SUBJECT "spam")))))) ' # And more
            '(NOT (UID 1:5)))',
        ]

        for (query, expected) in zip(inputs, outputs):
            self.assertEqual(query, expected)


    def test_queryKeywordFlagWithQuotes(self):
        """
        When passed the C{keyword} argument, L{imap4.Query} returns an unquoted
        string.

        @see: U{http://tools.ietf.org/html/rfc3501#section-9}
        @see: U{http://tools.ietf.org/html/rfc3501#section-6.4.4}
        """
        query = imap4.Query(keyword='twisted')
        self.assertEqual('(KEYWORD twisted)', query)


    def test_queryUnkeywordFlagWithQuotes(self):
        """
        When passed the C{unkeyword} argument, L{imap4.Query} returns an
        unquoted string.

        @see: U{http://tools.ietf.org/html/rfc3501#section-9}
        @see: U{http://tools.ietf.org/html/rfc3501#section-6.4.4}
        """
        query = imap4.Query(unkeyword='twisted')
        self.assertEqual('(UNKEYWORD twisted)', query)


    def _keywordFilteringTest(self, keyword):
        """
        Helper to implement tests for value filtering of KEYWORD and UNKEYWORD
        queries.

        @param keyword: A native string giving the name of the L{imap4.Query}
            keyword argument to test.
        """
        # Check all the printable exclusions
        self.assertEqual(
            '(%s twistedrocks)' % (keyword.upper(),),
            imap4.Query(**{keyword: r'twisted (){%*"\] rocks'}))

        # Check all the non-printable exclusions
        self.assertEqual(
            '(%s twistedrocks)' % (keyword.upper(),),
            imap4.Query(**{
                    keyword: 'twisted %s rocks' % (
                    ''.join(chr(ch) for ch in range(33)),)}))


    def test_queryKeywordFlag(self):
        """
        When passed the C{keyword} argument, L{imap4.Query} returns an
        C{atom} that consists of one or more non-special characters.

        List of the invalid characters:

            ( ) { % * " \ ] CTL SP

        @see: U{ABNF definition of CTL and SP<https://tools.ietf.org/html/rfc2234>}
        @see: U{IMAP4 grammar<http://tools.ietf.org/html/rfc3501#section-9>}
        @see: U{IMAP4 SEARCH specification<http://tools.ietf.org/html/rfc3501#section-6.4.4>}
        """
        self._keywordFilteringTest("keyword")


    def test_queryUnkeywordFlag(self):
        """
        When passed the C{unkeyword} argument, L{imap4.Query} returns an
        C{atom} that consists of one or more non-special characters.

        List of the invalid characters:

            ( ) { % * " \ ] CTL SP

        @see: U{ABNF definition of CTL and SP<https://tools.ietf.org/html/rfc2234>}
        @see: U{IMAP4 grammar<http://tools.ietf.org/html/rfc3501#section-9>}
        @see: U{IMAP4 SEARCH specification<http://tools.ietf.org/html/rfc3501#section-6.4.4>}
        """
        self._keywordFilteringTest("unkeyword")


    def test_invalidIdListParser(self):
        """
        Trying to parse an invalid representation of a sequence range raises an
        L{IllegalIdentifierError}.
        """
        inputs = [
            '*:*',
            'foo',
            '4:',
            'bar:5'
        ]

        for input in inputs:
            self.assertRaises(imap4.IllegalIdentifierError,
                              imap4.parseIdList, input, 12345)


    def test_invalidIdListParserNonPositive(self):
        """
        Zeroes and negative values are not accepted in id range expressions. RFC
        3501 states that sequence numbers and sequence ranges consist of
        non-negative numbers (RFC 3501 section 9, the seq-number grammar item).
        """
        inputs = [
            '0:5',
            '0:0',
            '*:0',
            '0',
            '-3:5',
            '1:-2',
            '-1'
        ]

        for input in inputs:
            self.assertRaises(imap4.IllegalIdentifierError,
                              imap4.parseIdList, input, 12345)


    def test_parseIdList(self):
        """
        The function to parse sequence ranges yields appropriate L{MessageSet}
        objects.
        """
        inputs = [
            '1:*',
            '5:*',
            '1:2,5:*',
            '*',
            '1',
            '1,2',
            '1,3,5',
            '1:10',
            '1:10,11',
            '1:5,10:20',
            '1,5:10',
            '1,5:10,15:20',
            '1:10,15,20:25',
            '4:2'
        ]

        outputs = [
            MessageSet(1, None),
            MessageSet(5, None),
            MessageSet(5, None) + MessageSet(1, 2),
            MessageSet(None, None),
            MessageSet(1),
            MessageSet(1, 2),
            MessageSet(1) + MessageSet(3) + MessageSet(5),
            MessageSet(1, 10),
            MessageSet(1, 11),
            MessageSet(1, 5) + MessageSet(10, 20),
            MessageSet(1) + MessageSet(5, 10),
            MessageSet(1) + MessageSet(5, 10) + MessageSet(15, 20),
            MessageSet(1, 10) + MessageSet(15) + MessageSet(20, 25),
            MessageSet(2, 4),
        ]

        lengths = [
            None, None, None,
            1, 1, 2, 3, 10, 11, 16, 7, 13, 17, 3
        ]

        for (input, expected) in zip(inputs, outputs):
            self.assertEqual(imap4.parseIdList(input), expected)

        for (input, expected) in zip(inputs, lengths):
            if expected is None:
                self.assertRaises(TypeError, len, imap4.parseIdList(input))
            else:
                L = len(imap4.parseIdList(input))
                self.assertEqual(L, expected,
                                  "len(%r) = %r != %r" % (input, L, expected))

class SimpleMailbox:
    implements(imap4.IMailboxInfo, imap4.IMailbox, imap4.ICloseableMailbox)

    flags = ('\\Flag1', 'Flag2', '\\AnotherSysFlag', 'LastFlag')
    messages = []
    mUID = 0
    rw = 1
    closed = False

    def __init__(self):
        self.listeners = []
        self.addListener = self.listeners.append
        self.removeListener = self.listeners.remove

    def getFlags(self):
        return self.flags

    def getUIDValidity(self):
        return 42

    def getUIDNext(self):
        return len(self.messages) + 1

    def getMessageCount(self):
        return 9

    def getRecentCount(self):
        return 3

    def getUnseenCount(self):
        return 4

    def isWriteable(self):
        return self.rw

    def destroy(self):
        pass

    def getHierarchicalDelimiter(self):
        return '/'

    def requestStatus(self, names):
        r = {}
        if 'MESSAGES' in names:
            r['MESSAGES'] = self.getMessageCount()
        if 'RECENT' in names:
            r['RECENT'] = self.getRecentCount()
        if 'UIDNEXT' in names:
            r['UIDNEXT'] = self.getMessageCount() + 1
        if 'UIDVALIDITY' in names:
            r['UIDVALIDITY'] = self.getUID()
        if 'UNSEEN' in names:
            r['UNSEEN'] = self.getUnseenCount()
        return defer.succeed(r)

    def addMessage(self, message, flags, date = None):
        self.messages.append((message, flags, date, self.mUID))
        self.mUID += 1
        return defer.succeed(None)

    def expunge(self):
        delete = []
        for i in self.messages:
            if '\\Deleted' in i[1]:
                delete.append(i)
        for i in delete:
            self.messages.remove(i)
        return [i[3] for i in delete]

    def close(self):
        self.closed = True

class Account(imap4.MemoryAccount):
    mailboxFactory = SimpleMailbox
    def _emptyMailbox(self, name, id):
        return self.mailboxFactory()

    def select(self, name, rw=1):
        mbox = imap4.MemoryAccount.select(self, name)
        if mbox is not None:
            mbox.rw = rw
        return mbox

class SimpleServer(imap4.IMAP4Server):
    def __init__(self, *args, **kw):
        imap4.IMAP4Server.__init__(self, *args, **kw)
        realm = TestRealm()
        realm.theAccount = Account('testuser')
        portal = cred.portal.Portal(realm)
        c = cred.checkers.InMemoryUsernamePasswordDatabaseDontUse()
        self.checker = c
        self.portal = portal
        portal.registerChecker(c)
        self.timeoutTest = False

    def lineReceived(self, line):
        if self.timeoutTest:
            #Do not send a respones
            return

        imap4.IMAP4Server.lineReceived(self, line)

    _username = 'testuser'
    _password = 'password-test'
    def authenticateLogin(self, username, password):
        if username == self._username and password == self._password:
            return imap4.IAccount, self.theAccount, lambda: None
        raise cred.error.UnauthorizedLogin()


class SimpleClient(imap4.IMAP4Client):
    def __init__(self, deferred, contextFactory = None):
        imap4.IMAP4Client.__init__(self, contextFactory)
        self.deferred = deferred
        self.events = []

    def serverGreeting(self, caps):
        self.deferred.callback(None)

    def modeChanged(self, writeable):
        self.events.append(['modeChanged', writeable])
        self.transport.loseConnection()

    def flagsChanged(self, newFlags):
        self.events.append(['flagsChanged', newFlags])
        self.transport.loseConnection()

    def newMessages(self, exists, recent):
        self.events.append(['newMessages', exists, recent])
        self.transport.loseConnection()



class IMAP4HelperMixin:

    serverCTX = None
    clientCTX = None

    def setUp(self):
        d = defer.Deferred()
        self.server = SimpleServer(contextFactory=self.serverCTX)
        self.client = SimpleClient(d, contextFactory=self.clientCTX)
        self.connected = d

        SimpleMailbox.messages = []
        theAccount = Account('testuser')
        theAccount.mboxType = SimpleMailbox
        SimpleServer.theAccount = theAccount


    def tearDown(self):
        del self.server
        del self.client
        del self.connected


    def _cbStopClient(self, ignore):
        self.client.transport.loseConnection()


    def _ebGeneral(self, failure):
        self.client.transport.loseConnection()
        self.server.transport.loseConnection()
        log.err(failure, "Problem with %r" % (self.function,))


    def loopback(self):
        return loopback.loopbackAsync(self.server, self.client)



class IMAP4ServerTestCase(IMAP4HelperMixin, unittest.TestCase):
    def testCapability(self):
        caps = {}
        def getCaps():
            def gotCaps(c):
                caps.update(c)
                self.server.transport.loseConnection()
            return self.client.getCapabilities().addCallback(gotCaps)
        d1 = self.connected.addCallback(strip(getCaps)).addErrback(self._ebGeneral)
        d = defer.gatherResults([self.loopback(), d1])
        expected = {'IMAP4rev1': None, 'NAMESPACE': None, 'IDLE': None}
        return d.addCallback(lambda _: self.assertEqual(expected, caps))

    def testCapabilityWithAuth(self):
        caps = {}
        self.server.challengers['CRAM-MD5'] = cred.credentials.CramMD5Credentials
        def getCaps():
            def gotCaps(c):
                caps.update(c)
                self.server.transport.loseConnection()
            return self.client.getCapabilities().addCallback(gotCaps)
        d1 = self.connected.addCallback(strip(getCaps)).addErrback(self._ebGeneral)
        d = defer.gatherResults([self.loopback(), d1])

        expCap = {'IMAP4rev1': None, 'NAMESPACE': None,
                  'IDLE': None, 'AUTH': ['CRAM-MD5']}

        return d.addCallback(lambda _: self.assertEqual(expCap, caps))

    def testLogout(self):
        self.loggedOut = 0
        def logout():
            def setLoggedOut():
                self.loggedOut = 1
            self.client.logout().addCallback(strip(setLoggedOut))
        self.connected.addCallback(strip(logout)).addErrback(self._ebGeneral)
        d = self.loopback()
        return d.addCallback(lambda _: self.assertEqual(self.loggedOut, 1))

    def testNoop(self):
        self.responses = None
        def noop():
            def setResponses(responses):
                self.responses = responses
                self.server.transport.loseConnection()
            self.client.noop().addCallback(setResponses)
        self.connected.addCallback(strip(noop)).addErrback(self._ebGeneral)
        d = self.loopback()
        return d.addCallback(lambda _: self.assertEqual(self.responses, []))

    def testLogin(self):
        def login():
            d = self.client.login('testuser', 'password-test')
            d.addCallback(self._cbStopClient)
        d1 = self.connected.addCallback(strip(login)).addErrback(self._ebGeneral)
        d = defer.gatherResults([d1, self.loopback()])
        return d.addCallback(self._cbTestLogin)

    def _cbTestLogin(self, ignored):
        self.assertEqual(self.server.account, SimpleServer.theAccount)
        self.assertEqual(self.server.state, 'auth')

    def testFailedLogin(self):
        def login():
            d = self.client.login('testuser', 'wrong-password')
            d.addBoth(self._cbStopClient)

        d1 = self.connected.addCallback(strip(login)).addErrback(self._ebGeneral)
        d2 = self.loopback()
        d = defer.gatherResults([d1, d2])
        return d.addCallback(self._cbTestFailedLogin)

    def _cbTestFailedLogin(self, ignored):
        self.assertEqual(self.server.account, None)
        self.assertEqual(self.server.state, 'unauth')


    def testLoginRequiringQuoting(self):
        self.server._username = '{test}user'
        self.server._password = '{test}password'

        def login():
            d = self.client.login('{test}user', '{test}password')
            d.addBoth(self._cbStopClient)

        d1 = self.connected.addCallback(strip(login)).addErrback(self._ebGeneral)
        d = defer.gatherResults([self.loopback(), d1])
        return d.addCallback(self._cbTestLoginRequiringQuoting)

    def _cbTestLoginRequiringQuoting(self, ignored):
        self.assertEqual(self.server.account, SimpleServer.theAccount)
        self.assertEqual(self.server.state, 'auth')


    def testNamespace(self):
        self.namespaceArgs = None
        def login():
            return self.client.login('testuser', 'password-test')
        def namespace():
            def gotNamespace(args):
                self.namespaceArgs = args
                self._cbStopClient(None)
            return self.client.namespace().addCallback(gotNamespace)

        d1 = self.connected.addCallback(strip(login))
        d1.addCallback(strip(namespace))
        d1.addErrback(self._ebGeneral)
        d2 = self.loopback()
        d = defer.gatherResults([d1, d2])
        d.addCallback(lambda _: self.assertEqual(self.namespaceArgs,
                                                  [[['', '/']], [], []]))
        return d

    def testSelect(self):
        SimpleServer.theAccount.addMailbox('test-mailbox')
        self.selectedArgs = None
        def login():
            return self.client.login('testuser', 'password-test')
        def select():
            def selected(args):
                self.selectedArgs = args
                self._cbStopClient(None)
            d = self.client.select('test-mailbox')
            d.addCallback(selected)
            return d

        d1 = self.connected.addCallback(strip(login))
        d1.addCallback(strip(select))
        d1.addErrback(self._ebGeneral)
        d2 = self.loopback()
        return defer.gatherResults([d1, d2]).addCallback(self._cbTestSelect)

    def _cbTestSelect(self, ignored):
        mbox = SimpleServer.theAccount.mailboxes['TEST-MAILBOX']
        self.assertEqual(self.server.mbox, mbox)
        self.assertEqual(self.selectedArgs, {
            'EXISTS': 9, 'RECENT': 3, 'UIDVALIDITY': 42,
            'FLAGS': ('\\Flag1', 'Flag2', '\\AnotherSysFlag', 'LastFlag'),
            'READ-WRITE': 1
        })


    def test_examine(self):
        """
        L{IMAP4Client.examine} issues an I{EXAMINE} command to the server and
        returns a L{Deferred} which fires with a C{dict} with as many of the
        following keys as the server includes in its response: C{'FLAGS'},
        C{'EXISTS'}, C{'RECENT'}, C{'UNSEEN'}, C{'READ-WRITE'}, C{'READ-ONLY'},
        C{'UIDVALIDITY'}, and C{'PERMANENTFLAGS'}.

        Unfortunately the server doesn't generate all of these so it's hard to
        test the client's handling of them here.  See
        L{IMAP4ClientExamineTests} below.

        See U{RFC 3501<http://www.faqs.org/rfcs/rfc3501.html>}, section 6.3.2,
        for details.
        """
        SimpleServer.theAccount.addMailbox('test-mailbox')
        self.examinedArgs = None
        def login():
            return self.client.login('testuser', 'password-test')
        def examine():
            def examined(args):
                self.examinedArgs = args
                self._cbStopClient(None)
            d = self.client.examine('test-mailbox')
            d.addCallback(examined)
            return d

        d1 = self.connected.addCallback(strip(login))
        d1.addCallback(strip(examine))
        d1.addErrback(self._ebGeneral)
        d2 = self.loopback()
        d = defer.gatherResults([d1, d2])
        return d.addCallback(self._cbTestExamine)


    def _cbTestExamine(self, ignored):
        mbox = SimpleServer.theAccount.mailboxes['TEST-MAILBOX']
        self.assertEqual(self.server.mbox, mbox)
        self.assertEqual(self.examinedArgs, {
            'EXISTS': 9, 'RECENT': 3, 'UIDVALIDITY': 42,
            'FLAGS': ('\\Flag1', 'Flag2', '\\AnotherSysFlag', 'LastFlag'),
            'READ-WRITE': False})


    def testCreate(self):
        succeed = ('testbox', 'test/box', 'test/', 'test/box/box', 'INBOX')
        fail = ('testbox', 'test/box')

        def cb(): self.result.append(1)
        def eb(failure): self.result.append(0)

        def login():
            return self.client.login('testuser', 'password-test')
        def create():
            for name in succeed + fail:
                d = self.client.create(name)
                d.addCallback(strip(cb)).addErrback(eb)
            d.addCallbacks(self._cbStopClient, self._ebGeneral)

        self.result = []
        d1 = self.connected.addCallback(strip(login)).addCallback(strip(create))
        d2 = self.loopback()
        d = defer.gatherResults([d1, d2])
        return d.addCallback(self._cbTestCreate, succeed, fail)

    def _cbTestCreate(self, ignored, succeed, fail):
        self.assertEqual(self.result, [1] * len(succeed) + [0] * len(fail))
        mbox = SimpleServer.theAccount.mailboxes.keys()
        answers = ['inbox', 'testbox', 'test/box', 'test', 'test/box/box']
        mbox.sort()
        answers.sort()
        self.assertEqual(mbox, [a.upper() for a in answers])

    def testDelete(self):
        SimpleServer.theAccount.addMailbox('delete/me')

        def login():
            return self.client.login('testuser', 'password-test')
        def delete():
            return self.client.delete('delete/me')
        d1 = self.connected.addCallback(strip(login))
        d1.addCallbacks(strip(delete), self._ebGeneral)
        d1.addCallbacks(self._cbStopClient, self._ebGeneral)
        d2 = self.loopback()
        d = defer.gatherResults([d1, d2])
        d.addCallback(lambda _:
                      self.assertEqual(SimpleServer.theAccount.mailboxes.keys(), []))
        return d

    def testIllegalInboxDelete(self):
        self.stashed = None
        def login():
            return self.client.login('testuser', 'password-test')
        def delete():
            return self.client.delete('inbox')
        def stash(result):
            self.stashed = result

        d1 = self.connected.addCallback(strip(login))
        d1.addCallbacks(strip(delete), self._ebGeneral)
        d1.addBoth(stash)
        d1.addCallbacks(self._cbStopClient, self._ebGeneral)
        d2 = self.loopback()
        d = defer.gatherResults([d1, d2])
        d.addCallback(lambda _: self.failUnless(isinstance(self.stashed,
                                                           failure.Failure)))
        return d


    def testNonExistentDelete(self):
        def login():
            return self.client.login('testuser', 'password-test')
        def delete():
            return self.client.delete('delete/me')
        def deleteFailed(failure):
            self.failure = failure

        self.failure = None
        d1 = self.connected.addCallback(strip(login))
        d1.addCallback(strip(delete)).addErrback(deleteFailed)
        d1.addCallbacks(self._cbStopClient, self._ebGeneral)
        d2 = self.loopback()
        d = defer.gatherResults([d1, d2])
        d.addCallback(lambda _: self.assertEqual(str(self.failure.value),
                                                  'No such mailbox'))
        return d


    def testIllegalDelete(self):
        m = SimpleMailbox()
        m.flags = (r'\Noselect',)
        SimpleServer.theAccount.addMailbox('delete', m)
        SimpleServer.theAccount.addMailbox('delete/me')

        def login():
            return self.client.login('testuser', 'password-test')
        def delete():
            return self.client.delete('delete')
        def deleteFailed(failure):
            self.failure = failure

        self.failure = None
        d1 = self.connected.addCallback(strip(login))
        d1.addCallback(strip(delete)).addErrback(deleteFailed)
        d1.addCallbacks(self._cbStopClient, self._ebGeneral)
        d2 = self.loopback()
        d = defer.gatherResults([d1, d2])
        expected = "Hierarchically inferior mailboxes exist and \\Noselect is set"
        d.addCallback(lambda _:
                      self.assertEqual(str(self.failure.value), expected))
        return d

    def testRename(self):
        SimpleServer.theAccount.addMailbox('oldmbox')
        def login():
            return self.client.login('testuser', 'password-test')
        def rename():
            return self.client.rename('oldmbox', 'newname')

        d1 = self.connected.addCallback(strip(login))
        d1.addCallbacks(strip(rename), self._ebGeneral)
        d1.addCallbacks(self._cbStopClient, self._ebGeneral)
        d2 = self.loopback()
        d = defer.gatherResults([d1, d2])
        d.addCallback(lambda _:
                      self.assertEqual(SimpleServer.theAccount.mailboxes.keys(),
                                        ['NEWNAME']))
        return d

    def testIllegalInboxRename(self):
        self.stashed = None
        def login():
            return self.client.login('testuser', 'password-test')
        def rename():
            return self.client.rename('inbox', 'frotz')
        def stash(stuff):
            self.stashed = stuff

        d1 = self.connected.addCallback(strip(login))
        d1.addCallbacks(strip(rename), self._ebGeneral)
        d1.addBoth(stash)
        d1.addCallbacks(self._cbStopClient, self._ebGeneral)
        d2 = self.loopback()
        d = defer.gatherResults([d1, d2])
        d.addCallback(lambda _:
                      self.failUnless(isinstance(self.stashed, failure.Failure)))
        return d

    def testHierarchicalRename(self):
        SimpleServer.theAccount.create('oldmbox/m1')
        SimpleServer.theAccount.create('oldmbox/m2')
        def login():
            return self.client.login('testuser', 'password-test')
        def rename():
            return self.client.rename('oldmbox', 'newname')

        d1 = self.connected.addCallback(strip(login))
        d1.addCallbacks(strip(rename), self._ebGeneral)
        d1.addCallbacks(self._cbStopClient, self._ebGeneral)
        d2 = self.loopback()
        d = defer.gatherResults([d1, d2])
        return d.addCallback(self._cbTestHierarchicalRename)

    def _cbTestHierarchicalRename(self, ignored):
        mboxes = SimpleServer.theAccount.mailboxes.keys()
        expected = ['newname', 'newname/m1', 'newname/m2']
        mboxes.sort()
        self.assertEqual(mboxes, [s.upper() for s in expected])

    def testSubscribe(self):
        def login():
            return self.client.login('testuser', 'password-test')
        def subscribe():
            return self.client.subscribe('this/mbox')

        d1 = self.connected.addCallback(strip(login))
        d1.addCallbacks(strip(subscribe), self._ebGeneral)
        d1.addCallbacks(self._cbStopClient, self._ebGeneral)
        d2 = self.loopback()
        d = defer.gatherResults([d1, d2])
        d.addCallback(lambda _:
                      self.assertEqual(SimpleServer.theAccount.subscriptions,
                                        ['THIS/MBOX']))
        return d

    def testUnsubscribe(self):
        SimpleServer.theAccount.subscriptions = ['THIS/MBOX', 'THAT/MBOX']
        def login():
            return self.client.login('testuser', 'password-test')
        def unsubscribe():
            return self.client.unsubscribe('this/mbox')

        d1 = self.connected.addCallback(strip(login))
        d1.addCallbacks(strip(unsubscribe), self._ebGeneral)
        d1.addCallbacks(self._cbStopClient, self._ebGeneral)
        d2 = self.loopback()
        d = defer.gatherResults([d1, d2])
        d.addCallback(lambda _:
                      self.assertEqual(SimpleServer.theAccount.subscriptions,
                                        ['THAT/MBOX']))
        return d

    def _listSetup(self, f):
        SimpleServer.theAccount.addMailbox('root/subthing')
        SimpleServer.theAccount.addMailbox('root/another-thing')
        SimpleServer.theAccount.addMailbox('non-root/subthing')

        def login():
            return self.client.login('testuser', 'password-test')
        def listed(answers):
            self.listed = answers

        self.listed = None
        d1 = self.connected.addCallback(strip(login))
        d1.addCallbacks(strip(f), self._ebGeneral)
        d1.addCallbacks(listed, self._ebGeneral)
        d1.addCallbacks(self._cbStopClient, self._ebGeneral)
        d2 = self.loopback()
        return defer.gatherResults([d1, d2]).addCallback(lambda _: self.listed)

    def testList(self):
        def list():
            return self.client.list('root', '%')
        d = self._listSetup(list)
        d.addCallback(lambda listed: self.assertEqual(
            sortNest(listed),
            sortNest([
                (SimpleMailbox.flags, "/", "ROOT/SUBTHING"),
                (SimpleMailbox.flags, "/", "ROOT/ANOTHER-THING")
            ])
        ))
        return d

    def testLSub(self):
        SimpleServer.theAccount.subscribe('ROOT/SUBTHING')
        def lsub():
            return self.client.lsub('root', '%')
        d = self._listSetup(lsub)
        d.addCallback(self.assertEqual,
                      [(SimpleMailbox.flags, "/", "ROOT/SUBTHING")])
        return d

    def testStatus(self):
        SimpleServer.theAccount.addMailbox('root/subthing')
        def login():
            return self.client.login('testuser', 'password-test')
        def status():
            return self.client.status('root/subthing', 'MESSAGES', 'UIDNEXT', 'UNSEEN')
        def statused(result):
            self.statused = result

        self.statused = None
        d1 = self.connected.addCallback(strip(login))
        d1.addCallbacks(strip(status), self._ebGeneral)
        d1.addCallbacks(statused, self._ebGeneral)
        d1.addCallbacks(self._cbStopClient, self._ebGeneral)
        d2 = self.loopback()
        d = defer.gatherResults([d1, d2])
        d.addCallback(lambda _: self.assertEqual(
            self.statused,
            {'MESSAGES': 9, 'UIDNEXT': '10', 'UNSEEN': 4}
        ))
        return d

    def testFailedStatus(self):
        def login():
            return self.client.login('testuser', 'password-test')
        def status():
            return self.client.status('root/nonexistent', 'MESSAGES', 'UIDNEXT', 'UNSEEN')
        def statused(result):
            self.statused = result
        def failed(failure):
            self.failure = failure

        self.statused = self.failure = None
        d1 = self.connected.addCallback(strip(login))
        d1.addCallbacks(strip(status), self._ebGeneral)
        d1.addCallbacks(statused, failed)
        d1.addCallbacks(self._cbStopClient, self._ebGeneral)
        d2 = self.loopback()
        return defer.gatherResults([d1, d2]).addCallback(self._cbTestFailedStatus)

    def _cbTestFailedStatus(self, ignored):
        self.assertEqual(
            self.statused, None
        )
        self.assertEqual(
            self.failure.value.args,
            ('Could not open mailbox',)
        )

    def testFullAppend(self):
        infile = util.sibpath(__file__, 'rfc822.message')
        message = open(infile)
        SimpleServer.theAccount.addMailbox('root/subthing')
        def login():
            return self.client.login('testuser', 'password-test')
        def append():
            return self.client.append(
                'root/subthing',
                message,
                ('\\SEEN', '\\DELETED'),
                'Tue, 17 Jun 2003 11:22:16 -0600 (MDT)',
            )

        d1 = self.connected.addCallback(strip(login))
        d1.addCallbacks(strip(append), self._ebGeneral)
        d1.addCallbacks(self._cbStopClient, self._ebGeneral)
        d2 = self.loopback()
        d = defer.gatherResults([d1, d2])
        return d.addCallback(self._cbTestFullAppend, infile)

    def _cbTestFullAppend(self, ignored, infile):
        mb = SimpleServer.theAccount.mailboxes['ROOT/SUBTHING']
        self.assertEqual(1, len(mb.messages))
        self.assertEqual(
            (['\\SEEN', '\\DELETED'], 'Tue, 17 Jun 2003 11:22:16 -0600 (MDT)', 0),
            mb.messages[0][1:]
        )
        self.assertEqual(open(infile).read(), mb.messages[0][0].getvalue())

    def testPartialAppend(self):
        infile = util.sibpath(__file__, 'rfc822.message')
        message = open(infile)
        SimpleServer.theAccount.addMailbox('PARTIAL/SUBTHING')
        def login():
            return self.client.login('testuser', 'password-test')
        def append():
            message = file(infile)
            return self.client.sendCommand(
                imap4.Command(
                    'APPEND',
                    'PARTIAL/SUBTHING (\\SEEN) "Right now" {%d}' % os.path.getsize(infile),
                    (), self.client._IMAP4Client__cbContinueAppend, message
                )
            )
        d1 = self.connected.addCallback(strip(login))
        d1.addCallbacks(strip(append), self._ebGeneral)
        d1.addCallbacks(self._cbStopClient, self._ebGeneral)
        d2 = self.loopback()
        d = defer.gatherResults([d1, d2])
        return d.addCallback(self._cbTestPartialAppend, infile)

    def _cbTestPartialAppend(self, ignored, infile):
        mb = SimpleServer.theAccount.mailboxes['PARTIAL/SUBTHING']
        self.assertEqual(1, len(mb.messages))
        self.assertEqual(
            (['\\SEEN'], 'Right now', 0),
            mb.messages[0][1:]
        )
        self.assertEqual(open(infile).read(), mb.messages[0][0].getvalue())

    def testCheck(self):
        SimpleServer.theAccount.addMailbox('root/subthing')
        def login():
            return self.client.login('testuser', 'password-test')
        def select():
            return self.client.select('root/subthing')
        def check():
            return self.client.check()

        d = self.connected.addCallback(strip(login))
        d.addCallbacks(strip(select), self._ebGeneral)
        d.addCallbacks(strip(check), self._ebGeneral)
        d.addCallbacks(self._cbStopClient, self._ebGeneral)
        return self.loopback()

        # Okay, that was fun

    def testClose(self):
        m = SimpleMailbox()
        m.messages = [
            ('Message 1', ('\\Deleted', 'AnotherFlag'), None, 0),
            ('Message 2', ('AnotherFlag',), None, 1),
            ('Message 3', ('\\Deleted',), None, 2),
        ]
        SimpleServer.theAccount.addMailbox('mailbox', m)
        def login():
            return self.client.login('testuser', 'password-test')
        def select():
            return self.client.select('mailbox')
        def close():
            return self.client.close()

        d = self.connected.addCallback(strip(login))
        d.addCallbacks(strip(select), self._ebGeneral)
        d.addCallbacks(strip(close), self._ebGeneral)
        d.addCallbacks(self._cbStopClient, self._ebGeneral)
        d2 = self.loopback()
        return defer.gatherResults([d, d2]).addCallback(self._cbTestClose, m)

    def _cbTestClose(self, ignored, m):
        self.assertEqual(len(m.messages), 1)
        self.assertEqual(m.messages[0], ('Message 2', ('AnotherFlag',), None, 1))
        self.failUnless(m.closed)

    def testExpunge(self):
        m = SimpleMailbox()
        m.messages = [
            ('Message 1', ('\\Deleted', 'AnotherFlag'), None, 0),
            ('Message 2', ('AnotherFlag',), None, 1),
            ('Message 3', ('\\Deleted',), None, 2),
        ]
        SimpleServer.theAccount.addMailbox('mailbox', m)
        def login():
            return self.client.login('testuser', 'password-test')
        def select():
            return self.client.select('mailbox')
        def expunge():
            return self.client.expunge()
        def expunged(results):
            self.failIf(self.server.mbox is None)
            self.results = results

        self.results = None
        d1 = self.connected.addCallback(strip(login))
        d1.addCallbacks(strip(select), self._ebGeneral)
        d1.addCallbacks(strip(expunge), self._ebGeneral)
        d1.addCallbacks(expunged, self._ebGeneral)
        d1.addCallbacks(self._cbStopClient, self._ebGeneral)
        d2 = self.loopback()
        d = defer.gatherResults([d1, d2])
        return d.addCallback(self._cbTestExpunge, m)

    def _cbTestExpunge(self, ignored, m):
        self.assertEqual(len(m.messages), 1)
        self.assertEqual(m.messages[0], ('Message 2', ('AnotherFlag',), None, 1))

        self.assertEqual(self.results, [0, 2])



class IMAP4ServerSearchTestCase(IMAP4HelperMixin, unittest.TestCase):
    """
    Tests for the behavior of the search_* functions in L{imap4.IMAP4Server}.
    """
    def setUp(self):
        IMAP4HelperMixin.setUp(self)
        self.earlierQuery = ["10-Dec-2009"]
        self.sameDateQuery = ["13-Dec-2009"]
        self.laterQuery = ["16-Dec-2009"]
        self.seq = 0
        self.msg = FakeyMessage({"date" : "Mon, 13 Dec 2009 21:25:10 GMT"}, [],
                                '', '', 1234, None)


    def test_searchSentBefore(self):
        """
        L{imap4.IMAP4Server.search_SENTBEFORE} returns True if the message date
        is earlier than the query date.
        """
        self.assertFalse(
            self.server.search_SENTBEFORE(self.earlierQuery, self.seq, self.msg))
        self.assertTrue(
            self.server.search_SENTBEFORE(self.laterQuery, self.seq, self.msg))

    def test_searchWildcard(self):
        """
        L{imap4.IMAP4Server.search_UID} returns True if the message UID is in
        the search range.
        """
        self.assertFalse(
            self.server.search_UID(['2:3'], self.seq, self.msg, (1, 1234)))
        # 2:* should get translated to 2:<max UID> and then to 1:2
        self.assertTrue(
            self.server.search_UID(['2:*'], self.seq, self.msg, (1, 1234)))
        self.assertTrue(
            self.server.search_UID(['*'], self.seq, self.msg, (1, 1234)))

    def test_searchWildcardHigh(self):
        """
        L{imap4.IMAP4Server.search_UID} should return True if there is a
        wildcard, because a wildcard means "highest UID in the mailbox".
        """
        self.assertTrue(
            self.server.search_UID(['1235:*'], self.seq, self.msg, (1234, 1)))

    def test_reversedSearchTerms(self):
        """
        L{imap4.IMAP4Server.search_SENTON} returns True if the message date is
        the same as the query date.
        """
        msgset = imap4.parseIdList('4:2')
        self.assertEqual(list(msgset), [2, 3, 4])

    def test_searchSentOn(self):
        """
        L{imap4.IMAP4Server.search_SENTON} returns True if the message date is
        the same as the query date.
        """
        self.assertFalse(
            self.server.search_SENTON(self.earlierQuery, self.seq, self.msg))
        self.assertTrue(
            self.server.search_SENTON(self.sameDateQuery, self.seq, self.msg))
        self.assertFalse(
            self.server.search_SENTON(self.laterQuery, self.seq, self.msg))


    def test_searchSentSince(self):
        """
        L{imap4.IMAP4Server.search_SENTSINCE} returns True if the message date
        is later than the query date.
        """
        self.assertTrue(
            self.server.search_SENTSINCE(self.earlierQuery, self.seq, self.msg))
        self.assertFalse(
            self.server.search_SENTSINCE(self.laterQuery, self.seq, self.msg))


    def test_searchOr(self):
        """
        L{imap4.IMAP4Server.search_OR} returns true if either of the two
        expressions supplied to it returns true and returns false if neither
        does.
        """
        self.assertTrue(
            self.server.search_OR(
                ["SENTSINCE"] + self.earlierQuery +
                ["SENTSINCE"] + self.laterQuery,
            self.seq, self.msg, (None, None)))
        self.assertTrue(
            self.server.search_OR(
                ["SENTSINCE"] + self.laterQuery +
                ["SENTSINCE"] + self.earlierQuery,
            self.seq, self.msg, (None, None)))
        self.assertFalse(
            self.server.search_OR(
                ["SENTON"] + self.laterQuery +
                ["SENTSINCE"] + self.laterQuery,
            self.seq, self.msg, (None, None)))


    def test_searchNot(self):
        """
        L{imap4.IMAP4Server.search_NOT} returns the negation of the result
        of the expression supplied to it.
        """
        self.assertFalse(self.server.search_NOT(
                ["SENTSINCE"] + self.earlierQuery, self.seq, self.msg,
                (None, None)))
        self.assertTrue(self.server.search_NOT(
                ["SENTON"] + self.laterQuery, self.seq, self.msg,
                (None, None)))



class TestRealm:
    theAccount = None

    def requestAvatar(self, avatarId, mind, *interfaces):
        return imap4.IAccount, self.theAccount, lambda: None

class TestChecker:
    credentialInterfaces = (cred.credentials.IUsernameHashedPassword, cred.credentials.IUsernamePassword)

    users = {
        'testuser': 'secret'
    }

    def requestAvatarId(self, credentials):
        if credentials.username in self.users:
            return defer.maybeDeferred(
                credentials.checkPassword, self.users[credentials.username]
        ).addCallback(self._cbCheck, credentials.username)

    def _cbCheck(self, result, username):
        if result:
            return username
        raise cred.error.UnauthorizedLogin()

class AuthenticatorTestCase(IMAP4HelperMixin, unittest.TestCase):
    def setUp(self):
        IMAP4HelperMixin.setUp(self)

        realm = TestRealm()
        realm.theAccount = Account('testuser')
        portal = cred.portal.Portal(realm)
        portal.registerChecker(TestChecker())
        self.server.portal = portal

        self.authenticated = 0
        self.account = realm.theAccount

    def testCramMD5(self):
        self.server.challengers['CRAM-MD5'] = cred.credentials.CramMD5Credentials
        cAuth = imap4.CramMD5ClientAuthenticator('testuser')
        self.client.registerAuthenticator(cAuth)

        def auth():
            return self.client.authenticate('secret')
        def authed():
            self.authenticated = 1

        d1 = self.connected.addCallback(strip(auth))
        d1.addCallbacks(strip(authed), self._ebGeneral)
        d1.addCallbacks(self._cbStopClient, self._ebGeneral)
        d2 = self.loopback()
        d = defer.gatherResults([d1, d2])
        return d.addCallback(self._cbTestCramMD5)

    def _cbTestCramMD5(self, ignored):
        self.assertEqual(self.authenticated, 1)
        self.assertEqual(self.server.account, self.account)

    def testFailedCramMD5(self):
        self.server.challengers['CRAM-MD5'] = cred.credentials.CramMD5Credentials
        cAuth = imap4.CramMD5ClientAuthenticator('testuser')
        self.client.registerAuthenticator(cAuth)

        def misauth():
            return self.client.authenticate('not the secret')
        def authed():
            self.authenticated = 1
        def misauthed():
            self.authenticated = -1

        d1 = self.connected.addCallback(strip(misauth))
        d1.addCallbacks(strip(authed), strip(misauthed))
        d1.addCallbacks(self._cbStopClient, self._ebGeneral)
        d = defer.gatherResults([self.loopback(), d1])
        return d.addCallback(self._cbTestFailedCramMD5)

    def _cbTestFailedCramMD5(self, ignored):
        self.assertEqual(self.authenticated, -1)
        self.assertEqual(self.server.account, None)

    def testLOGIN(self):
        self.server.challengers['LOGIN'] = imap4.LOGINCredentials
        cAuth = imap4.LOGINAuthenticator('testuser')
        self.client.registerAuthenticator(cAuth)

        def auth():
            return self.client.authenticate('secret')
        def authed():
            self.authenticated = 1

        d1 = self.connected.addCallback(strip(auth))
        d1.addCallbacks(strip(authed), self._ebGeneral)
        d1.addCallbacks(self._cbStopClient, self._ebGeneral)
        d = defer.gatherResults([self.loopback(), d1])
        return d.addCallback(self._cbTestLOGIN)

    def _cbTestLOGIN(self, ignored):
        self.assertEqual(self.authenticated, 1)
        self.assertEqual(self.server.account, self.account)

    def testFailedLOGIN(self):
        self.server.challengers['LOGIN'] = imap4.LOGINCredentials
        cAuth = imap4.LOGINAuthenticator('testuser')
        self.client.registerAuthenticator(cAuth)

        def misauth():
            return self.client.authenticate('not the secret')
        def authed():
            self.authenticated = 1
        def misauthed():
            self.authenticated = -1

        d1 = self.connected.addCallback(strip(misauth))
        d1.addCallbacks(strip(authed), strip(misauthed))
        d1.addCallbacks(self._cbStopClient, self._ebGeneral)
        d = defer.gatherResults([self.loopback(), d1])
        return d.addCallback(self._cbTestFailedLOGIN)

    def _cbTestFailedLOGIN(self, ignored):
        self.assertEqual(self.authenticated, -1)
        self.assertEqual(self.server.account, None)

    def testPLAIN(self):
        self.server.challengers['PLAIN'] = imap4.PLAINCredentials
        cAuth = imap4.PLAINAuthenticator('testuser')
        self.client.registerAuthenticator(cAuth)

        def auth():
            return self.client.authenticate('secret')
        def authed():
            self.authenticated = 1

        d1 = self.connected.addCallback(strip(auth))
        d1.addCallbacks(strip(authed), self._ebGeneral)
        d1.addCallbacks(self._cbStopClient, self._ebGeneral)
        d = defer.gatherResults([self.loopback(), d1])
        return d.addCallback(self._cbTestPLAIN)

    def _cbTestPLAIN(self, ignored):
        self.assertEqual(self.authenticated, 1)
        self.assertEqual(self.server.account, self.account)

    def testFailedPLAIN(self):
        self.server.challengers['PLAIN'] = imap4.PLAINCredentials
        cAuth = imap4.PLAINAuthenticator('testuser')
        self.client.registerAuthenticator(cAuth)

        def misauth():
            return self.client.authenticate('not the secret')
        def authed():
            self.authenticated = 1
        def misauthed():
            self.authenticated = -1

        d1 = self.connected.addCallback(strip(misauth))
        d1.addCallbacks(strip(authed), strip(misauthed))
        d1.addCallbacks(self._cbStopClient, self._ebGeneral)
        d = defer.gatherResults([self.loopback(), d1])
        return d.addCallback(self._cbTestFailedPLAIN)

    def _cbTestFailedPLAIN(self, ignored):
        self.assertEqual(self.authenticated, -1)
        self.assertEqual(self.server.account, None)



class SASLPLAINTestCase(unittest.TestCase):
    """
    Tests for I{SASL PLAIN} authentication, as implemented by
    L{imap4.PLAINAuthenticator} and L{imap4.PLAINCredentials}.

    @see: U{http://www.faqs.org/rfcs/rfc2595.html}
    @see: U{http://www.faqs.org/rfcs/rfc4616.html}
    """
    def test_authenticatorChallengeResponse(self):
        """
        L{PLAINAuthenticator.challengeResponse} returns challenge strings of
        the form::

            NUL<authn-id>NUL<secret>
        """
        username = 'testuser'
        secret = 'secret'
        chal = 'challenge'
        cAuth = imap4.PLAINAuthenticator(username)
        response = cAuth.challengeResponse(secret, chal)
        self.assertEqual(response, '\0%s\0%s' % (username, secret))


    def test_credentialsSetResponse(self):
        """
        L{PLAINCredentials.setResponse} parses challenge strings of the
        form::

            NUL<authn-id>NUL<secret>
        """
        cred = imap4.PLAINCredentials()
        cred.setResponse('\0testuser\0secret')
        self.assertEqual(cred.username, 'testuser')
        self.assertEqual(cred.password, 'secret')


    def test_credentialsInvalidResponse(self):
        """
        L{PLAINCredentials.setResponse} raises L{imap4.IllegalClientResponse}
        when passed a string not of the expected form.
        """
        cred = imap4.PLAINCredentials()
        self.assertRaises(
            imap4.IllegalClientResponse, cred.setResponse, 'hello')
        self.assertRaises(
            imap4.IllegalClientResponse, cred.setResponse, 'hello\0world')
        self.assertRaises(
            imap4.IllegalClientResponse, cred.setResponse,
            'hello\0world\0Zoom!\0')



class UnsolicitedResponseTestCase(IMAP4HelperMixin, unittest.TestCase):
    def testReadWrite(self):
        def login():
            return self.client.login('testuser', 'password-test')
        def loggedIn():
            self.server.modeChanged(1)

        d1 = self.connected.addCallback(strip(login))
        d1.addCallback(strip(loggedIn)).addErrback(self._ebGeneral)
        d = defer.gatherResults([self.loopback(), d1])
        return d.addCallback(self._cbTestReadWrite)

    def _cbTestReadWrite(self, ignored):
        E = self.client.events
        self.assertEqual(E, [['modeChanged', 1]])

    def testReadOnly(self):
        def login():
            return self.client.login('testuser', 'password-test')
        def loggedIn():
            self.server.modeChanged(0)

        d1 = self.connected.addCallback(strip(login))
        d1.addCallback(strip(loggedIn)).addErrback(self._ebGeneral)
        d = defer.gatherResults([self.loopback(), d1])
        return d.addCallback(self._cbTestReadOnly)

    def _cbTestReadOnly(self, ignored):
        E = self.client.events
        self.assertEqual(E, [['modeChanged', 0]])

    def testFlagChange(self):
        flags = {
            1: ['\\Answered', '\\Deleted'],
            5: [],
            10: ['\\Recent']
        }
        def login():
            return self.client.login('testuser', 'password-test')
        def loggedIn():
            self.server.flagsChanged(flags)

        d1 = self.connected.addCallback(strip(login))
        d1.addCallback(strip(loggedIn)).addErrback(self._ebGeneral)
        d = defer.gatherResults([self.loopback(), d1])
        return d.addCallback(self._cbTestFlagChange, flags)

    def _cbTestFlagChange(self, ignored, flags):
        E = self.client.events
        expect = [['flagsChanged', {x[0]: x[1]}] for x in flags.items()]
        E.sort()
        expect.sort()
        self.assertEqual(E, expect)

    def testNewMessages(self):
        def login():
            return self.client.login('testuser', 'password-test')
        def loggedIn():
            self.server.newMessages(10, None)

        d1 = self.connected.addCallback(strip(login))
        d1.addCallback(strip(loggedIn)).addErrback(self._ebGeneral)
        d = defer.gatherResults([self.loopback(), d1])
        return d.addCallback(self._cbTestNewMessages)

    def _cbTestNewMessages(self, ignored):
        E = self.client.events
        self.assertEqual(E, [['newMessages', 10, None]])

    def testNewRecentMessages(self):
        def login():
            return self.client.login('testuser', 'password-test')
        def loggedIn():
            self.server.newMessages(None, 10)

        d1 = self.connected.addCallback(strip(login))
        d1.addCallback(strip(loggedIn)).addErrback(self._ebGeneral)
        d = defer.gatherResults([self.loopback(), d1])
        return d.addCallback(self._cbTestNewRecentMessages)

    def _cbTestNewRecentMessages(self, ignored):
        E = self.client.events
        self.assertEqual(E, [['newMessages', None, 10]])

    def testNewMessagesAndRecent(self):
        def login():
            return self.client.login('testuser', 'password-test')
        def loggedIn():
            self.server.newMessages(20, 10)

        d1 = self.connected.addCallback(strip(login))
        d1.addCallback(strip(loggedIn)).addErrback(self._ebGeneral)
        d = defer.gatherResults([self.loopback(), d1])
        return d.addCallback(self._cbTestNewMessagesAndRecent)

    def _cbTestNewMessagesAndRecent(self, ignored):
        E = self.client.events
        self.assertEqual(E, [['newMessages', 20, None], ['newMessages', None, 10]])


class ClientCapabilityTests(unittest.TestCase):
    """
    Tests for issuance of the CAPABILITY command and handling of its response.
    """
    def setUp(self):
        """
        Create an L{imap4.IMAP4Client} connected to a L{StringTransport}.
        """
        self.transport = StringTransport()
        self.protocol = imap4.IMAP4Client()
        self.protocol.makeConnection(self.transport)
        self.protocol.dataReceived('* OK [IMAP4rev1]\r\n')


    def test_simpleAtoms(self):
        """
        A capability response consisting only of atoms without C{'='} in them
        should result in a dict mapping those atoms to C{None}.
        """
        capabilitiesResult = self.protocol.getCapabilities(useCache=False)
        self.protocol.dataReceived('* CAPABILITY IMAP4rev1 LOGINDISABLED\r\n')
        self.protocol.dataReceived('0001 OK Capability completed.\r\n')
        def gotCapabilities(capabilities):
            self.assertEqual(
                capabilities, {'IMAP4rev1': None, 'LOGINDISABLED': None})
        capabilitiesResult.addCallback(gotCapabilities)
        return capabilitiesResult


    def test_categoryAtoms(self):
        """
        A capability response consisting of atoms including C{'='} should have
        those atoms split on that byte and have capabilities in the same
        category aggregated into lists in the resulting dictionary.

        (n.b. - I made up the word "category atom"; the protocol has no notion
        of structure here, but rather allows each capability to define the
        semantics of its entry in the capability response in a freeform manner.
        If I had realized this earlier, the API for capabilities would look
        different.  As it is, we can hope that no one defines any crazy
        semantics which are incompatible with this API, or try to figure out a
        better API when someone does. -exarkun)
        """
        capabilitiesResult = self.protocol.getCapabilities(useCache=False)
        self.protocol.dataReceived('* CAPABILITY IMAP4rev1 AUTH=LOGIN AUTH=PLAIN\r\n')
        self.protocol.dataReceived('0001 OK Capability completed.\r\n')
        def gotCapabilities(capabilities):
            self.assertEqual(
                capabilities, {'IMAP4rev1': None, 'AUTH': ['LOGIN', 'PLAIN']})
        capabilitiesResult.addCallback(gotCapabilities)
        return capabilitiesResult


    def test_mixedAtoms(self):
        """
        A capability response consisting of both simple and category atoms of
        the same type should result in a list containing C{None} as well as the
        values for the category.
        """
        capabilitiesResult = self.protocol.getCapabilities(useCache=False)
        # Exercise codepath for both orderings of =-having and =-missing
        # capabilities.
        self.protocol.dataReceived(
            '* CAPABILITY IMAP4rev1 FOO FOO=BAR BAR=FOO BAR\r\n')
        self.protocol.dataReceived('0001 OK Capability completed.\r\n')
        def gotCapabilities(capabilities):
            self.assertEqual(capabilities, {'IMAP4rev1': None,
                                            'FOO': [None, 'BAR'],
                                            'BAR': ['FOO', None]})
        capabilitiesResult.addCallback(gotCapabilities)
        return capabilitiesResult



class StillSimplerClient(imap4.IMAP4Client):
    """
    An IMAP4 client which keeps track of unsolicited flag changes.
    """
    def __init__(self):
        imap4.IMAP4Client.__init__(self)
        self.flags = {}


    def flagsChanged(self, newFlags):
        self.flags.update(newFlags)



class HandCraftedTestCase(IMAP4HelperMixin, unittest.TestCase):
    def testTrailingLiteral(self):
        transport = StringTransport()
        c = imap4.IMAP4Client()
        c.makeConnection(transport)
        c.lineReceived('* OK [IMAP4rev1]')

        def cbSelect(ignored):
            d = c.fetchMessage('1')
            c.dataReceived('* 1 FETCH (RFC822 {10}\r\n0123456789\r\n RFC822.SIZE 10)\r\n')
            c.dataReceived('0003 OK FETCH\r\n')
            return d

        def cbLogin(ignored):
            d = c.select('inbox')
            c.lineReceived('0002 OK SELECT')
            d.addCallback(cbSelect)
            return d

        d = c.login('blah', 'blah')
        c.dataReceived('0001 OK LOGIN\r\n')
        d.addCallback(cbLogin)
        return d


    def testPathelogicalScatteringOfLiterals(self):
        self.server.checker.addUser('testuser', 'password-test')
        transport = StringTransport()
        self.server.makeConnection(transport)

        transport.clear()
        self.server.dataReceived("01 LOGIN {8}\r\n")
        self.assertEqual(transport.value(), "+ Ready for 8 octets of text\r\n")

        transport.clear()
        self.server.dataReceived("testuser {13}\r\n")
        self.assertEqual(transport.value(), "+ Ready for 13 octets of text\r\n")

        transport.clear()
        self.server.dataReceived("password-test\r\n")
        self.assertEqual(transport.value(), "01 OK LOGIN succeeded\r\n")
        self.assertEqual(self.server.state, 'auth')

        self.server.connectionLost(error.ConnectionDone("Connection done."))


    def test_unsolicitedResponseMixedWithSolicitedResponse(self):
        """
        If unsolicited data is received along with solicited data in the
        response to a I{FETCH} command issued by L{IMAP4Client.fetchSpecific},
        the unsolicited data is passed to the appropriate callback and not
        included in the result with wihch the L{Deferred} returned by
        L{IMAP4Client.fetchSpecific} fires.
        """
        transport = StringTransport()
        c = StillSimplerClient()
        c.makeConnection(transport)
        c.lineReceived('* OK [IMAP4rev1]')

        def login():
            d = c.login('blah', 'blah')
            c.dataReceived('0001 OK LOGIN\r\n')
            return d
        def select():
            d = c.select('inbox')
            c.lineReceived('0002 OK SELECT')
            return d
        def fetch():
            d = c.fetchSpecific('1:*',
                headerType='HEADER.FIELDS',
                headerArgs=['SUBJECT'])
            c.dataReceived('* 1 FETCH (BODY[HEADER.FIELDS ("SUBJECT")] {38}\r\n')
            c.dataReceived('Subject: Suprise for your woman...\r\n')
            c.dataReceived('\r\n')
            c.dataReceived(')\r\n')
            c.dataReceived('* 1 FETCH (FLAGS (\Seen))\r\n')
            c.dataReceived('* 2 FETCH (BODY[HEADER.FIELDS ("SUBJECT")] {75}\r\n')
            c.dataReceived('Subject: What you been doing. Order your meds here . ,. handcuff madsen\r\n')
            c.dataReceived('\r\n')
            c.dataReceived(')\r\n')
            c.dataReceived('0003 OK FETCH completed\r\n')
            return d
        def test(res):
            self.assertEqual(res, {
                1: [['BODY', ['HEADER.FIELDS', ['SUBJECT']],
                    'Subject: Suprise for your woman...\r\n\r\n']],
                2: [['BODY', ['HEADER.FIELDS', ['SUBJECT']],
                    'Subject: What you been doing. Order your meds here . ,. handcuff madsen\r\n\r\n']]
            })

            self.assertEqual(c.flags, {1: ['\\Seen']})

        return login(
            ).addCallback(strip(select)
            ).addCallback(strip(fetch)
            ).addCallback(test)


    def test_literalWithoutPrecedingWhitespace(self):
        """
        Literals should be recognized even when they are not preceded by
        whitespace.
        """
        transport = StringTransport()
        protocol = imap4.IMAP4Client()

        protocol.makeConnection(transport)
        protocol.lineReceived('* OK [IMAP4rev1]')

        def login():
            d = protocol.login('blah', 'blah')
            protocol.dataReceived('0001 OK LOGIN\r\n')
            return d
        def select():
            d = protocol.select('inbox')
            protocol.lineReceived('0002 OK SELECT')
            return d
        def fetch():
            d = protocol.fetchSpecific('1:*',
                headerType='HEADER.FIELDS',
                headerArgs=['SUBJECT'])
            protocol.dataReceived(
                '* 1 FETCH (BODY[HEADER.FIELDS ({7}\r\nSUBJECT)] "Hello")\r\n')
            protocol.dataReceived('0003 OK FETCH completed\r\n')
            return d
        def test(result):
            self.assertEqual(
                result,  {1: [['BODY', ['HEADER.FIELDS', ['SUBJECT']], 'Hello']]})

        d = login()
        d.addCallback(strip(select))
        d.addCallback(strip(fetch))
        d.addCallback(test)
        return d


    def test_nonIntegerLiteralLength(self):
        """
        If the server sends a literal length which cannot be parsed as an
        integer, L{IMAP4Client.lineReceived} should cause the protocol to be
        disconnected by raising L{imap4.IllegalServerResponse}.
        """
        transport = StringTransport()
        protocol = imap4.IMAP4Client()

        protocol.makeConnection(transport)
        protocol.lineReceived('* OK [IMAP4rev1]')

        def login():
            d = protocol.login('blah', 'blah')
            protocol.dataReceived('0001 OK LOGIN\r\n')
            return d
        def select():
            d = protocol.select('inbox')
            protocol.lineReceived('0002 OK SELECT')
            return d
        def fetch():
            d = protocol.fetchSpecific('1:*',
                headerType='HEADER.FIELDS',
                headerArgs=['SUBJECT'])
            self.assertRaises(
                imap4.IllegalServerResponse,
                protocol.dataReceived,
                '* 1 FETCH {xyz}\r\n...')
        d = login()
        d.addCallback(strip(select))
        d.addCallback(strip(fetch))
        return d


    def test_flagsChangedInsideFetchSpecificResponse(self):
        """
        Any unrequested flag information received along with other requested
        information in an untagged I{FETCH} received in response to a request
        issued with L{IMAP4Client.fetchSpecific} is passed to the
        C{flagsChanged} callback.
        """
        transport = StringTransport()
        c = StillSimplerClient()
        c.makeConnection(transport)
        c.lineReceived('* OK [IMAP4rev1]')

        def login():
            d = c.login('blah', 'blah')
            c.dataReceived('0001 OK LOGIN\r\n')
            return d
        def select():
            d = c.select('inbox')
            c.lineReceived('0002 OK SELECT')
            return d
        def fetch():
            d = c.fetchSpecific('1:*',
                headerType='HEADER.FIELDS',
                headerArgs=['SUBJECT'])
            # This response includes FLAGS after the requested data.
            c.dataReceived('* 1 FETCH (BODY[HEADER.FIELDS ("SUBJECT")] {22}\r\n')
            c.dataReceived('Subject: subject one\r\n')
            c.dataReceived(' FLAGS (\\Recent))\r\n')
            # And this one includes it before!  Either is possible.
            c.dataReceived('* 2 FETCH (FLAGS (\\Seen) BODY[HEADER.FIELDS ("SUBJECT")] {22}\r\n')
            c.dataReceived('Subject: subject two\r\n')
            c.dataReceived(')\r\n')
            c.dataReceived('0003 OK FETCH completed\r\n')
            return d

        def test(res):
            self.assertEqual(res, {
                1: [['BODY', ['HEADER.FIELDS', ['SUBJECT']],
                    'Subject: subject one\r\n']],
                2: [['BODY', ['HEADER.FIELDS', ['SUBJECT']],
                    'Subject: subject two\r\n']]
            })

            self.assertEqual(c.flags, {1: ['\\Recent'], 2: ['\\Seen']})

        return login(
            ).addCallback(strip(select)
            ).addCallback(strip(fetch)
            ).addCallback(test)


    def test_flagsChangedInsideFetchMessageResponse(self):
        """
        Any unrequested flag information received along with other requested
        information in an untagged I{FETCH} received in response to a request
        issued with L{IMAP4Client.fetchMessage} is passed to the
        C{flagsChanged} callback.
        """
        transport = StringTransport()
        c = StillSimplerClient()
        c.makeConnection(transport)
        c.lineReceived('* OK [IMAP4rev1]')

        def login():
            d = c.login('blah', 'blah')
            c.dataReceived('0001 OK LOGIN\r\n')
            return d
        def select():
            d = c.select('inbox')
            c.lineReceived('0002 OK SELECT')
            return d
        def fetch():
            d = c.fetchMessage('1:*')
            c.dataReceived('* 1 FETCH (RFC822 {24}\r\n')
            c.dataReceived('Subject: first subject\r\n')
            c.dataReceived(' FLAGS (\Seen))\r\n')
            c.dataReceived('* 2 FETCH (FLAGS (\Recent \Seen) RFC822 {25}\r\n')
            c.dataReceived('Subject: second subject\r\n')
            c.dataReceived(')\r\n')
            c.dataReceived('0003 OK FETCH completed\r\n')
            return d

        def test(res):
            self.assertEqual(res, {
                1: {'RFC822': 'Subject: first subject\r\n'},
                2: {'RFC822': 'Subject: second subject\r\n'}})

            self.assertEqual(
                c.flags, {1: ['\\Seen'], 2: ['\\Recent', '\\Seen']})

        return login(
            ).addCallback(strip(select)
            ).addCallback(strip(fetch)
            ).addCallback(test)


    def test_authenticationChallengeDecodingException(self):
        """
        When decoding a base64 encoded authentication message from the server,
        decoding errors are logged and then the client closes the connection.
        """
        transport = StringTransportWithDisconnection()
        protocol = imap4.IMAP4Client()
        transport.protocol = protocol

        protocol.makeConnection(transport)
        protocol.lineReceived(
            '* OK [CAPABILITY IMAP4rev1 IDLE NAMESPACE AUTH=CRAM-MD5] '
            'Twisted IMAP4rev1 Ready')
        cAuth = imap4.CramMD5ClientAuthenticator('testuser')
        protocol.registerAuthenticator(cAuth)

        d = protocol.authenticate('secret')
        # Should really be something describing the base64 decode error.  See
        # #6021.
        self.assertFailure(d, error.ConnectionDone)

        protocol.dataReceived('+ Something bad! and bad\r\n')

        # This should not really be logged.  See #6021.
        logged = self.flushLoggedErrors(imap4.IllegalServerResponse)
        self.assertEqual(len(logged), 1)
        self.assertEqual(logged[0].value.args[0], "Something bad! and bad")
        return d



class PreauthIMAP4ClientMixin:
    """
    Mixin for L{unittest.TestCase} subclasses which provides a C{setUp} method
    which creates an L{IMAP4Client} connected to a L{StringTransport} and puts
    it into the I{authenticated} state.

    @ivar transport: A L{StringTransport} to which C{client} is connected.
    @ivar client: An L{IMAP4Client} which is connected to C{transport}.
    """
    clientProtocol = imap4.IMAP4Client

    def setUp(self):
        """
        Create an IMAP4Client connected to a fake transport and in the
        authenticated state.
        """
        self.transport = StringTransport()
        self.client = self.clientProtocol()
        self.client.makeConnection(self.transport)
        self.client.dataReceived('* PREAUTH Hello unittest\r\n')


    def _extractDeferredResult(self, d):
        """
        Synchronously extract the result of the given L{Deferred}.  Fail the
        test if that is not possible.
        """
        result = []
        error = []
        d.addCallbacks(result.append, error.append)
        if result:
            return result[0]
        elif error:
            error[0].raiseException()
        else:
            self.fail("Expected result not available")



class SelectionTestsMixin(PreauthIMAP4ClientMixin):
    """
    Mixin for test cases which defines tests which apply to both I{EXAMINE} and
    I{SELECT} support.
    """
    def _examineOrSelect(self):
        """
        Issue either an I{EXAMINE} or I{SELECT} command (depending on
        C{self.method}), assert that the correct bytes are written to the
        transport, and return the L{Deferred} returned by whichever method was
        called.
        """
        d = getattr(self.client, self.method)('foobox')
        self.assertEqual(
            self.transport.value(), '0001 %s foobox\r\n' % (self.command,))
        return d


    def _response(self, *lines):
        """
        Deliver the given (unterminated) response lines to C{self.client} and
        then deliver a tagged SELECT or EXAMINE completion line to finish the
        SELECT or EXAMINE response.
        """
        for line in lines:
            self.client.dataReceived(line + '\r\n')
        self.client.dataReceived(
            '0001 OK [READ-ONLY] %s completed\r\n' % (self.command,))


    def test_exists(self):
        """
        If the server response to a I{SELECT} or I{EXAMINE} command includes an
        I{EXISTS} response, the L{Deferred} return by L{IMAP4Client.select} or
        L{IMAP4Client.examine} fires with a C{dict} including the value
        associated with the C{'EXISTS'} key.
        """
        d = self._examineOrSelect()
        self._response('* 3 EXISTS')
        self.assertEqual(
            self._extractDeferredResult(d),
            {'READ-WRITE': False, 'EXISTS': 3})


    def test_nonIntegerExists(self):
        """
        If the server returns a non-integer EXISTS value in its response to a
        I{SELECT} or I{EXAMINE} command, the L{Deferred} returned by
        L{IMAP4Client.select} or L{IMAP4Client.examine} fails with
        L{IllegalServerResponse}.
        """
        d = self._examineOrSelect()
        self._response('* foo EXISTS')
        self.assertRaises(
            imap4.IllegalServerResponse, self._extractDeferredResult, d)


    def test_recent(self):
        """
        If the server response to a I{SELECT} or I{EXAMINE} command includes an
        I{RECENT} response, the L{Deferred} return by L{IMAP4Client.select} or
        L{IMAP4Client.examine} fires with a C{dict} including the value
        associated with the C{'RECENT'} key.
        """
        d = self._examineOrSelect()
        self._response('* 5 RECENT')
        self.assertEqual(
            self._extractDeferredResult(d),
            {'READ-WRITE': False, 'RECENT': 5})


    def test_nonIntegerRecent(self):
        """
        If the server returns a non-integer RECENT value in its response to a
        I{SELECT} or I{EXAMINE} command, the L{Deferred} returned by
        L{IMAP4Client.select} or L{IMAP4Client.examine} fails with
        L{IllegalServerResponse}.
        """
        d = self._examineOrSelect()
        self._response('* foo RECENT')
        self.assertRaises(
            imap4.IllegalServerResponse, self._extractDeferredResult, d)


    def test_unseen(self):
        """
        If the server response to a I{SELECT} or I{EXAMINE} command includes an
        I{UNSEEN} response, the L{Deferred} returned by L{IMAP4Client.select} or
        L{IMAP4Client.examine} fires with a C{dict} including the value
        associated with the C{'UNSEEN'} key.
        """
        d = self._examineOrSelect()
        self._response('* OK [UNSEEN 8] Message 8 is first unseen')
        self.assertEqual(
            self._extractDeferredResult(d),
            {'READ-WRITE': False, 'UNSEEN': 8})


    def test_nonIntegerUnseen(self):
        """
        If the server returns a non-integer UNSEEN value in its response to a
        I{SELECT} or I{EXAMINE} command, the L{Deferred} returned by
        L{IMAP4Client.select} or L{IMAP4Client.examine} fails with
        L{IllegalServerResponse}.
        """
        d = self._examineOrSelect()
        self._response('* OK [UNSEEN foo] Message foo is first unseen')
        self.assertRaises(
            imap4.IllegalServerResponse, self._extractDeferredResult, d)


    def test_uidvalidity(self):
        """
        If the server response to a I{SELECT} or I{EXAMINE} command includes an
        I{UIDVALIDITY} response, the L{Deferred} returned by
        L{IMAP4Client.select} or L{IMAP4Client.examine} fires with a C{dict}
        including the value associated with the C{'UIDVALIDITY'} key.
        """
        d = self._examineOrSelect()
        self._response('* OK [UIDVALIDITY 12345] UIDs valid')
        self.assertEqual(
            self._extractDeferredResult(d),
            {'READ-WRITE': False, 'UIDVALIDITY': 12345})


    def test_nonIntegerUIDVALIDITY(self):
        """
        If the server returns a non-integer UIDVALIDITY value in its response to
        a I{SELECT} or I{EXAMINE} command, the L{Deferred} returned by
        L{IMAP4Client.select} or L{IMAP4Client.examine} fails with
        L{IllegalServerResponse}.
        """
        d = self._examineOrSelect()
        self._response('* OK [UIDVALIDITY foo] UIDs valid')
        self.assertRaises(
            imap4.IllegalServerResponse, self._extractDeferredResult, d)


    def test_uidnext(self):
        """
        If the server response to a I{SELECT} or I{EXAMINE} command includes an
        I{UIDNEXT} response, the L{Deferred} returned by L{IMAP4Client.select}
        or L{IMAP4Client.examine} fires with a C{dict} including the value
        associated with the C{'UIDNEXT'} key.
        """
        d = self._examineOrSelect()
        self._response('* OK [UIDNEXT 4392] Predicted next UID')
        self.assertEqual(
            self._extractDeferredResult(d),
            {'READ-WRITE': False, 'UIDNEXT': 4392})


    def test_nonIntegerUIDNEXT(self):
        """
        If the server returns a non-integer UIDNEXT value in its response to a
        I{SELECT} or I{EXAMINE} command, the L{Deferred} returned by
        L{IMAP4Client.select} or L{IMAP4Client.examine} fails with
        L{IllegalServerResponse}.
        """
        d = self._examineOrSelect()
        self._response('* OK [UIDNEXT foo] Predicted next UID')
        self.assertRaises(
            imap4.IllegalServerResponse, self._extractDeferredResult, d)


    def test_flags(self):
        """
        If the server response to a I{SELECT} or I{EXAMINE} command includes an
        I{FLAGS} response, the L{Deferred} returned by L{IMAP4Client.select} or
        L{IMAP4Client.examine} fires with a C{dict} including the value
        associated with the C{'FLAGS'} key.
        """
        d = self._examineOrSelect()
        self._response(
            '* FLAGS (\\Answered \\Flagged \\Deleted \\Seen \\Draft)')
        self.assertEqual(
            self._extractDeferredResult(d), {
                'READ-WRITE': False,
                'FLAGS': ('\\Answered', '\\Flagged', '\\Deleted', '\\Seen',
                          '\\Draft')})


    def test_permanentflags(self):
        """
        If the server response to a I{SELECT} or I{EXAMINE} command includes an
        I{FLAGS} response, the L{Deferred} returned by L{IMAP4Client.select} or
        L{IMAP4Client.examine} fires with a C{dict} including the value
        associated with the C{'FLAGS'} key.
        """
        d = self._examineOrSelect()
        self._response(
            '* OK [PERMANENTFLAGS (\\Starred)] Just one permanent flag in '
            'that list up there')
        self.assertEqual(
            self._extractDeferredResult(d), {
                'READ-WRITE': False,
                'PERMANENTFLAGS': ('\\Starred',)})


    def test_unrecognizedOk(self):
        """
        If the server response to a I{SELECT} or I{EXAMINE} command includes an
        I{OK} with unrecognized response code text, parsing does not fail.
        """
        d = self._examineOrSelect()
        self._response(
            '* OK [X-MADE-UP] I just made this response text up.')
        # The value won't show up in the result.  It would be okay if it did
        # someday, perhaps.  This shouldn't ever happen, though.
        self.assertEqual(
            self._extractDeferredResult(d), {'READ-WRITE': False})


    def test_bareOk(self):
        """
        If the server response to a I{SELECT} or I{EXAMINE} command includes an
        I{OK} with no response code text, parsing does not fail.
        """
        d = self._examineOrSelect()
        self._response('* OK')
        self.assertEqual(
            self._extractDeferredResult(d), {'READ-WRITE': False})



class IMAP4ClientExamineTests(SelectionTestsMixin, unittest.TestCase):
    """
    Tests for the L{IMAP4Client.examine} method.

    An example of usage of the EXAMINE command from RFC 3501, section 6.3.2::

        S: * 17 EXISTS
        S: * 2 RECENT
        S: * OK [UNSEEN 8] Message 8 is first unseen
        S: * OK [UIDVALIDITY 3857529045] UIDs valid
        S: * OK [UIDNEXT 4392] Predicted next UID
        S: * FLAGS (\\Answered \\Flagged \\Deleted \\Seen \\Draft)
        S: * OK [PERMANENTFLAGS ()] No permanent flags permitted
        S: A932 OK [READ-ONLY] EXAMINE completed
    """
    method = 'examine'
    command = 'EXAMINE'




class IMAP4ClientSelectTests(SelectionTestsMixin, unittest.TestCase):
    """
    Tests for the L{IMAP4Client.select} method.

    An example of usage of the SELECT command from RFC 3501, section 6.3.1::

        C: A142 SELECT INBOX
        S: * 172 EXISTS
        S: * 1 RECENT
        S: * OK [UNSEEN 12] Message 12 is first unseen
        S: * OK [UIDVALIDITY 3857529045] UIDs valid
        S: * OK [UIDNEXT 4392] Predicted next UID
        S: * FLAGS (\Answered \Flagged \Deleted \Seen \Draft)
        S: * OK [PERMANENTFLAGS (\Deleted \Seen \*)] Limited
        S: A142 OK [READ-WRITE] SELECT completed
    """
    method = 'select'
    command = 'SELECT'



class IMAP4ClientExpungeTests(PreauthIMAP4ClientMixin, unittest.TestCase):
    """
    Tests for the L{IMAP4Client.expunge} method.

    An example of usage of the EXPUNGE command from RFC 3501, section 6.4.3::

        C: A202 EXPUNGE
        S: * 3 EXPUNGE
        S: * 3 EXPUNGE
        S: * 5 EXPUNGE
        S: * 8 EXPUNGE
        S: A202 OK EXPUNGE completed
    """
    def _expunge(self):
        d = self.client.expunge()
        self.assertEqual(self.transport.value(), '0001 EXPUNGE\r\n')
        self.transport.clear()
        return d


    def _response(self, sequenceNumbers):
        for number in sequenceNumbers:
            self.client.lineReceived('* %s EXPUNGE' % (number,))
        self.client.lineReceived('0001 OK EXPUNGE COMPLETED')


    def test_expunge(self):
        """
        L{IMAP4Client.expunge} sends the I{EXPUNGE} command and returns a
        L{Deferred} which fires with a C{list} of message sequence numbers
        given by the server's response.
        """
        d = self._expunge()
        self._response([3, 3, 5, 8])
        self.assertEqual(self._extractDeferredResult(d), [3, 3, 5, 8])


    def test_nonIntegerExpunged(self):
        """
        If the server responds with a non-integer where a message sequence
        number is expected, the L{Deferred} returned by L{IMAP4Client.expunge}
        fails with L{IllegalServerResponse}.
        """
        d = self._expunge()
        self._response([3, 3, 'foo', 8])
        self.assertRaises(
            imap4.IllegalServerResponse, self._extractDeferredResult, d)



class IMAP4ClientSearchTests(PreauthIMAP4ClientMixin, unittest.TestCase):
    """
    Tests for the L{IMAP4Client.search} method.

    An example of usage of the SEARCH command from RFC 3501, section 6.4.4::

        C: A282 SEARCH FLAGGED SINCE 1-Feb-1994 NOT FROM "Smith"
        S: * SEARCH 2 84 882
        S: A282 OK SEARCH completed
        C: A283 SEARCH TEXT "string not in mailbox"
        S: * SEARCH
        S: A283 OK SEARCH completed
        C: A284 SEARCH CHARSET UTF-8 TEXT {6}
        C: XXXXXX
        S: * SEARCH 43
        S: A284 OK SEARCH completed
    """
    def _search(self):
        d = self.client.search(imap4.Query(text="ABCDEF"))
        self.assertEqual(
            self.transport.value(), '0001 SEARCH (TEXT "ABCDEF")\r\n')
        return d


    def _response(self, messageNumbers):
        self.client.lineReceived(
            "* SEARCH " + " ".join(map(str, messageNumbers)))
        self.client.lineReceived("0001 OK SEARCH completed")


    def test_search(self):
        """
        L{IMAP4Client.search} sends the I{SEARCH} command and returns a
        L{Deferred} which fires with a C{list} of message sequence numbers
        given by the server's response.
        """
        d = self._search()
        self._response([2, 5, 10])
        self.assertEqual(self._extractDeferredResult(d), [2, 5, 10])


    def test_nonIntegerFound(self):
        """
        If the server responds with a non-integer where a message sequence
        number is expected, the L{Deferred} returned by L{IMAP4Client.search}
        fails with L{IllegalServerResponse}.
        """
        d = self._search()
        self._response([2, "foo", 10])
        self.assertRaises(
            imap4.IllegalServerResponse, self._extractDeferredResult, d)



class IMAP4ClientFetchTests(PreauthIMAP4ClientMixin, unittest.TestCase):
    """
    Tests for the L{IMAP4Client.fetch} method.

    See RFC 3501, section 6.4.5.
    """
    def test_fetchUID(self):
        """
        L{IMAP4Client.fetchUID} sends the I{FETCH UID} command and returns a
        L{Deferred} which fires with a C{dict} mapping message sequence numbers
        to C{dict}s mapping C{'UID'} to that message's I{UID} in the server's
        response.
        """
        d = self.client.fetchUID('1:7')
        self.assertEqual(self.transport.value(), '0001 FETCH 1:7 (UID)\r\n')
        self.client.lineReceived('* 2 FETCH (UID 22)')
        self.client.lineReceived('* 3 FETCH (UID 23)')
        self.client.lineReceived('* 4 FETCH (UID 24)')
        self.client.lineReceived('* 5 FETCH (UID 25)')
        self.client.lineReceived('0001 OK FETCH completed')
        self.assertEqual(
            self._extractDeferredResult(d), {
                2: {'UID': '22'},
                3: {'UID': '23'},
                4: {'UID': '24'},
                5: {'UID': '25'}})


    def test_fetchUIDNonIntegerFound(self):
        """
        If the server responds with a non-integer where a message sequence
        number is expected, the L{Deferred} returned by L{IMAP4Client.fetchUID}
        fails with L{IllegalServerResponse}.
        """
        d = self.client.fetchUID('1')
        self.assertEqual(self.transport.value(), '0001 FETCH 1 (UID)\r\n')
        self.client.lineReceived('* foo FETCH (UID 22)')
        self.client.lineReceived('0001 OK FETCH completed')
        self.assertRaises(
            imap4.IllegalServerResponse, self._extractDeferredResult, d)


    def test_incompleteFetchUIDResponse(self):
        """
        If the server responds with an incomplete I{FETCH} response line, the
        L{Deferred} returned by L{IMAP4Client.fetchUID} fails with
        L{IllegalServerResponse}.
        """
        d = self.client.fetchUID('1:7')
        self.assertEqual(self.transport.value(), '0001 FETCH 1:7 (UID)\r\n')
        self.client.lineReceived('* 2 FETCH (UID 22)')
        self.client.lineReceived('* 3 FETCH (UID)')
        self.client.lineReceived('* 4 FETCH (UID 24)')
        self.client.lineReceived('0001 OK FETCH completed')
        self.assertRaises(
            imap4.IllegalServerResponse, self._extractDeferredResult, d)


    def test_fetchBody(self):
        """
        L{IMAP4Client.fetchBody} sends the I{FETCH BODY} command and returns a
        L{Deferred} which fires with a C{dict} mapping message sequence numbers
        to C{dict}s mapping C{'RFC822.TEXT'} to that message's body as given in
        the server's response.
        """
        d = self.client.fetchBody('3')
        self.assertEqual(
            self.transport.value(), '0001 FETCH 3 (RFC822.TEXT)\r\n')
        self.client.lineReceived('* 3 FETCH (RFC822.TEXT "Message text")')
        self.client.lineReceived('0001 OK FETCH completed')
        self.assertEqual(
            self._extractDeferredResult(d),
            {3: {'RFC822.TEXT': 'Message text'}})


    def test_fetchSpecific(self):
        """
        L{IMAP4Client.fetchSpecific} sends the I{BODY[]} command if no
        parameters beyond the message set to retrieve are given.  It returns a
        L{Deferred} which fires with a C{dict} mapping message sequence numbers
        to C{list}s of corresponding message data given by the server's
        response.
        """
        d = self.client.fetchSpecific('7')
        self.assertEqual(
            self.transport.value(), '0001 FETCH 7 BODY[]\r\n')
        self.client.lineReceived('* 7 FETCH (BODY[] "Some body")')
        self.client.lineReceived('0001 OK FETCH completed')
        self.assertEqual(
            self._extractDeferredResult(d), {7: [['BODY', [], "Some body"]]})


    def test_fetchSpecificPeek(self):
        """
        L{IMAP4Client.fetchSpecific} issues a I{BODY.PEEK[]} command if passed
        C{True} for the C{peek} parameter.
        """
        d = self.client.fetchSpecific('6', peek=True)
        self.assertEqual(
            self.transport.value(), '0001 FETCH 6 BODY.PEEK[]\r\n')
        # BODY.PEEK responses are just BODY
        self.client.lineReceived('* 6 FETCH (BODY[] "Some body")')
        self.client.lineReceived('0001 OK FETCH completed')
        self.assertEqual(
            self._extractDeferredResult(d), {6: [['BODY', [], "Some body"]]})


    def test_fetchSpecificNumbered(self):
        """
        L{IMAP4Client.fetchSpecific}, when passed a sequence for for
        C{headerNumber}, sends the I{BODY[N.M]} command.  It returns a
        L{Deferred} which fires with a C{dict} mapping message sequence numbers
        to C{list}s of corresponding message data given by the server's
        response.
        """
        d = self.client.fetchSpecific('7', headerNumber=(1, 2, 3))
        self.assertEqual(
            self.transport.value(), '0001 FETCH 7 BODY[1.2.3]\r\n')
        self.client.lineReceived('* 7 FETCH (BODY[1.2.3] "Some body")')
        self.client.lineReceived('0001 OK FETCH completed')
        self.assertEqual(
            self._extractDeferredResult(d),
            {7: [['BODY', ['1.2.3'], "Some body"]]})


    def test_fetchSpecificText(self):
        """
        L{IMAP4Client.fetchSpecific}, when passed C{'TEXT'} for C{headerType},
        sends the I{BODY[TEXT]} command.  It returns a L{Deferred} which fires
        with a C{dict} mapping message sequence numbers to C{list}s of
        corresponding message data given by the server's response.
        """
        d = self.client.fetchSpecific('8', headerType='TEXT')
        self.assertEqual(
            self.transport.value(), '0001 FETCH 8 BODY[TEXT]\r\n')
        self.client.lineReceived('* 8 FETCH (BODY[TEXT] "Some body")')
        self.client.lineReceived('0001 OK FETCH completed')
        self.assertEqual(
            self._extractDeferredResult(d),
            {8: [['BODY', ['TEXT'], "Some body"]]})


    def test_fetchSpecificNumberedText(self):
        """
        If passed a value for the C{headerNumber} parameter and C{'TEXT'} for
        the C{headerType} parameter, L{IMAP4Client.fetchSpecific} sends a
        I{BODY[number.TEXT]} request and returns a L{Deferred} which fires with
        a C{dict} mapping message sequence numbers to C{list}s of message data
        given by the server's response.
        """
        d = self.client.fetchSpecific('4', headerType='TEXT', headerNumber=7)
        self.assertEqual(
            self.transport.value(), '0001 FETCH 4 BODY[7.TEXT]\r\n')
        self.client.lineReceived('* 4 FETCH (BODY[7.TEXT] "Some body")')
        self.client.lineReceived('0001 OK FETCH completed')
        self.assertEqual(
            self._extractDeferredResult(d),
            {4: [['BODY', ['7.TEXT'], "Some body"]]})


    def test_incompleteFetchSpecificTextResponse(self):
        """
        If the server responds to a I{BODY[TEXT]} request with a I{FETCH} line
        which is truncated after the I{BODY[TEXT]} tokens, the L{Deferred}
        returned by L{IMAP4Client.fetchUID} fails with
        L{IllegalServerResponse}.
        """
        d = self.client.fetchSpecific('8', headerType='TEXT')
        self.assertEqual(
            self.transport.value(), '0001 FETCH 8 BODY[TEXT]\r\n')
        self.client.lineReceived('* 8 FETCH (BODY[TEXT])')
        self.client.lineReceived('0001 OK FETCH completed')
        self.assertRaises(
            imap4.IllegalServerResponse, self._extractDeferredResult, d)


    def test_fetchSpecificMIME(self):
        """
        L{IMAP4Client.fetchSpecific}, when passed C{'MIME'} for C{headerType},
        sends the I{BODY[MIME]} command.  It returns a L{Deferred} which fires
        with a C{dict} mapping message sequence numbers to C{list}s of
        corresponding message data given by the server's response.
        """
        d = self.client.fetchSpecific('8', headerType='MIME')
        self.assertEqual(
            self.transport.value(), '0001 FETCH 8 BODY[MIME]\r\n')
        self.client.lineReceived('* 8 FETCH (BODY[MIME] "Some body")')
        self.client.lineReceived('0001 OK FETCH completed')
        self.assertEqual(
            self._extractDeferredResult(d),
            {8: [['BODY', ['MIME'], "Some body"]]})


    def test_fetchSpecificPartial(self):
        """
        L{IMAP4Client.fetchSpecific}, when passed C{offset} and C{length},
        sends a partial content request (like I{BODY[TEXT]<offset.length>}).
        It returns a L{Deferred} which fires with a C{dict} mapping message
        sequence numbers to C{list}s of corresponding message data given by the
        server's response.
        """
        d = self.client.fetchSpecific(
            '9', headerType='TEXT', offset=17, length=3)
        self.assertEqual(
            self.transport.value(), '0001 FETCH 9 BODY[TEXT]<17.3>\r\n')
        self.client.lineReceived('* 9 FETCH (BODY[TEXT]<17> "foo")')
        self.client.lineReceived('0001 OK FETCH completed')
        self.assertEqual(
            self._extractDeferredResult(d),
            {9: [['BODY', ['TEXT'], '<17>', 'foo']]})


    def test_incompleteFetchSpecificPartialResponse(self):
        """
        If the server responds to a I{BODY[TEXT]} request with a I{FETCH} line
        which is truncated after the I{BODY[TEXT]<offset>} tokens, the
        L{Deferred} returned by L{IMAP4Client.fetchUID} fails with
        L{IllegalServerResponse}.
        """
        d = self.client.fetchSpecific('8', headerType='TEXT')
        self.assertEqual(
            self.transport.value(), '0001 FETCH 8 BODY[TEXT]\r\n')
        self.client.lineReceived('* 8 FETCH (BODY[TEXT]<17>)')
        self.client.lineReceived('0001 OK FETCH completed')
        self.assertRaises(
            imap4.IllegalServerResponse, self._extractDeferredResult, d)


    def test_fetchSpecificHTML(self):
        """
        If the body of a message begins with I{<} and ends with I{>} (as,
        for example, HTML bodies typically will), this is still interpreted
        as the body by L{IMAP4Client.fetchSpecific} (and particularly, not
        as a length indicator for a response to a request for a partial
        body).
        """
        d = self.client.fetchSpecific('7')
        self.assertEqual(
            self.transport.value(), '0001 FETCH 7 BODY[]\r\n')
        self.client.lineReceived('* 7 FETCH (BODY[] "<html>test</html>")')
        self.client.lineReceived('0001 OK FETCH completed')
        self.assertEqual(
            self._extractDeferredResult(d), {7: [['BODY', [], "<html>test</html>"]]})



class IMAP4ClientStoreTests(PreauthIMAP4ClientMixin, unittest.TestCase):
    """
    Tests for the L{IMAP4Client.setFlags}, L{IMAP4Client.addFlags}, and
    L{IMAP4Client.removeFlags} methods.

    An example of usage of the STORE command, in terms of which these three
    methods are implemented, from RFC 3501, section 6.4.6::

        C: A003 STORE 2:4 +FLAGS (\Deleted)
        S: * 2 FETCH (FLAGS (\Deleted \Seen))
        S: * 3 FETCH (FLAGS (\Deleted))
        S: * 4 FETCH (FLAGS (\Deleted \Flagged \Seen))
        S: A003 OK STORE completed
    """
    clientProtocol = StillSimplerClient

    def _flagsTest(self, method, item):
        """
        Test a non-silent flag modifying method.  Call the method, assert that
        the correct bytes are sent, deliver a I{FETCH} response, and assert
        that the result of the Deferred returned by the method is correct.

        @param method: The name of the method to test.
        @param item: The data item which is expected to be specified.
        """
        d = getattr(self.client, method)('3', ('\\Read', '\\Seen'), False)
        self.assertEqual(
            self.transport.value(),
            '0001 STORE 3 ' + item + ' (\\Read \\Seen)\r\n')
        self.client.lineReceived('* 3 FETCH (FLAGS (\\Read \\Seen))')
        self.client.lineReceived('0001 OK STORE completed')
        self.assertEqual(
            self._extractDeferredResult(d),
            {3: {'FLAGS': ['\\Read', '\\Seen']}})


    def _flagsSilentlyTest(self, method, item):
        """
        Test a silent flag modifying method.  Call the method, assert that the
        correct bytes are sent, deliver an I{OK} response, and assert that the
        result of the Deferred returned by the method is correct.

        @param method: The name of the method to test.
        @param item: The data item which is expected to be specified.
        """
        d = getattr(self.client, method)('3', ('\\Read', '\\Seen'), True)
        self.assertEqual(
            self.transport.value(),
            '0001 STORE 3 ' + item + ' (\\Read \\Seen)\r\n')
        self.client.lineReceived('0001 OK STORE completed')
        self.assertEqual(self._extractDeferredResult(d), {})


    def _flagsSilentlyWithUnsolicitedDataTest(self, method, item):
        """
        Test unsolicited data received in response to a silent flag modifying
        method.  Call the method, assert that the correct bytes are sent,
        deliver the unsolicited I{FETCH} response, and assert that the result
        of the Deferred returned by the method is correct.

        @param method: The name of the method to test.
        @param item: The data item which is expected to be specified.
        """
        d = getattr(self.client, method)('3', ('\\Read', '\\Seen'), True)
        self.assertEqual(
            self.transport.value(),
            '0001 STORE 3 ' + item + ' (\\Read \\Seen)\r\n')
        self.client.lineReceived('* 2 FETCH (FLAGS (\\Read \\Seen))')
        self.client.lineReceived('0001 OK STORE completed')
        self.assertEqual(self._extractDeferredResult(d), {})
        self.assertEqual(self.client.flags, {2: ['\\Read', '\\Seen']})


    def test_setFlags(self):
        """
        When passed a C{False} value for the C{silent} parameter,
        L{IMAP4Client.setFlags} sends the I{STORE} command with a I{FLAGS} data
        item and returns a L{Deferred} which fires with a C{dict} mapping
        message sequence numbers to C{dict}s mapping C{'FLAGS'} to the new
        flags of those messages.
        """
        self._flagsTest('setFlags', 'FLAGS')


    def test_setFlagsSilently(self):
        """
        When passed a C{True} value for the C{silent} parameter,
        L{IMAP4Client.setFlags} sends the I{STORE} command with a
        I{FLAGS.SILENT} data item and returns a L{Deferred} which fires with an
        empty dictionary.
        """
        self._flagsSilentlyTest('setFlags', 'FLAGS.SILENT')


    def test_setFlagsSilentlyWithUnsolicitedData(self):
        """
        If unsolicited flag data is received in response to a I{STORE}
        I{FLAGS.SILENT} request, that data is passed to the C{flagsChanged}
        callback.
        """
        self._flagsSilentlyWithUnsolicitedDataTest('setFlags', 'FLAGS.SILENT')


    def test_addFlags(self):
        """
        L{IMAP4Client.addFlags} is like L{IMAP4Client.setFlags}, but sends
        I{+FLAGS} instead of I{FLAGS}.
        """
        self._flagsTest('addFlags', '+FLAGS')


    def test_addFlagsSilently(self):
        """
        L{IMAP4Client.addFlags} with a C{True} value for C{silent} behaves like
        L{IMAP4Client.setFlags} with a C{True} value for C{silent}, but it
        sends I{+FLAGS.SILENT} instead of I{FLAGS.SILENT}.
        """
        self._flagsSilentlyTest('addFlags', '+FLAGS.SILENT')


    def test_addFlagsSilentlyWithUnsolicitedData(self):
        """
        L{IMAP4Client.addFlags} behaves like L{IMAP4Client.setFlags} when used
        in silent mode and unsolicited data is received.
        """
        self._flagsSilentlyWithUnsolicitedDataTest('addFlags', '+FLAGS.SILENT')


    def test_removeFlags(self):
        """
        L{IMAP4Client.removeFlags} is like L{IMAP4Client.setFlags}, but sends
        I{-FLAGS} instead of I{FLAGS}.
        """
        self._flagsTest('removeFlags', '-FLAGS')


    def test_removeFlagsSilently(self):
        """
        L{IMAP4Client.removeFlags} with a C{True} value for C{silent} behaves
        like L{IMAP4Client.setFlags} with a C{True} value for C{silent}, but it
        sends I{-FLAGS.SILENT} instead of I{FLAGS.SILENT}.
        """
        self._flagsSilentlyTest('removeFlags', '-FLAGS.SILENT')


    def test_removeFlagsSilentlyWithUnsolicitedData(self):
        """
        L{IMAP4Client.removeFlags} behaves like L{IMAP4Client.setFlags} when
        used in silent mode and unsolicited data is received.
        """
        self._flagsSilentlyWithUnsolicitedDataTest('removeFlags', '-FLAGS.SILENT')



class FakeyServer(imap4.IMAP4Server):
    state = 'select'
    timeout = None

    def sendServerGreeting(self):
        pass

class FakeyMessage(util.FancyStrMixin):
    implements(imap4.IMessage)

    showAttributes = ('headers', 'flags', 'date', 'body', 'uid')

    def __init__(self, headers, flags, date, body, uid, subpart):
        self.headers = headers
        self.flags = flags
        self._body = body
        self.size = len(body)
        self.date = date
        self.uid = uid
        self.subpart = subpart

    def getHeaders(self, negate, *names):
        self.got_headers = negate, names
        return self.headers

    def getFlags(self):
        return self.flags

    def getInternalDate(self):
        return self.date

    def getBodyFile(self):
        return StringIO(self._body)

    def getSize(self):
        return self.size

    def getUID(self):
        return self.uid

    def isMultipart(self):
        return self.subpart is not None

    def getSubPart(self, part):
        self.got_subpart = part
        return self.subpart[part]

class NewStoreTestCase(unittest.TestCase, IMAP4HelperMixin):
    result = None
    storeArgs = None

    def setUp(self):
        self.received_messages = self.received_uid = None

        self.server = imap4.IMAP4Server()
        self.server.state = 'select'
        self.server.mbox = self
        self.connected = defer.Deferred()
        self.client = SimpleClient(self.connected)

    def addListener(self, x):
        pass
    def removeListener(self, x):
        pass

    def store(self, *args, **kw):
        self.storeArgs = args, kw
        return self.response

    def _storeWork(self):
        def connected():
            return self.function(self.messages, self.flags, self.silent, self.uid)
        def result(R):
            self.result = R

        self.connected.addCallback(strip(connected)
        ).addCallback(result
        ).addCallback(self._cbStopClient
        ).addErrback(self._ebGeneral)

        def check(ignored):
            self.assertEqual(self.result, self.expected)
            self.assertEqual(self.storeArgs, self.expectedArgs)
        d = loopback.loopbackTCP(self.server, self.client, noisy=False)
        d.addCallback(check)
        return d

    def testSetFlags(self, uid=0):
        self.function = self.client.setFlags
        self.messages = '1,5,9'
        self.flags = ['\\A', '\\B', 'C']
        self.silent = False
        self.uid = uid
        self.response = {
            1: ['\\A', '\\B', 'C'],
            5: ['\\A', '\\B', 'C'],
            9: ['\\A', '\\B', 'C'],
        }
        self.expected = {
            1: {'FLAGS': ['\\A', '\\B', 'C']},
            5: {'FLAGS': ['\\A', '\\B', 'C']},
            9: {'FLAGS': ['\\A', '\\B', 'C']},
        }
        msg = imap4.MessageSet()
        msg.add(1)
        msg.add(5)
        msg.add(9)
        self.expectedArgs = ((msg, ['\\A', '\\B', 'C'], 0), {'uid': 0})
        return self._storeWork()



class GetBodyStructureTests(unittest.TestCase):
    """
    Tests for L{imap4.getBodyStructure}, a helper for constructing a list which
    directly corresponds to the wire information needed for a I{BODY} or
    I{BODYSTRUCTURE} response.
    """
    def test_singlePart(self):
        """
        L{imap4.getBodyStructure} accepts a L{IMessagePart} provider and returns
        a list giving the basic fields for the I{BODY} response for that
        message.
        """
        body = 'hello, world'
        major = 'image'
        minor = 'jpeg'
        charset = 'us-ascii'
        identifier = 'some kind of id'
        description = 'great justice'
        encoding = 'maximum'
        msg = FakeyMessage({
                'content-type': '%s/%s; charset=%s; x=y' % (
                    major, minor, charset),
                'content-id': identifier,
                'content-description': description,
                'content-transfer-encoding': encoding,
                }, (), '', body, 123, None)
        structure = imap4.getBodyStructure(msg)
        self.assertEqual(
            [major, minor, ["charset", charset, 'x', 'y'], identifier,
             description, encoding, len(body)],
            structure)


    def test_singlePartExtended(self):
        """
        L{imap4.getBodyStructure} returns a list giving the basic and extended
        fields for a I{BODYSTRUCTURE} response if passed C{True} for the
        C{extended} parameter.
        """
        body = 'hello, world'
        major = 'image'
        minor = 'jpeg'
        charset = 'us-ascii'
        identifier = 'some kind of id'
        description = 'great justice'
        encoding = 'maximum'
        md5 = 'abcdefabcdef'
        msg = FakeyMessage({
                'content-type': '%s/%s; charset=%s; x=y' % (
                    major, minor, charset),
                'content-id': identifier,
                'content-description': description,
                'content-transfer-encoding': encoding,
                'content-md5': md5,
                'content-disposition': 'attachment; name=foo; size=bar',
                'content-language': 'fr',
                'content-location': 'France',
                }, (), '', body, 123, None)
        structure = imap4.getBodyStructure(msg, extended=True)
        self.assertEqual(
            [major, minor, ["charset", charset, 'x', 'y'], identifier,
             description, encoding, len(body), md5,
             ['attachment', ['name', 'foo', 'size', 'bar']], 'fr', 'France'],
            structure)


    def test_singlePartWithMissing(self):
        """
        For fields with no information contained in the message headers,
        L{imap4.getBodyStructure} fills in C{None} values in its result.
        """
        major = 'image'
        minor = 'jpeg'
        body = 'hello, world'
        msg = FakeyMessage({
                'content-type': '%s/%s' % (major, minor),
                }, (), '', body, 123, None)
        structure = imap4.getBodyStructure(msg, extended=True)
        self.assertEqual(
            [major, minor, None, None, None, None, len(body), None, None,
             None, None],
            structure)


    def test_textPart(self):
        """
        For a I{text/*} message, the number of lines in the message body are
        included after the common single-part basic fields.
        """
        body = 'hello, world\nhow are you?\ngoodbye\n'
        major = 'text'
        minor = 'jpeg'
        charset = 'us-ascii'
        identifier = 'some kind of id'
        description = 'great justice'
        encoding = 'maximum'
        msg = FakeyMessage({
                'content-type': '%s/%s; charset=%s; x=y' % (
                    major, minor, charset),
                'content-id': identifier,
                'content-description': description,
                'content-transfer-encoding': encoding,
                }, (), '', body, 123, None)
        structure = imap4.getBodyStructure(msg)
        self.assertEqual(
            [major, minor, ["charset", charset, 'x', 'y'], identifier,
             description, encoding, len(body), len(body.splitlines())],
            structure)


    def test_rfc822Message(self):
        """
        For a I{message/rfc822} message, the common basic fields are followed
        by information about the contained message.
        """
        body = 'hello, world\nhow are you?\ngoodbye\n'
        major = 'text'
        minor = 'jpeg'
        charset = 'us-ascii'
        identifier = 'some kind of id'
        description = 'great justice'
        encoding = 'maximum'
        msg = FakeyMessage({
                'content-type': '%s/%s; charset=%s; x=y' % (
                    major, minor, charset),
                'from': 'Alice <alice@example.com>',
                'to': 'Bob <bob@example.com>',
                'content-id': identifier,
                'content-description': description,
                'content-transfer-encoding': encoding,
                }, (), '', body, 123, None)

        container = FakeyMessage({
                'content-type': 'message/rfc822',
                }, (), '', '', 123, [msg])

        structure = imap4.getBodyStructure(container)
        self.assertEqual(
            ['message', 'rfc822', None, None, None, None, 0,
             imap4.getEnvelope(msg), imap4.getBodyStructure(msg), 3],
            structure)


    def test_multiPart(self):
        """
        For a I{multipart/*} message, L{imap4.getBodyStructure} returns a list
        containing the body structure information for each part of the message
        followed by an element giving the MIME subtype of the message.
        """
        oneSubPart = FakeyMessage({
                'content-type': 'image/jpeg; x=y',
                'content-id': 'some kind of id',
                'content-description': 'great justice',
                'content-transfer-encoding': 'maximum',
                }, (), '', 'hello world', 123, None)

        anotherSubPart = FakeyMessage({
                'content-type': 'text/plain; charset=us-ascii',
                }, (), '', 'some stuff', 321, None)

        container = FakeyMessage({
                'content-type': 'multipart/related',
                }, (), '', '', 555, [oneSubPart, anotherSubPart])

        self.assertEqual(
            [imap4.getBodyStructure(oneSubPart),
             imap4.getBodyStructure(anotherSubPart),
             'related'],
            imap4.getBodyStructure(container))


    def test_multiPartExtended(self):
        """
        When passed a I{multipart/*} message and C{True} for the C{extended}
        argument, L{imap4.getBodyStructure} includes extended structure
        information from the parts of the multipart message and extended
        structure information about the multipart message itself.
        """
        oneSubPart = FakeyMessage({
                'content-type': 'image/jpeg; x=y',
                'content-id': 'some kind of id',
                'content-description': 'great justice',
                'content-transfer-encoding': 'maximum',
                }, (), '', 'hello world', 123, None)

        anotherSubPart = FakeyMessage({
                'content-type': 'text/plain; charset=us-ascii',
                }, (), '', 'some stuff', 321, None)

        container = FakeyMessage({
                'content-type': 'multipart/related; foo=bar',
                'content-language': 'es',
                'content-location': 'Spain',
                'content-disposition': 'attachment; name=monkeys',
                }, (), '', '', 555, [oneSubPart, anotherSubPart])

        self.assertEqual(
            [imap4.getBodyStructure(oneSubPart, extended=True),
             imap4.getBodyStructure(anotherSubPart, extended=True),
             'related', ['foo', 'bar'], ['attachment', ['name', 'monkeys']],
             'es', 'Spain'],
            imap4.getBodyStructure(container, extended=True))



class NewFetchTestCase(unittest.TestCase, IMAP4HelperMixin):
    def setUp(self):
        self.received_messages = self.received_uid = None
        self.result = None

        self.server = imap4.IMAP4Server()
        self.server.state = 'select'
        self.server.mbox = self
        self.connected = defer.Deferred()
        self.client = SimpleClient(self.connected)

    def addListener(self, x):
        pass
    def removeListener(self, x):
        pass

    def fetch(self, messages, uid):
        self.received_messages = messages
        self.received_uid = uid
        return iter(zip(range(len(self.msgObjs)), self.msgObjs))

    def _fetchWork(self, uid):
        if uid:
            for (i, msg) in zip(range(len(self.msgObjs)), self.msgObjs):
                self.expected[i]['UID'] = str(msg.getUID())

        def result(R):
            self.result = R

        self.connected.addCallback(lambda _: self.function(self.messages, uid)
        ).addCallback(result
        ).addCallback(self._cbStopClient
        ).addErrback(self._ebGeneral)

        d = loopback.loopbackTCP(self.server, self.client, noisy=False)
        d.addCallback(lambda x : self.assertEqual(self.result, self.expected))
        return d

    def testFetchUID(self):
        self.function = lambda m, u: self.client.fetchUID(m)

        self.messages = '7'
        self.msgObjs = [
            FakeyMessage({}, (), '', '', 12345, None),
            FakeyMessage({}, (), '', '', 999, None),
            FakeyMessage({}, (), '', '', 10101, None),
        ]
        self.expected = {
            0: {'UID': '12345'},
            1: {'UID': '999'},
            2: {'UID': '10101'},
        }
        return self._fetchWork(0)

    def testFetchFlags(self, uid=0):
        self.function = self.client.fetchFlags
        self.messages = '9'
        self.msgObjs = [
            FakeyMessage({}, ['FlagA', 'FlagB', '\\FlagC'], '', '', 54321, None),
            FakeyMessage({}, ['\\FlagC', 'FlagA', 'FlagB'], '', '', 12345, None),
        ]
        self.expected = {
            0: {'FLAGS': ['FlagA', 'FlagB', '\\FlagC']},
            1: {'FLAGS': ['\\FlagC', 'FlagA', 'FlagB']},
        }
        return self._fetchWork(uid)

    def testFetchFlagsUID(self):
        return self.testFetchFlags(1)

    def testFetchInternalDate(self, uid=0):
        self.function = self.client.fetchInternalDate
        self.messages = '13'
        self.msgObjs = [
            FakeyMessage({}, (), 'Fri, 02 Nov 2003 21:25:10 GMT', '', 23232, None),
            FakeyMessage({}, (), 'Thu, 29 Dec 2013 11:31:52 EST', '', 101, None),
            FakeyMessage({}, (), 'Mon, 10 Mar 1992 02:44:30 CST', '', 202, None),
            FakeyMessage({}, (), 'Sat, 11 Jan 2000 14:40:24 PST', '', 303, None),
        ]
        self.expected = {
            0: {'INTERNALDATE': '02-Nov-2003 21:25:10 +0000'},
            1: {'INTERNALDATE': '29-Dec-2013 11:31:52 -0500'},
            2: {'INTERNALDATE': '10-Mar-1992 02:44:30 -0600'},
            3: {'INTERNALDATE': '11-Jan-2000 14:40:24 -0800'},
        }
        return self._fetchWork(uid)

    def testFetchInternalDateUID(self):
        return self.testFetchInternalDate(1)


    def test_fetchInternalDateLocaleIndependent(self):
        """
        The month name in the date is locale independent.
        """
        # Fake that we're in a language where December is not Dec
        currentLocale = locale.setlocale(locale.LC_ALL, None)
        locale.setlocale(locale.LC_ALL, "es_AR.UTF8")
        self.addCleanup(locale.setlocale, locale.LC_ALL, currentLocale)
        return self.testFetchInternalDate(1)

    # if alternate locale is not available, the previous test will be skipped,
    # please install this locale for it to run.  Avoid using locale.getlocale to
    # learn the current locale; its values don't round-trip well on all
    # platforms.  Fortunately setlocale returns a value which does round-trip
    # well.
    currentLocale = locale.setlocale(locale.LC_ALL, None)
    try:
        locale.setlocale(locale.LC_ALL, "es_AR.UTF8")
    except locale.Error:
        test_fetchInternalDateLocaleIndependent.skip = (
            "The es_AR.UTF8 locale is not installed.")
    else:
        locale.setlocale(locale.LC_ALL, currentLocale)


    def testFetchEnvelope(self, uid=0):
        self.function = self.client.fetchEnvelope
        self.messages = '15'
        self.msgObjs = [
            FakeyMessage({
                'from': 'user@domain', 'to': 'resu@domain',
                'date': 'thursday', 'subject': 'it is a message',
                'message-id': 'id-id-id-yayaya'}, (), '', '', 65656,
                None),
        ]
        self.expected = {
            0: {'ENVELOPE':
                ['thursday', 'it is a message',
                    [[None, None, 'user', 'domain']],
                    [[None, None, 'user', 'domain']],
                    [[None, None, 'user', 'domain']],
                    [[None, None, 'resu', 'domain']],
                    None, None, None, 'id-id-id-yayaya']
            }
        }
        return self._fetchWork(uid)

    def testFetchEnvelopeUID(self):
        return self.testFetchEnvelope(1)


    def test_fetchBodyStructure(self, uid=0):
        """
        L{IMAP4Client.fetchBodyStructure} issues a I{FETCH BODYSTRUCTURE}
        command and returns a Deferred which fires with a structure giving the
        result of parsing the server's response.  The structure is a list
        reflecting the parenthesized data sent by the server, as described by
        RFC 3501, section 7.4.2.
        """
        self.function = self.client.fetchBodyStructure
        self.messages = '3:9,10:*'
        self.msgObjs = [FakeyMessage({
                'content-type': 'text/plain; name=thing; key="value"',
                'content-id': 'this-is-the-content-id',
                'content-description': 'describing-the-content-goes-here!',
                'content-transfer-encoding': '8BIT',
                'content-md5': 'abcdef123456',
                'content-disposition': 'attachment; filename=monkeys',
                'content-language': 'es',
                'content-location': 'http://example.com/monkeys',
            }, (), '', 'Body\nText\nGoes\nHere\n', 919293, None)]
        self.expected = {0: {'BODYSTRUCTURE': [
            'text', 'plain', ['key', 'value', 'name', 'thing'],
            'this-is-the-content-id', 'describing-the-content-goes-here!',
            '8BIT', '20', '4', 'abcdef123456',
            ['attachment', ['filename', 'monkeys']], 'es',
             'http://example.com/monkeys']}}
        return self._fetchWork(uid)


    def testFetchBodyStructureUID(self):
        """
        If passed C{True} for the C{uid} argument, C{fetchBodyStructure} can
        also issue a I{UID FETCH BODYSTRUCTURE} command.
        """
        return self.test_fetchBodyStructure(1)


    def test_fetchBodyStructureMultipart(self, uid=0):
        """
        L{IMAP4Client.fetchBodyStructure} can also parse the response to a
        I{FETCH BODYSTRUCTURE} command for a multipart message.
        """
        self.function = self.client.fetchBodyStructure
        self.messages = '3:9,10:*'
        innerMessage = FakeyMessage({
                'content-type': 'text/plain; name=thing; key="value"',
                'content-id': 'this-is-the-content-id',
                'content-description': 'describing-the-content-goes-here!',
                'content-transfer-encoding': '8BIT',
                'content-language': 'fr',
                'content-md5': '123456abcdef',
                'content-disposition': 'inline',
                'content-location': 'outer space',
            }, (), '', 'Body\nText\nGoes\nHere\n', 919293, None)
        self.msgObjs = [FakeyMessage({
                'content-type': 'multipart/mixed; boundary="xyz"',
                'content-language': 'en',
                'content-location': 'nearby',
            }, (), '', '', 919293, [innerMessage])]
        self.expected = {0: {'BODYSTRUCTURE': [
            ['text', 'plain', ['key', 'value', 'name', 'thing'],
             'this-is-the-content-id', 'describing-the-content-goes-here!',
             '8BIT', '20', '4', '123456abcdef', ['inline', None], 'fr',
             'outer space'],
            'mixed', ['boundary', 'xyz'], None, 'en', 'nearby'
            ]}}
        return self._fetchWork(uid)


    def testFetchSimplifiedBody(self, uid=0):
        self.function = self.client.fetchSimplifiedBody
        self.messages = '21'
        self.msgObjs = [FakeyMessage({}, (), '', 'Yea whatever', 91825,
            [FakeyMessage({'content-type': 'image/jpg'}, (), '',
                'Body Body Body', None, None
            )]
        )]
        self.expected = {0:
            {'BODY':
                [None, None, None, None, None, None,
                    '12'
                ]
            }
        }

        return self._fetchWork(uid)

    def testFetchSimplifiedBodyUID(self):
        return self.testFetchSimplifiedBody(1)

    def testFetchSimplifiedBodyText(self, uid=0):
        self.function = self.client.fetchSimplifiedBody
        self.messages = '21'
        self.msgObjs = [FakeyMessage({'content-type': 'text/plain'},
            (), '', 'Yea whatever', 91825, None)]
        self.expected = {0:
            {'BODY':
                ['text', 'plain', None, None, None, None,
                    '12', '1'
                ]
            }
        }

        return self._fetchWork(uid)

    def testFetchSimplifiedBodyTextUID(self):
        return self.testFetchSimplifiedBodyText(1)

    def testFetchSimplifiedBodyRFC822(self, uid=0):
        self.function = self.client.fetchSimplifiedBody
        self.messages = '21'
        self.msgObjs = [FakeyMessage({'content-type': 'message/rfc822'},
            (), '', 'Yea whatever', 91825,
            [FakeyMessage({'content-type': 'image/jpg'}, (), '',
                'Body Body Body', None, None
            )]
        )]
        self.expected = {0:
            {'BODY':
                ['message', 'rfc822', None, None, None, None,
                    '12', [None, None, [[None, None, None]],
                    [[None, None, None]], None, None, None,
                    None, None, None], ['image', 'jpg', None,
                    None, None, None, '14'], '1'
                ]
            }
        }

        return self._fetchWork(uid)

    def testFetchSimplifiedBodyRFC822UID(self):
        return self.testFetchSimplifiedBodyRFC822(1)


    def test_fetchSimplifiedBodyMultipart(self):
        """
        L{IMAP4Client.fetchSimplifiedBody} returns a dictionary mapping message
        sequence numbers to fetch responses for the corresponding messages.  In
        particular, for a multipart message, the value in the dictionary maps
        the string C{"BODY"} to a list giving the body structure information for
        that message, in the form of a list of subpart body structure
        information followed by the subtype of the message (eg C{"alternative"}
        for a I{multipart/alternative} message).  This structure is self-similar
        in the case where a subpart is itself multipart.
        """
        self.function = self.client.fetchSimplifiedBody
        self.messages = '21'

        # A couple non-multipart messages to use as the inner-most payload
        singles = [
            FakeyMessage(
                {'content-type': 'text/plain'},
                (), 'date', 'Stuff', 54321,  None),
            FakeyMessage(
                {'content-type': 'text/html'},
                (), 'date', 'Things', 32415, None)]

        # A multipart/alternative message containing the above non-multipart
        # messages.  This will be the payload of the outer-most message.
        alternative = FakeyMessage(
            {'content-type': 'multipart/alternative'},
            (), '', 'Irrelevant', 12345, singles)

        # The outer-most message, also with a multipart type, containing just
        # the single middle message.
        mixed = FakeyMessage(
            # The message is multipart/mixed
            {'content-type': 'multipart/mixed'},
            (), '', 'RootOf', 98765, [alternative])

        self.msgObjs = [mixed]

        self.expected = {
            0: {'BODY': [
                    [['text', 'plain', None, None, None, None, '5', '1'],
                     ['text', 'html', None, None, None, None, '6', '1'],
                     'alternative'],
                    'mixed']}}

        return self._fetchWork(False)


    def testFetchMessage(self, uid=0):
        self.function = self.client.fetchMessage
        self.messages = '1,3,7,10101'
        self.msgObjs = [
            FakeyMessage({'Header': 'Value'}, (), '', 'BODY TEXT\r\n', 91, None),
        ]
        self.expected = {
            0: {'RFC822': 'Header: Value\r\n\r\nBODY TEXT\r\n'}
        }
        return self._fetchWork(uid)

    def testFetchMessageUID(self):
        return self.testFetchMessage(1)

    def testFetchHeaders(self, uid=0):
        self.function = self.client.fetchHeaders
        self.messages = '9,6,2'
        self.msgObjs = [
            FakeyMessage({'H1': 'V1', 'H2': 'V2'}, (), '', '', 99, None),
        ]
        self.expected = {
            0: {'RFC822.HEADER': imap4._formatHeaders({'H1': 'V1', 'H2': 'V2'})},
        }
        return self._fetchWork(uid)

    def testFetchHeadersUID(self):
        return self.testFetchHeaders(1)

    def testFetchBody(self, uid=0):
        self.function = self.client.fetchBody
        self.messages = '1,2,3,4,5,6,7'
        self.msgObjs = [
            FakeyMessage({'Header': 'Value'}, (), '', 'Body goes here\r\n', 171, None),
        ]
        self.expected = {
            0: {'RFC822.TEXT': 'Body goes here\r\n'},
        }
        return self._fetchWork(uid)

    def testFetchBodyUID(self):
        return self.testFetchBody(1)

    def testFetchBodyParts(self):
        """
        Test the server's handling of requests for specific body sections.
        """
        self.function = self.client.fetchSpecific
        self.messages = '1'
        outerBody = ''
        innerBody1 = 'Contained body message text.  Squarge.'
        innerBody2 = 'Secondary <i>message</i> text of squarge body.'
        headers = util.OrderedDict()
        headers['from'] = 'sender@host'
        headers['to'] = 'recipient@domain'
        headers['subject'] = 'booga booga boo'
        headers['content-type'] = 'multipart/alternative; boundary="xyz"'
        innerHeaders = util.OrderedDict()
        innerHeaders['subject'] = 'this is subject text'
        innerHeaders['content-type'] = 'text/plain'
        innerHeaders2 = util.OrderedDict()
        innerHeaders2['subject'] = '<b>this is subject</b>'
        innerHeaders2['content-type'] = 'text/html'
        self.msgObjs = [FakeyMessage(
            headers, (), None, outerBody, 123,
            [FakeyMessage(innerHeaders, (), None, innerBody1, None, None),
             FakeyMessage(innerHeaders2, (), None, innerBody2, None, None)])]
        self.expected = {
            0: [['BODY', ['1'], 'Contained body message text.  Squarge.']]}

        def result(R):
            self.result = R

        self.connected.addCallback(
            lambda _: self.function(self.messages, headerNumber=1))
        self.connected.addCallback(result)
        self.connected.addCallback(self._cbStopClient)
        self.connected.addErrback(self._ebGeneral)

        d = loopback.loopbackTCP(self.server, self.client, noisy=False)
        d.addCallback(lambda ign: self.assertEqual(self.result, self.expected))
        return d


    def test_fetchBodyPartOfNonMultipart(self):
        """
        Single-part messages have an implicit first part which clients
        should be able to retrieve explicitly.  Test that a client
        requesting part 1 of a text/plain message receives the body of the
        text/plain part.
        """
        self.function = self.client.fetchSpecific
        self.messages = '1'
        parts = [1]
        outerBody = 'DA body'
        headers = util.OrderedDict()
        headers['from'] = 'sender@host'
        headers['to'] = 'recipient@domain'
        headers['subject'] = 'booga booga boo'
        headers['content-type'] = 'text/plain'
        self.msgObjs = [FakeyMessage(
            headers, (), None, outerBody, 123, None)]

        self.expected = {0: [['BODY', ['1'], 'DA body']]}

        def result(R):
            self.result = R

        self.connected.addCallback(
            lambda _: self.function(self.messages, headerNumber=parts))
        self.connected.addCallback(result)
        self.connected.addCallback(self._cbStopClient)
        self.connected.addErrback(self._ebGeneral)

        d = loopback.loopbackTCP(self.server, self.client, noisy=False)
        d.addCallback(lambda ign: self.assertEqual(self.result, self.expected))
        return d


    def testFetchSize(self, uid=0):
        self.function = self.client.fetchSize
        self.messages = '1:100,2:*'
        self.msgObjs = [
            FakeyMessage({}, (), '', 'x' * 20, 123, None),
        ]
        self.expected = {
            0: {'RFC822.SIZE': '20'},
        }
        return self._fetchWork(uid)

    def testFetchSizeUID(self):
        return self.testFetchSize(1)

    def testFetchFull(self, uid=0):
        self.function = self.client.fetchFull
        self.messages = '1,3'
        self.msgObjs = [
            FakeyMessage({}, ('\\XYZ', '\\YZX', 'Abc'),
                'Sun, 25 Jul 2010 06:20:30 -0400 (EDT)',
                'xyz' * 2, 654, None),
            FakeyMessage({}, ('\\One', '\\Two', 'Three'),
                'Mon, 14 Apr 2003 19:43:44 -0400',
                'abc' * 4, 555, None),
        ]
        self.expected = {
            0: {'FLAGS': ['\\XYZ', '\\YZX', 'Abc'],
                'INTERNALDATE': '25-Jul-2010 06:20:30 -0400',
                'RFC822.SIZE': '6',
                'ENVELOPE': [None, None, [[None, None, None]], [[None, None, None]], None, None, None, None, None, None],
                'BODY': [None, None, None, None, None, None, '6']},
            1: {'FLAGS': ['\\One', '\\Two', 'Three'],
                'INTERNALDATE': '14-Apr-2003 19:43:44 -0400',
                'RFC822.SIZE': '12',
                'ENVELOPE': [None, None, [[None, None, None]], [[None, None, None]], None, None, None, None, None, None],
                'BODY': [None, None, None, None, None, None, '12']},
        }
        return self._fetchWork(uid)

    def testFetchFullUID(self):
        return self.testFetchFull(1)

    def testFetchAll(self, uid=0):
        self.function = self.client.fetchAll
        self.messages = '1,2:3'
        self.msgObjs = [
            FakeyMessage({}, (), 'Mon, 14 Apr 2003 19:43:44 +0400',
                'Lalala', 10101, None),
            FakeyMessage({}, (), 'Tue, 15 Apr 2003 19:43:44 +0200',
                'Alalal', 20202, None),
        ]
        self.expected = {
            0: {'ENVELOPE': [None, None, [[None, None, None]], [[None, None, None]], None, None, None, None, None, None],
                'RFC822.SIZE': '6',
                'INTERNALDATE': '14-Apr-2003 19:43:44 +0400',
                'FLAGS': []},
            1: {'ENVELOPE': [None, None, [[None, None, None]], [[None, None, None]], None, None, None, None, None, None],
                'RFC822.SIZE': '6',
                'INTERNALDATE': '15-Apr-2003 19:43:44 +0200',
                'FLAGS': []},
        }
        return self._fetchWork(uid)

    def testFetchAllUID(self):
        return self.testFetchAll(1)

    def testFetchFast(self, uid=0):
        self.function = self.client.fetchFast
        self.messages = '1'
        self.msgObjs = [
            FakeyMessage({}, ('\\X',), '19 Mar 2003 19:22:21 -0500', '', 9, None),
        ]
        self.expected = {
            0: {'FLAGS': ['\\X'],
                'INTERNALDATE': '19-Mar-2003 19:22:21 -0500',
                'RFC822.SIZE': '0'},
        }
        return self._fetchWork(uid)

    def testFetchFastUID(self):
        return self.testFetchFast(1)



class DefaultSearchTestCase(IMAP4HelperMixin, unittest.TestCase):
    """
    Test the behavior of the server's SEARCH implementation, particularly in
    the face of unhandled search terms.
    """
    def setUp(self):
        self.server = imap4.IMAP4Server()
        self.server.state = 'select'
        self.server.mbox = self
        self.connected = defer.Deferred()
        self.client = SimpleClient(self.connected)
        self.msgObjs = [
            FakeyMessage({}, (), '', '', 999, None),
            FakeyMessage({}, (), '', '', 10101, None),
            FakeyMessage({}, (), '', '', 12345, None),
            FakeyMessage({}, (), '', '', 20001, None),
            FakeyMessage({}, (), '', '', 20002, None),
        ]


    def fetch(self, messages, uid):
        """
        Pretend to be a mailbox and let C{self.server} lookup messages on me.
        """
        return zip(range(1, len(self.msgObjs) + 1), self.msgObjs)


    def _messageSetSearchTest(self, queryTerms, expectedMessages):
        """
        Issue a search with given query and verify that the returned messages
        match the given expected messages.

        @param queryTerms: A string giving the search query.
        @param expectedMessages: A list of the message sequence numbers
            expected as the result of the search.
        @return: A L{Deferred} which fires when the test is complete.
        """
        def search():
            return self.client.search(queryTerms)

        d = self.connected.addCallback(strip(search))
        def searched(results):
            self.assertEqual(results, expectedMessages)
        d.addCallback(searched)
        d.addCallback(self._cbStopClient)
        d.addErrback(self._ebGeneral)
        self.loopback()
        return d


    def test_searchMessageSet(self):
        """
        Test that a search which starts with a message set properly limits
        the search results to messages in that set.
        """
        return self._messageSetSearchTest('1', [1])


    def test_searchMessageSetWithStar(self):
        """
        If the search filter ends with a star, all the message from the
        starting point are returned.
        """
        return self._messageSetSearchTest('2:*', [2, 3, 4, 5])


    def test_searchMessageSetWithStarFirst(self):
        """
        If the search filter starts with a star, the result should be identical
        with if the filter would end with a star.
        """
        return self._messageSetSearchTest('*:2', [2, 3, 4, 5])


    def test_searchMessageSetUIDWithStar(self):
        """
        If the search filter ends with a star, all the message from the
        starting point are returned (also for the SEARCH UID case).
        """
        return self._messageSetSearchTest('UID 10000:*', [2, 3, 4, 5])


    def test_searchMessageSetUIDWithStarFirst(self):
        """
        If the search filter starts with a star, the result should be identical
        with if the filter would end with a star (also for the SEARCH UID case).
        """
        return self._messageSetSearchTest('UID *:10000', [2, 3, 4, 5])


    def test_searchMessageSetUIDWithStarAndHighStart(self):
        """
        A search filter of 1234:* should include the UID of the last message in
        the mailbox, even if its UID is less than 1234.
        """
        # in our fake mbox the highest message UID is 20002
        return self._messageSetSearchTest('UID 30000:*', [5])


    def test_searchMessageSetWithList(self):
        """
        If the search filter contains nesting terms, one of which includes a
        message sequence set with a wildcard, IT ALL WORKS GOOD.
        """
        # 6 is bigger than the biggest message sequence number, but that's
        # okay, because N:* includes the biggest message sequence number even
        # if N is bigger than that (read the rfc nub).
        return self._messageSetSearchTest('(6:*)', [5])


    def test_searchOr(self):
        """
        If the search filter contains an I{OR} term, all messages
        which match either subexpression are returned.
        """
        return self._messageSetSearchTest('OR 1 2', [1, 2])


    def test_searchOrMessageSet(self):
        """
        If the search filter contains an I{OR} term with a
        subexpression which includes a message sequence set wildcard,
        all messages in that set are considered for inclusion in the
        results.
        """
        return self._messageSetSearchTest('OR 2:* 2:*', [2, 3, 4, 5])


    def test_searchNot(self):
        """
        If the search filter contains a I{NOT} term, all messages
        which do not match the subexpression are returned.
        """
        return self._messageSetSearchTest('NOT 3', [1, 2, 4, 5])


    def test_searchNotMessageSet(self):
        """
        If the search filter contains a I{NOT} term with a
        subexpression which includes a message sequence set wildcard,
        no messages in that set are considered for inclusion in the
        result.
        """
        return self._messageSetSearchTest('NOT 2:*', [1])


    def test_searchAndMessageSet(self):
        """
        If the search filter contains multiple terms implicitly
        conjoined with a message sequence set wildcard, only the
        intersection of the results of each term are returned.
        """
        return self._messageSetSearchTest('2:* 3', [3])

    def test_searchInvalidCriteria(self):
        """
        If the search criteria is not a valid key, a NO result is returned to
        the client (resulting in an error callback), and an IllegalQueryError is
        logged on the server side.
        """
        queryTerms = 'FOO'
        def search():
            return self.client.search(queryTerms)

        d = self.connected.addCallback(strip(search))
        d = self.assertFailure(d, imap4.IMAP4Exception)

        def errorReceived(results):
            """
            Verify that the server logs an IllegalQueryError and the
            client raises an IMAP4Exception with 'Search failed:...'
            """
            self.client.transport.loseConnection()
            self.server.transport.loseConnection()

            # Check what the server logs
            errors = self.flushLoggedErrors(imap4.IllegalQueryError)
            self.assertEqual(len(errors), 1)

            # Verify exception given to client has the correct message
            self.assertEqual(
                "SEARCH failed: Invalid search command FOO", str(results))

        d.addCallback(errorReceived)
        d.addErrback(self._ebGeneral)
        self.loopback()
        return d



class FetchSearchStoreTestCase(unittest.TestCase, IMAP4HelperMixin):
    implements(imap4.ISearchableMailbox)

    def setUp(self):
        self.expected = self.result = None
        self.server_received_query = None
        self.server_received_uid = None
        self.server_received_parts = None
        self.server_received_messages = None

        self.server = imap4.IMAP4Server()
        self.server.state = 'select'
        self.server.mbox = self
        self.connected = defer.Deferred()
        self.client = SimpleClient(self.connected)

    def search(self, query, uid):
        # Look for a specific bad query, so we can verify we handle it properly
        if query == ['FOO']:
            raise imap4.IllegalQueryError("FOO is not a valid search criteria")

        self.server_received_query = query
        self.server_received_uid = uid
        return self.expected

    def addListener(self, *a, **kw):
        pass
    removeListener = addListener

    def _searchWork(self, uid):
        def search():
            return self.client.search(self.query, uid=uid)
        def result(R):
            self.result = R

        self.connected.addCallback(strip(search)
        ).addCallback(result
        ).addCallback(self._cbStopClient
        ).addErrback(self._ebGeneral)

        def check(ignored):
            # Ensure no short-circuiting wierdness is going on
            self.failIf(self.result is self.expected)

            self.assertEqual(self.result, self.expected)
            self.assertEqual(self.uid, self.server_received_uid)
            self.assertEqual(
                imap4.parseNestedParens(self.query),
                self.server_received_query
            )
        d = loopback.loopbackTCP(self.server, self.client, noisy=False)
        d.addCallback(check)
        return d

    def testSearch(self):
        self.query = imap4.Or(
            imap4.Query(header=('subject', 'substring')),
            imap4.Query(larger=1024, smaller=4096),
        )
        self.expected = [1, 4, 5, 7]
        self.uid = 0
        return self._searchWork(0)

    def testUIDSearch(self):
        self.query = imap4.Or(
            imap4.Query(header=('subject', 'substring')),
            imap4.Query(larger=1024, smaller=4096),
        )
        self.uid = 1
        self.expected = [1, 2, 3]
        return self._searchWork(1)

    def getUID(self, msg):
        try:
            return self.expected[msg]['UID']
        except (TypeError, IndexError):
            return self.expected[msg-1]
        except KeyError:
            return 42

    def fetch(self, messages, uid):
        self.server_received_uid = uid
        self.server_received_messages = str(messages)
        return self.expected

    def _fetchWork(self, fetch):
        def result(R):
            self.result = R

        self.connected.addCallback(strip(fetch)
        ).addCallback(result
        ).addCallback(self._cbStopClient
        ).addErrback(self._ebGeneral)

        def check(ignored):
            # Ensure no short-circuiting wierdness is going on
            self.failIf(self.result is self.expected)

            self.parts and self.parts.sort()
            self.server_received_parts and self.server_received_parts.sort()

            if self.uid:
                for (k, v) in self.expected.items():
                    v['UID'] = str(k)

            self.assertEqual(self.result, self.expected)
            self.assertEqual(self.uid, self.server_received_uid)
            self.assertEqual(self.parts, self.server_received_parts)
            self.assertEqual(imap4.parseIdList(self.messages),
                              imap4.parseIdList(self.server_received_messages))

        d = loopback.loopbackTCP(self.server, self.client, noisy=False)
        d.addCallback(check)
        return d


    def test_invalidTerm(self):
        """
        If, as part of a search, an ISearchableMailbox raises an
        IllegalQueryError (e.g. due to invalid search criteria), client sees a
        failure response, and an IllegalQueryError is logged on the server.
        """
        query = 'FOO'

        def search():
            return self.client.search(query)

        d = self.connected.addCallback(strip(search))
        d = self.assertFailure(d, imap4.IMAP4Exception)

        def errorReceived(results):
            """
            Verify that the server logs an IllegalQueryError and the
            client raises an IMAP4Exception with 'Search failed:...'
            """
            self.client.transport.loseConnection()
            self.server.transport.loseConnection()

            # Check what the server logs
            errors = self.flushLoggedErrors(imap4.IllegalQueryError)
            self.assertEqual(len(errors), 1)

            # Verify exception given to client has the correct message
            self.assertEqual(
                "SEARCH failed: FOO is not a valid search criteria",
                str(results))

        d.addCallback(errorReceived)
        d.addErrback(self._ebGeneral)
        self.loopback()
        return d



class FakeMailbox:
    def __init__(self):
        self.args = []
    def addMessage(self, body, flags, date):
        self.args.append((body, flags, date))
        return defer.succeed(None)

class FeaturefulMessage:
    implements(imap4.IMessageFile)

    def getFlags(self):
        return 'flags'

    def getInternalDate(self):
        return 'internaldate'

    def open(self):
        return StringIO("open")

class MessageCopierMailbox:
    implements(imap4.IMessageCopier)

    def __init__(self):
        self.msgs = []

    def copy(self, msg):
        self.msgs.append(msg)
        return len(self.msgs)

class CopyWorkerTestCase(unittest.TestCase):
    def testFeaturefulMessage(self):
        s = imap4.IMAP4Server()

        # Yes.  I am grabbing this uber-non-public method to test it.
        # It is complex.  It needs to be tested directly!
        # Perhaps it should be refactored, simplified, or split up into
        # not-so-private components, but that is a task for another day.

        # Ha ha! Addendum!  Soon it will be split up, and this test will
        # be re-written to just use the default adapter for IMailbox to
        # IMessageCopier and call .copy on that adapter.
        f = s._IMAP4Server__cbCopy

        m = FakeMailbox()
        d = f([(i, FeaturefulMessage()) for i in range(1, 11)], 'tag', m)

        def cbCopy(results):
            for a in m.args:
                self.assertEqual(a[0].read(), "open")
                self.assertEqual(a[1], "flags")
                self.assertEqual(a[2], "internaldate")

            for (status, result) in results:
                self.failUnless(status)
                self.assertEqual(result, None)

        return d.addCallback(cbCopy)


    def testUnfeaturefulMessage(self):
        s = imap4.IMAP4Server()

        # See above comment
        f = s._IMAP4Server__cbCopy

        m = FakeMailbox()
        msgs = [FakeyMessage({'Header-Counter': str(i)}, (), 'Date', 'Body %d' % (i,), i + 10, None) for i in range(1, 11)]
        d = f([im for im in zip(range(1, 11), msgs)], 'tag', m)

        def cbCopy(results):
            seen = []
            for a in m.args:
                seen.append(a[0].read())
                self.assertEqual(a[1], ())
                self.assertEqual(a[2], "Date")

            seen.sort()
            exp = ["Header-Counter: %d\r\n\r\nBody %d" % (i, i) for i in range(1, 11)]
            exp.sort()
            self.assertEqual(seen, exp)

            for (status, result) in results:
                self.failUnless(status)
                self.assertEqual(result, None)

        return d.addCallback(cbCopy)

    def testMessageCopier(self):
        s = imap4.IMAP4Server()

        # See above comment
        f = s._IMAP4Server__cbCopy

        m = MessageCopierMailbox()
        msgs = [object() for i in range(1, 11)]
        d = f([im for im in zip(range(1, 11), msgs)], 'tag', m)

        def cbCopy(results):
            self.assertEqual(results, zip([1] * 10, range(1, 11)))
            for (orig, new) in zip(msgs, m.msgs):
                self.assertIdentical(orig, new)

        return d.addCallback(cbCopy)


class TLSTestCase(IMAP4HelperMixin, unittest.TestCase):
    serverCTX = ServerTLSContext and ServerTLSContext()
    clientCTX = ClientTLSContext and ClientTLSContext()

    def loopback(self):
        return loopback.loopbackTCP(self.server, self.client, noisy=False)

    def testAPileOfThings(self):
        SimpleServer.theAccount.addMailbox('inbox')
        called = []
        def login():
            called.append(None)
            return self.client.login('testuser', 'password-test')
        def list():
            called.append(None)
            return self.client.list('inbox', '%')
        def status():
            called.append(None)
            return self.client.status('inbox', 'UIDNEXT')
        def examine():
            called.append(None)
            return self.client.examine('inbox')
        def logout():
            called.append(None)
            return self.client.logout()

        self.client.requireTransportSecurity = True

        methods = [login, list, status, examine, logout]
        map(self.connected.addCallback, map(strip, methods))
        self.connected.addCallbacks(self._cbStopClient, self._ebGeneral)
        def check(ignored):
            self.assertEqual(self.server.startedTLS, True)
            self.assertEqual(self.client.startedTLS, True)
            self.assertEqual(len(called), len(methods))
        d = self.loopback()
        d.addCallback(check)
        return d

    def testLoginLogin(self):
        self.server.checker.addUser('testuser', 'password-test')
        success = []
        self.client.registerAuthenticator(imap4.LOGINAuthenticator('testuser'))
        self.connected.addCallback(
                lambda _: self.client.authenticate('password-test')
            ).addCallback(
                lambda _: self.client.logout()
            ).addCallback(success.append
            ).addCallback(self._cbStopClient
            ).addErrback(self._ebGeneral)

        d = self.loopback()
        d.addCallback(lambda x : self.assertEqual(len(success), 1))
        return d


    def test_startTLS(self):
        """
        L{IMAP4Client.startTLS} triggers TLS negotiation and returns a
        L{Deferred} which fires after the client's transport is using
        encryption.
        """
        success = []
        self.connected.addCallback(lambda _: self.client.startTLS())
        def checkSecure(ignored):
            self.assertTrue(
                interfaces.ISSLTransport.providedBy(self.client.transport))
        self.connected.addCallback(checkSecure)
        self.connected.addCallback(self._cbStopClient)
        self.connected.addCallback(success.append)
        self.connected.addErrback(self._ebGeneral)

        d = self.loopback()
        d.addCallback(lambda x : self.failUnless(success))
        return defer.gatherResults([d, self.connected])


    def testFailedStartTLS(self):
        failure = []
        def breakServerTLS(ign):
            self.server.canStartTLS = False

        self.connected.addCallback(breakServerTLS)
        self.connected.addCallback(lambda ign: self.client.startTLS())
        self.connected.addErrback(lambda err: failure.append(err.trap(imap4.IMAP4Exception)))
        self.connected.addCallback(self._cbStopClient)
        self.connected.addErrback(self._ebGeneral)

        def check(ignored):
            self.failUnless(failure)
            self.assertIdentical(failure[0], imap4.IMAP4Exception)
        return self.loopback().addCallback(check)



class SlowMailbox(SimpleMailbox):
    howSlow = 2
    callLater = None
    fetchDeferred = None

    # Not a very nice implementation of fetch(), but it'll
    # do for the purposes of testing.
    def fetch(self, messages, uid):
        d = defer.Deferred()
        self.callLater(self.howSlow, d.callback, ())
        self.fetchDeferred.callback(None)
        return d

class Timeout(IMAP4HelperMixin, unittest.TestCase):

    def test_serverTimeout(self):
        """
        The *client* has a timeout mechanism which will close connections that
        are inactive for a period.
        """
        c = Clock()
        self.server.timeoutTest = True
        self.client.timeout = 5 #seconds
        self.client.callLater = c.callLater
        self.selectedArgs = None

        def login():
            d = self.client.login('testuser', 'password-test')
            c.advance(5)
            d.addErrback(timedOut)
            return d

        def timedOut(failure):
            self._cbStopClient(None)
            failure.trap(error.TimeoutError)

        d = self.connected.addCallback(strip(login))
        d.addErrback(self._ebGeneral)
        return defer.gatherResults([d, self.loopback()])


    def test_longFetchDoesntTimeout(self):
        """
        The connection timeout does not take effect during fetches.
        """
        c = Clock()
        SlowMailbox.callLater = c.callLater
        SlowMailbox.fetchDeferred = defer.Deferred()
        self.server.callLater = c.callLater
        SimpleServer.theAccount.mailboxFactory = SlowMailbox
        SimpleServer.theAccount.addMailbox('mailbox-test')

        self.server.setTimeout(1)

        def login():
            return self.client.login('testuser', 'password-test')
        def select():
            self.server.setTimeout(1)
            return self.client.select('mailbox-test')
        def fetch():
            return self.client.fetchUID('1:*')
        def stillConnected():
            self.assertNotEquals(self.server.state, 'timeout')

        def cbAdvance(ignored):
            for i in xrange(4):
                c.advance(.5)

        SlowMailbox.fetchDeferred.addCallback(cbAdvance)

        d1 = self.connected.addCallback(strip(login))
        d1.addCallback(strip(select))
        d1.addCallback(strip(fetch))
        d1.addCallback(strip(stillConnected))
        d1.addCallback(self._cbStopClient)
        d1.addErrback(self._ebGeneral)
        d = defer.gatherResults([d1, self.loopback()])
        return d


    def test_idleClientDoesDisconnect(self):
        """
        The *server* has a timeout mechanism which will close connections that
        are inactive for a period.
        """
        c = Clock()
        # Hook up our server protocol
        transport = StringTransportWithDisconnection()
        transport.protocol = self.server
        self.server.callLater = c.callLater
        self.server.makeConnection(transport)

        # Make sure we can notice when the connection goes away
        lost = []
        connLost = self.server.connectionLost
        self.server.connectionLost = lambda reason: (lost.append(None), connLost(reason))[1]

        # 2/3rds of the idle timeout elapses...
        c.pump([0.0] + [self.server.timeOut / 3.0] * 2)
        self.failIf(lost, lost)

        # Now some more
        c.pump([0.0, self.server.timeOut / 2.0])
        self.failUnless(lost)



class Disconnection(unittest.TestCase):
    def testClientDisconnectFailsDeferreds(self):
        c = imap4.IMAP4Client()
        t = StringTransportWithDisconnection()
        c.makeConnection(t)
        d = self.assertFailure(c.login('testuser', 'example.com'), error.ConnectionDone)
        c.connectionLost(error.ConnectionDone("Connection closed"))
        return d



class SynchronousMailbox(object):
    """
    Trivial, in-memory mailbox implementation which can produce a message
    synchronously.
    """
    def __init__(self, messages):
        self.messages = messages


    def fetch(self, msgset, uid):
        assert not uid, "Cannot handle uid requests."
        for msg in msgset:
            yield msg, self.messages[msg - 1]



class StringTransportConsumer(StringTransport):
    producer = None
    streaming = None

    def registerProducer(self, producer, streaming):
        self.producer = producer
        self.streaming = streaming



class Pipelining(unittest.TestCase):
    """
    Tests for various aspects of the IMAP4 server's pipelining support.
    """
    messages = [
        FakeyMessage({}, [], '', '0', None, None),
        FakeyMessage({}, [], '', '1', None, None),
        FakeyMessage({}, [], '', '2', None, None),
        ]

    def setUp(self):
        self.iterators = []

        self.transport = StringTransportConsumer()
        self.server = imap4.IMAP4Server(None, None, self.iterateInReactor)
        self.server.makeConnection(self.transport)


    def iterateInReactor(self, iterator):
        d = defer.Deferred()
        self.iterators.append((iterator, d))
        return d


    def tearDown(self):
        self.server.connectionLost(failure.Failure(error.ConnectionDone()))


    def test_synchronousFetch(self):
        """
        Test that pipelined FETCH commands which can be responded to
        synchronously are responded to correctly.
        """
        mailbox = SynchronousMailbox(self.messages)

        # Skip over authentication and folder selection
        self.server.state = 'select'
        self.server.mbox = mailbox

        # Get rid of any greeting junk
        self.transport.clear()

        # Here's some pipelined stuff
        self.server.dataReceived(
            '01 FETCH 1 BODY[]\r\n'
            '02 FETCH 2 BODY[]\r\n'
            '03 FETCH 3 BODY[]\r\n')

        # Flush anything the server has scheduled to run
        while self.iterators:
            for e in self.iterators[0][0]:
                break
            else:
                self.iterators.pop(0)[1].callback(None)

        # The bodies are empty because we aren't simulating a transport
        # exactly correctly (we have StringTransportConsumer but we never
        # call resumeProducing on its producer).  It doesn't matter: just
        # make sure the surrounding structure is okay, and that no
        # exceptions occurred.
        self.assertEqual(
            self.transport.value(),
            '* 1 FETCH (BODY[] )\r\n'
            '01 OK FETCH completed\r\n'
            '* 2 FETCH (BODY[] )\r\n'
            '02 OK FETCH completed\r\n'
            '* 3 FETCH (BODY[] )\r\n'
            '03 OK FETCH completed\r\n')



if ClientTLSContext is None:
    for case in (TLSTestCase,):
        case.skip = "OpenSSL not present"
elif interfaces.IReactorSSL(reactor, None) is None:
    for case in (TLSTestCase,):
        case.skip = "Reactor doesn't support SSL"



class IMAP4ServerFetchTestCase(unittest.TestCase):
    """
    This test case is for the FETCH tests that require
    a C{StringTransport}.
    """

    def setUp(self):
        self.transport = StringTransport()
        self.server = imap4.IMAP4Server()
        self.server.state = 'select'
        self.server.makeConnection(self.transport)


    def test_fetchWithPartialValidArgument(self):
        """
        If by any chance, extra bytes got appended at the end of of an valid
        FETCH arguments, the client should get a BAD - arguments invalid
        response.

        See U{RFC 3501<http://tools.ietf.org/html/rfc3501#section-6.4.5>},
        section 6.4.5,
        """
        # We need to clear out the welcome message.
        self.transport.clear()
        # Let's send out the faulty command.
        self.server.dataReceived("0001 FETCH 1 FULLL\r\n")
        expected = "0001 BAD Illegal syntax: Invalid Argument\r\n"
        self.assertEqual(self.transport.value(), expected)
        self.transport.clear()
        self.server.connectionLost(error.ConnectionDone("Connection closed"))
