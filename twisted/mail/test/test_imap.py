# -*- test-case-name: twisted.mail.test.test_imap -*-
# Copyright (c) 2001-2008 Twisted Matrix Laboratories.
# See LICENSE for details.


"""
Test case for twisted.mail.imap4
"""

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

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
from twisted.python import util
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


    def testEncode(self):
        for (input, output) in self.tests:
            self.assertEquals(input.encode('imap4-utf-7'), output)

    def testDecode(self):
        for (input, output) in self.tests:
            # XXX - Piece of *crap* 2.1
            self.assertEquals(input, imap4.decoder(output)[0])

    def testPrintableSingletons(self):
        # All printables represent themselves
        for o in range(0x20, 0x26) + range(0x27, 0x7f):
            self.failUnlessEqual(chr(o), chr(o).encode('imap4-utf-7'))
            self.failUnlessEqual(chr(o), chr(o).decode('imap4-utf-7'))
        self.failUnlessEqual('&'.encode('imap4-utf-7'), '&-')
        self.failUnlessEqual('&-'.decode('imap4-utf-7'), '&')

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
            self.assertEquals(
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

            self.assertEquals(
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

            self.assertEquals(
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
    def testFileProducer(self):
        b = (('x' * 1) + ('y' * 1) + ('z' * 1)) * 10
        c = BufferingConsumer()
        f = StringIO(b)
        p = imap4.FileProducer(f)
        d = p.beginProducing(c)

        def cbProduced(result):
            self.failUnlessIdentical(result, p)
            self.assertEquals(
                ('{%d}\r\n' % len(b))+ b,
                ''.join(c.buffer))
        return d.addCallback(cbProduced)

    def testWildcard(self):
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

    def testWildcardNoDelim(self):
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

    def testHeaderFormatter(self):
        cases = [
            ({'Header1': 'Value1', 'Header2': 'Value2'}, 'Header2: Value2\r\nHeader1: Value1\r\n'),
        ]

        for (input, output) in cases:
            self.assertEquals(imap4._formatHeaders(input), output)

    def testMessageSet(self):
        m1 = MessageSet()
        m2 = MessageSet()

        self.assertEquals(m1, m2)

        m1 = m1 + (1, 3)
        self.assertEquals(len(m1), 3)
        self.assertEquals(list(m1), [1, 2, 3])

        m2 = m2 + (1, 3)
        self.assertEquals(m1, m2)
        self.assertEquals(list(m1 + m2), [1, 2, 3])

    def testQuotedSplitter(self):
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
            self.assertEquals(imap4.splitQuoted(case), expected)


    def testStringCollapser(self):
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
            self.assertEquals(imap4.collapseStrings(case), expected)

    def testParenParser(self):
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
        ]

        for (case, expected) in zip(cases, answers):
            self.assertEquals(imap4.parseNestedParens(case), [expected])

        # XXX This code used to work, but changes occurred within the
        # imap4.py module which made it no longer necessary for *all* of it
        # to work.  In particular, only the part that makes
        # 'BODY.PEEK[HEADER.FIELDS.NOT (Subject Bcc Cc)]' come out correctly
        # no longer needs to work.  So, I am loathe to delete the entire
        # section of the test. --exarkun
        #

#        for (case, expected) in zip(answers, cases):
#            self.assertEquals('(' + imap4.collapseNestedLists(case) + ')', expected)

    def testFetchParserSimple(self):
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
            self.assertEquals(len(p.result), 1)
            self.failUnless(isinstance(p.result[0], getattr(p, outp)))

    def testFetchParserMacros(self):
        cases = [
            ['ALL', (4, ['flags', 'internaldate', 'rfc822.size', 'envelope'])],
            ['FULL', (5, ['flags', 'internaldate', 'rfc822.size', 'envelope', 'body'])],
            ['FAST', (3, ['flags', 'internaldate', 'rfc822.size'])],
        ]

        for (inp, outp) in cases:
            p = imap4._FetchParser()
            p.parseString(inp)
            self.assertEquals(len(p.result), outp[0])
            p = [str(p).lower() for p in p.result]
            p.sort()
            outp[1].sort()
            self.assertEquals(p, outp[1])

    def testFetchParserBody(self):
        P = imap4._FetchParser

        p = P()
        p.parseString('BODY')
        self.assertEquals(len(p.result), 1)
        self.failUnless(isinstance(p.result[0], p.Body))
        self.assertEquals(p.result[0].peek, False)
        self.assertEquals(p.result[0].header, None)
        self.assertEquals(str(p.result[0]), 'BODY')

        p = P()
        p.parseString('BODY.PEEK')
        self.assertEquals(len(p.result), 1)
        self.failUnless(isinstance(p.result[0], p.Body))
        self.assertEquals(p.result[0].peek, True)
        self.assertEquals(str(p.result[0]), 'BODY')

        p = P()
        p.parseString('BODY[]')
        self.assertEquals(len(p.result), 1)
        self.failUnless(isinstance(p.result[0], p.Body))
        self.assertEquals(p.result[0].empty, True)
        self.assertEquals(str(p.result[0]), 'BODY[]')

        p = P()
        p.parseString('BODY[HEADER]')
        self.assertEquals(len(p.result), 1)
        self.failUnless(isinstance(p.result[0], p.Body))
        self.assertEquals(p.result[0].peek, False)
        self.failUnless(isinstance(p.result[0].header, p.Header))
        self.assertEquals(p.result[0].header.negate, True)
        self.assertEquals(p.result[0].header.fields, ())
        self.assertEquals(p.result[0].empty, False)
        self.assertEquals(str(p.result[0]), 'BODY[HEADER]')

        p = P()
        p.parseString('BODY.PEEK[HEADER]')
        self.assertEquals(len(p.result), 1)
        self.failUnless(isinstance(p.result[0], p.Body))
        self.assertEquals(p.result[0].peek, True)
        self.failUnless(isinstance(p.result[0].header, p.Header))
        self.assertEquals(p.result[0].header.negate, True)
        self.assertEquals(p.result[0].header.fields, ())
        self.assertEquals(p.result[0].empty, False)
        self.assertEquals(str(p.result[0]), 'BODY[HEADER]')

        p = P()
        p.parseString('BODY[HEADER.FIELDS (Subject Cc Message-Id)]')
        self.assertEquals(len(p.result), 1)
        self.failUnless(isinstance(p.result[0], p.Body))
        self.assertEquals(p.result[0].peek, False)
        self.failUnless(isinstance(p.result[0].header, p.Header))
        self.assertEquals(p.result[0].header.negate, False)
        self.assertEquals(p.result[0].header.fields, ['SUBJECT', 'CC', 'MESSAGE-ID'])
        self.assertEquals(p.result[0].empty, False)
        self.assertEquals(str(p.result[0]), 'BODY[HEADER.FIELDS (Subject Cc Message-Id)]')

        p = P()
        p.parseString('BODY.PEEK[HEADER.FIELDS (Subject Cc Message-Id)]')
        self.assertEquals(len(p.result), 1)
        self.failUnless(isinstance(p.result[0], p.Body))
        self.assertEquals(p.result[0].peek, True)
        self.failUnless(isinstance(p.result[0].header, p.Header))
        self.assertEquals(p.result[0].header.negate, False)
        self.assertEquals(p.result[0].header.fields, ['SUBJECT', 'CC', 'MESSAGE-ID'])
        self.assertEquals(p.result[0].empty, False)
        self.assertEquals(str(p.result[0]), 'BODY[HEADER.FIELDS (Subject Cc Message-Id)]')

        p = P()
        p.parseString('BODY.PEEK[HEADER.FIELDS.NOT (Subject Cc Message-Id)]')
        self.assertEquals(len(p.result), 1)
        self.failUnless(isinstance(p.result[0], p.Body))
        self.assertEquals(p.result[0].peek, True)
        self.failUnless(isinstance(p.result[0].header, p.Header))
        self.assertEquals(p.result[0].header.negate, True)
        self.assertEquals(p.result[0].header.fields, ['SUBJECT', 'CC', 'MESSAGE-ID'])
        self.assertEquals(p.result[0].empty, False)
        self.assertEquals(str(p.result[0]), 'BODY[HEADER.FIELDS.NOT (Subject Cc Message-Id)]')

        p = P()
        p.parseString('BODY[1.MIME]<10.50>')
        self.assertEquals(len(p.result), 1)
        self.failUnless(isinstance(p.result[0], p.Body))
        self.assertEquals(p.result[0].peek, False)
        self.failUnless(isinstance(p.result[0].mime, p.MIME))
        self.assertEquals(p.result[0].part, (0,))
        self.assertEquals(p.result[0].partialBegin, 10)
        self.assertEquals(p.result[0].partialLength, 50)
        self.assertEquals(p.result[0].empty, False)
        self.assertEquals(str(p.result[0]), 'BODY[1.MIME]<10.50>')

        p = P()
        p.parseString('BODY.PEEK[1.3.9.11.HEADER.FIELDS.NOT (Message-Id Date)]<103.69>')
        self.assertEquals(len(p.result), 1)
        self.failUnless(isinstance(p.result[0], p.Body))
        self.assertEquals(p.result[0].peek, True)
        self.failUnless(isinstance(p.result[0].header, p.Header))
        self.assertEquals(p.result[0].part, (0, 2, 8, 10))
        self.assertEquals(p.result[0].header.fields, ['MESSAGE-ID', 'DATE'])
        self.assertEquals(p.result[0].partialBegin, 103)
        self.assertEquals(p.result[0].partialLength, 69)
        self.assertEquals(p.result[0].empty, False)
        self.assertEquals(str(p.result[0]), 'BODY[1.3.9.11.HEADER.FIELDS.NOT (Message-Id Date)]<103.69>')


    def testFiles(self):
        inputStructure = [
            'foo', 'bar', 'baz', StringIO('this is a file\r\n'), 'buz'
        ]

        output = '"foo" "bar" "baz" {16}\r\nthis is a file\r\n "buz"'

        self.assertEquals(imap4.collapseNestedLists(inputStructure), output)

    def testQuoteAvoider(self):
        input = [
            'foo', imap4.DontQuoteMe('bar'), "baz", StringIO('this is a file\r\n'),
            imap4.DontQuoteMe('buz'), ""
        ]

        output = '"foo" bar "baz" {16}\r\nthis is a file\r\n buz ""'

        self.assertEquals(imap4.collapseNestedLists(input), output)

    def testLiterals(self):
        cases = [
            ('({10}\r\n0123456789)', [['0123456789']]),
        ]

        for (case, expected) in cases:
            self.assertEquals(imap4.parseNestedParens(case), expected)

    def testQueryBuilder(self):
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
            self.assertEquals(query, expected)

    def testIdListParser(self):
        inputs = [
            '1:*',
            '5:*',
            '1:2,5:*',
            '1',
            '1,2',
            '1,3,5',
            '1:10',
            '1:10,11',
            '1:5,10:20',
            '1,5:10',
            '1,5:10,15:20',
            '1:10,15,20:25',
        ]

        outputs = [
            MessageSet(1, None),
            MessageSet(5, None),
            MessageSet(5, None) + MessageSet(1, 2),
            MessageSet(1),
            MessageSet(1, 2),
            MessageSet(1) + MessageSet(3) + MessageSet(5),
            MessageSet(1, 10),
            MessageSet(1, 11),
            MessageSet(1, 5) + MessageSet(10, 20),
            MessageSet(1) + MessageSet(5, 10),
            MessageSet(1) + MessageSet(5, 10) + MessageSet(15, 20),
            MessageSet(1, 10) + MessageSet(15) + MessageSet(20, 25),
        ]

        lengths = [
            None, None, None,
            1, 2, 3, 10, 11, 16, 7, 13, 17,
        ]

        for (input, expected) in zip(inputs, outputs):
            self.assertEquals(imap4.parseIdList(input), expected)

        for (input, expected) in zip(inputs, lengths):
            try:
                L = len(imap4.parseIdList(input))
            except TypeError:
                L = None
            self.assertEquals(L, expected,
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

    def fetchBodyParts(self, message, parts):
        """Fetch some parts of the body.

        @param message: message with parts to fetch
        @type message: C{str}
        @param parts: a list of int/str
        @type parts: C{list}
        """
        cmd = "%s (BODY[%s]" % (message, parts[0])
        for p in parts[1:]:
            cmd += " BODY[%s]" % p
        cmd += ")"
        d = self.sendCommand(imap4.Command("FETCH", cmd,
                                           wantResponse=("FETCH",)))
        d.addCallback(self.__cb_fetchBodyParts)
        return d

    def __cb_fetchBodyParts(self, (lines, last)):
        info = {}
        for line in lines:
            parts = line.split(None, 2)
            if len(parts) == 3:
                if parts[1] == "FETCH":
                    try:
                        mail_id = int(parts[0])
                    except ValueError:
                        raise imap4.IllegalServerResponse, line
                    else:
                        body_parts = imap4.parseNestedParens(parts[2])[0]
                        dict_parts = {}
                        for i in range(len(body_parts)/3):
                            dict_parts[body_parts[3*i+1][0]] = body_parts[3*i+2]
                        info[mail_id] = dict_parts
        return info

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
        failure.printTraceback(open('failure.log', 'w'))
        failure.printTraceback()
        raise failure.value

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
        return d.addCallback(lambda _: self.assertEquals(expected, caps))

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

        return d.addCallback(lambda _: self.assertEquals(expCap, caps))

    def testLogout(self):
        self.loggedOut = 0
        def logout():
            def setLoggedOut():
                self.loggedOut = 1
            self.client.logout().addCallback(strip(setLoggedOut))
        self.connected.addCallback(strip(logout)).addErrback(self._ebGeneral)
        d = self.loopback()
        return d.addCallback(lambda _: self.assertEquals(self.loggedOut, 1))

    def testNoop(self):
        self.responses = None
        def noop():
            def setResponses(responses):
                self.responses = responses
                self.server.transport.loseConnection()
            self.client.noop().addCallback(setResponses)
        self.connected.addCallback(strip(noop)).addErrback(self._ebGeneral)
        d = self.loopback()
        return d.addCallback(lambda _: self.assertEquals(self.responses, []))

    def testLogin(self):
        def login():
            d = self.client.login('testuser', 'password-test')
            d.addCallback(self._cbStopClient)
        d1 = self.connected.addCallback(strip(login)).addErrback(self._ebGeneral)
        d = defer.gatherResults([d1, self.loopback()])
        return d.addCallback(self._cbTestLogin)

    def _cbTestLogin(self, ignored):
        self.assertEquals(self.server.account, SimpleServer.theAccount)
        self.assertEquals(self.server.state, 'auth')

    def testFailedLogin(self):
        def login():
            d = self.client.login('testuser', 'wrong-password')
            d.addBoth(self._cbStopClient)

        d1 = self.connected.addCallback(strip(login)).addErrback(self._ebGeneral)
        d2 = self.loopback()
        d = defer.gatherResults([d1, d2])
        return d.addCallback(self._cbTestFailedLogin)

    def _cbTestFailedLogin(self, ignored):
        self.assertEquals(self.server.account, None)
        self.assertEquals(self.server.state, 'unauth')


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
        self.assertEquals(self.server.account, SimpleServer.theAccount)
        self.assertEquals(self.server.state, 'auth')


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
        d.addCallback(lambda _: self.assertEquals(self.namespaceArgs,
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
        self.assertEquals(self.server.mbox, mbox)
        self.assertEquals(self.selectedArgs, {
            'EXISTS': 9, 'RECENT': 3, 'UIDVALIDITY': 42,
            'FLAGS': ('\\Flag1', 'Flag2', '\\AnotherSysFlag', 'LastFlag'),
            'READ-WRITE': 1
        })

    def testExamine(self):
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
        self.assertEquals(self.server.mbox, mbox)
        self.assertEquals(self.examinedArgs, {
            'EXISTS': 9, 'RECENT': 3, 'UIDVALIDITY': 42,
            'FLAGS': ('\\Flag1', 'Flag2', '\\AnotherSysFlag', 'LastFlag'),
            'READ-WRITE': 0
        })

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
        self.assertEquals(self.result, [1] * len(succeed) + [0] * len(fail))
        mbox = SimpleServer.theAccount.mailboxes.keys()
        answers = ['inbox', 'testbox', 'test/box', 'test', 'test/box/box']
        mbox.sort()
        answers.sort()
        self.assertEquals(mbox, [a.upper() for a in answers])

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
                      self.assertEquals(SimpleServer.theAccount.mailboxes.keys(), []))
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
        d.addCallback(lambda _: self.assertEquals(str(self.failure.value),
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
                      self.assertEquals(str(self.failure.value), expected))
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
                      self.assertEquals(SimpleServer.theAccount.mailboxes.keys(),
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
        self.assertEquals(mboxes, [s.upper() for s in expected])

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
                      self.assertEquals(SimpleServer.theAccount.subscriptions,
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
                      self.assertEquals(SimpleServer.theAccount.subscriptions,
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
        d.addCallback(lambda listed: self.assertEquals(
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
        d.addCallback(self.assertEquals,
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
        d.addCallback(lambda _: self.assertEquals(
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
        self.assertEquals(
            self.statused, None
        )
        self.assertEquals(
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
        self.assertEquals(1, len(mb.messages))
        self.assertEquals(
            (['\\SEEN', '\\DELETED'], 'Tue, 17 Jun 2003 11:22:16 -0600 (MDT)', 0),
            mb.messages[0][1:]
        )
        self.assertEquals(open(infile).read(), mb.messages[0][0].getvalue())

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
        self.assertEquals(1, len(mb.messages))
        self.assertEquals(
            (['\\SEEN'], 'Right now', 0),
            mb.messages[0][1:]
        )
        self.assertEquals(open(infile).read(), mb.messages[0][0].getvalue())

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
        self.assertEquals(len(m.messages), 1)
        self.assertEquals(m.messages[0], ('Message 2', ('AnotherFlag',), None, 1))
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
        self.assertEquals(len(m.messages), 1)
        self.assertEquals(m.messages[0], ('Message 2', ('AnotherFlag',), None, 1))

        self.assertEquals(self.results, [0, 2])

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
        self.assertEquals(self.authenticated, 1)
        self.assertEquals(self.server.account, self.account)

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
        self.assertEquals(self.authenticated, -1)
        self.assertEquals(self.server.account, None)

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
        self.assertEquals(self.authenticated, 1)
        self.assertEquals(self.server.account, self.account)

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
        self.assertEquals(self.authenticated, -1)
        self.assertEquals(self.server.account, None)

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
        self.assertEquals(self.authenticated, 1)
        self.assertEquals(self.server.account, self.account)

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
        self.assertEquals(self.authenticated, -1)
        self.assertEquals(self.server.account, None)


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
        self.assertEquals(E, [['modeChanged', 1]])

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
        self.assertEquals(E, [['modeChanged', 0]])

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
        self.assertEquals(E, expect)

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
        self.assertEquals(E, [['newMessages', 10, None]])

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
        self.assertEquals(E, [['newMessages', None, 10]])

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
        self.assertEquals(E, [['newMessages', 20, None], ['newMessages', None, 10]])


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
        self.assertEquals(transport.value(), "+ Ready for 8 octets of text\r\n")

        transport.clear()
        self.server.dataReceived("testuser {13}\r\n")
        self.assertEquals(transport.value(), "+ Ready for 13 octets of text\r\n")

        transport.clear()
        self.server.dataReceived("password-test\r\n")
        self.assertEquals(transport.value(), "01 OK LOGIN succeeded\r\n")
        self.assertEquals(self.server.state, 'auth')

        self.server.connectionLost(error.ConnectionDone("Connection done."))

    def testUnsolicitedResponseMixedWithSolicitedResponse(self):

        class StillSimplerClient(imap4.IMAP4Client):
            events = []
            def flagsChanged(self, newFlags):
                self.events.append(['flagsChanged', newFlags])

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
            self.assertEquals(res, {
                1: [['BODY', ['HEADER.FIELDS', ['SUBJECT']],
                    'Subject: Suprise for your woman...\r\n\r\n']],
                2: [['BODY', ['HEADER.FIELDS', ['SUBJECT']],
                    'Subject: What you been doing. Order your meds here . ,. handcuff madsen\r\n\r\n']]
            })

            self.assertEquals(c.events, [['flagsChanged', {1: ['\\Seen']}]])

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



class FakeyServer(imap4.IMAP4Server):
    state = 'select'
    timeout = None

    def sendServerGreeting(self):
        pass

class FakeyMessage:
    implements(imap4.IMessage)

    def __init__(self, headers, flags, date, body, uid, subpart):
        self.headers = headers
        self.flags = flags
        self.body = StringIO(body)
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
        return self.body

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
            self.assertEquals(self.result, self.expected)
            self.assertEquals(self.storeArgs, self.expectedArgs)
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
        d.addCallback(lambda x : self.assertEquals(self.result, self.expected))
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

    def testFetchBodyStructure(self, uid=0):
        self.function = self.client.fetchBodyStructure
        self.messages = '3:9,10:*'
        self.msgObjs = [FakeyMessage({
                'content-type': 'text/plain; name=thing; key="value"',
                'content-id': 'this-is-the-content-id',
                'content-description': 'describing-the-content-goes-here!',
                'content-transfer-encoding': '8BIT',
            }, (), '', 'Body\nText\nGoes\nHere\n', 919293, None)]
        self.expected = {0: {'BODYSTRUCTURE': [
            'text', 'plain', [['name', 'thing'], ['key', 'value']],
            'this-is-the-content-id', 'describing-the-content-goes-here!',
            '8BIT', '20', '4', None, None, None]}}
        return self._fetchWork(uid)

    def testFetchBodyStructureUID(self):
        return self.testFetchBodyStructure(1)

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
                [None, None, [], None, None, None,
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
                ['text', 'plain', [], None, None, None,
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
                ['message', 'rfc822', [], None, None, None,
                    '12', [None, None, [[None, None, None]],
                    [[None, None, None]], None, None, None,
                    None, None, None], ['image', 'jpg', [],
                    None, None, None, '14'], '1'
                ]
            }
        }

        return self._fetchWork(uid)

    def testFetchSimplifiedBodyRFC822UID(self):
        return self.testFetchSimplifiedBodyRFC822(1)

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
        self.function = self.client.fetchBodyParts
        self.messages = '1'
        parts = [1, 2]
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
            0: {'1': innerBody1, '2': innerBody2},
        }

        def result(R):
            self.result = R

        self.connected.addCallback(lambda _: self.function(self.messages, parts))
        self.connected.addCallback(result)
        self.connected.addCallback(self._cbStopClient)
        self.connected.addErrback(self._ebGeneral)

        d = loopback.loopbackTCP(self.server, self.client, noisy=False)
        d.addCallback(lambda ign: self.assertEquals(self.result, self.expected))
        return d


    def test_fetchBodyPartOfNonMultipart(self):
        """
        Single-part messages have an implicit first part which clients
        should be able to retrieve explicitly.  Test that a client
        requesting part 1 of a text/plain message receives the body of the
        text/plain part.
        """
        self.function = self.client.fetchBodyParts
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

        self.expected = {
            0: {'1': outerBody},
        }

        def result(R):
            self.result = R

        self.connected.addCallback(lambda _: self.function(self.messages, parts))
        self.connected.addCallback(result)
        self.connected.addCallback(self._cbStopClient)
        self.connected.addErrback(self._ebGeneral)

        d = loopback.loopbackTCP(self.server, self.client, noisy=False)
        d.addCallback(lambda ign: self.assertEquals(self.result, self.expected))
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
                'BODY': [None, None, [], None, None, None, '6']},
            1: {'FLAGS': ['\\One', '\\Two', 'Three'],
                'INTERNALDATE': '14-Apr-2003 19:43:44 -0400',
                'RFC822.SIZE': '12',
                'ENVELOPE': [None, None, [[None, None, None]], [[None, None, None]], None, None, None, None, None, None],
                'BODY': [None, None, [], None, None, None, '12']},
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

            self.assertEquals(self.result, self.expected)
            self.assertEquals(self.uid, self.server_received_uid)
            self.assertEquals(
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

            self.assertEquals(self.result, self.expected)
            self.assertEquals(self.uid, self.server_received_uid)
            self.assertEquals(self.parts, self.server_received_parts)
            self.assertEquals(imap4.parseIdList(self.messages),
                              imap4.parseIdList(self.server_received_messages))

        d = loopback.loopbackTCP(self.server, self.client, noisy=False)
        d.addCallback(check)
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
                self.assertEquals(a[0].read(), "open")
                self.assertEquals(a[1], "flags")
                self.assertEquals(a[2], "internaldate")

            for (status, result) in results:
                self.failUnless(status)
                self.assertEquals(result, None)

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
                self.assertEquals(a[1], ())
                self.assertEquals(a[2], "Date")

            seen.sort()
            exp = ["Header-Counter: %d\r\n\r\nBody %d" % (i, i) for i in range(1, 11)]
            exp.sort()
            self.assertEquals(seen, exp)

            for (status, result) in results:
                self.failUnless(status)
                self.assertEquals(result, None)

        return d.addCallback(cbCopy)

    def testMessageCopier(self):
        s = imap4.IMAP4Server()

        # See above comment
        f = s._IMAP4Server__cbCopy

        m = MessageCopierMailbox()
        msgs = [object() for i in range(1, 11)]
        d = f([im for im in zip(range(1, 11), msgs)], 'tag', m)

        def cbCopy(results):
            self.assertEquals(results, zip([1] * 10, range(1, 11)))
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
            self.assertEquals(self.server.startedTLS, True)
            self.assertEquals(self.client.startedTLS, True)
            self.assertEquals(len(called), len(methods))
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
        d.addCallback(lambda x : self.assertEquals(len(success), 1))
        return d

    def testStartTLS(self):
        success = []
        self.connected.addCallback(lambda _: self.client.startTLS())
        self.connected.addCallback(lambda _: self.assertNotEquals(-1, self.client.transport.__class__.__name__.find('TLS')))
        self.connected.addCallback(self._cbStopClient)
        self.connected.addCallback(success.append)
        self.connected.addErrback(self._ebGeneral)

        d = self.loopback()
        d.addCallback(lambda x : self.failUnless(success))
        return d

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
        self.assertEquals(
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
