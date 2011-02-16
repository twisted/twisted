# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.web2.http_headers}.
"""

from twisted.trial import unittest
import random, time

from twisted.web2 import http_headers
from twisted.web2.http_headers import Cookie, HeaderHandler, quoteString, generateKeyValues
from twisted.python import util

class parsedvalue:
    """Marker class"""
    def __init__(self, raw):
        self.raw = raw

    def __eq__(self, other):
        return isinstance(other, parsedvalue) and other.raw == self.raw

class HeadersAPITest(unittest.TestCase):
    """Make sure the public API exists and works."""
    def testRaw(self):
        rawvalue = ("value1", "value2")
        h = http_headers.Headers(handler=HeaderHandler(parsers={}, generators={}))
        h.setRawHeaders("test", rawvalue)
        self.assertEquals(h.hasHeader("test"), True)
        self.assertEquals(h.getRawHeaders("test"), rawvalue)
        self.assertEquals(list(h.getAllRawHeaders()), [('Test', rawvalue)])

        self.assertEquals(h.getRawHeaders("foobar"), None)
        h.removeHeader("test")
        self.assertEquals(h.getRawHeaders("test"), None)

    def testParsed(self):
        parsed = parsedvalue(("value1", "value2"))
        h = http_headers.Headers(handler=HeaderHandler(parsers={}, generators={}))

        h.setHeader("test", parsed)
        self.assertEquals(h.hasHeader("test"), True)
        self.assertEquals(h.getHeader("test"), parsed)

        self.assertEquals(h.getHeader("foobar"), None)
        h.removeHeader("test")
        self.assertEquals(h.getHeader("test"), None)

    def testParsedAndRaw(self):
        def parse(raw):
            return parsedvalue(raw)

        def generate(parsed):
            return parsed.raw

        rawvalue = ("value1", "value2")
        rawvalue2 = ("value3", "value4")
        handler = HeaderHandler(parsers={'test':(parse,)},
                                generators={'test':(generate,)})

        h = http_headers.Headers(handler=handler)
        h.setRawHeaders("test", rawvalue)
        self.assertEquals(h.getHeader("test"), parsedvalue(rawvalue))

        h.setHeader("test", parsedvalue(rawvalue2))
        self.assertEquals(h.getRawHeaders("test"), rawvalue2)

        # Check the initializers
        h = http_headers.Headers(rawHeaders={"test": rawvalue},
                                 handler=handler)
        self.assertEquals(h.getHeader("test"), parsedvalue(rawvalue))

        h = http_headers.Headers({"test": parsedvalue(rawvalue2)},
                                 handler=handler)
        self.assertEquals(h.getRawHeaders("test"), rawvalue2)

    def testImmutable(self):
        h = http_headers.Headers(handler=HeaderHandler(parsers={}, generators={}))

        h.makeImmutable()
        self.assertRaises(AttributeError, h.setRawHeaders, "test", [1])
        self.assertRaises(AttributeError, h.setHeader, "test", 1)
        self.assertRaises(AttributeError, h.removeHeader, "test")

class TokenizerTest(unittest.TestCase):
    """Test header list parsing functions."""

    def testParse(self):
        parser = lambda val: list(http_headers.tokenize([val,]))
        Token = http_headers.Token
        tests = (('foo,bar', ['foo', Token(','), 'bar']),
                 ('FOO,BAR', ['foo', Token(','), 'bar']),
                 (' \t foo  \t bar  \t  ,  \t baz   ', ['foo', Token(' '), 'bar', Token(','), 'baz']),
                 ('()<>@,;:\\/[]?={}', [Token('('), Token(')'), Token('<'), Token('>'), Token('@'), Token(','), Token(';'), Token(':'), Token('\\'), Token('/'), Token('['), Token(']'), Token('?'), Token('='), Token('{'), Token('}')]),
                 (' "foo" ', ['foo']),
                 ('"FOO(),\\"BAR,"', ['FOO(),"BAR,']))

        raiseTests = ('"open quote', '"ending \\', "control character: \x127", "\x00", "\x1f")

        for test,result in tests:
            self.assertEquals(parser(test), result)
        for test in raiseTests:
            self.assertRaises(ValueError, parser, test)

    def testGenerate(self):
        pass

    def testRoundtrip(self):
        pass

def atSpecifiedTime(when, func):
    def inner(*a, **kw):
        orig = time.time
        time.time = lambda: when
        try:
            return func(*a, **kw)
        finally:
            time.time = orig
    return util.mergeFunctionMetadata(func, inner)

def parseHeader(name, val):
    head = http_headers.Headers(handler=http_headers.DefaultHTTPHandler)
    head.setRawHeaders(name,val)
    return head.getHeader(name)
parseHeader = atSpecifiedTime(999999990, parseHeader) # Sun, 09 Sep 2001 01:46:30 GMT

def generateHeader(name, val):
    head = http_headers.Headers(handler=http_headers.DefaultHTTPHandler)
    head.setHeader(name, val)
    return head.getRawHeaders(name)
generateHeader = atSpecifiedTime(999999990, generateHeader) # Sun, 09 Sep 2001 01:46:30 GMT


class HeaderParsingTestBase(unittest.TestCase):
    def runRoundtripTest(self, headername, table):
        """
        Perform some assertions about the behavior of parsing and
        generating HTTP headers.  Specifically: parse an HTTP header
        value, assert that the parsed form contains all the available
        information with the correct structure; generate the HTTP
        header value from the parsed form, assert that it contains
        certain literal strings; finally, re-parse the generated HTTP
        header value and assert that the resulting structured data is
        the same as the first-pass parsed form.

        @type headername: C{str}
        @param headername: The name of the HTTP header L{table} contains values for.

        @type table: A sequence of tuples describing inputs to and
        outputs from header parsing and generation.  The tuples may be
        either 2 or 3 elements long.  In either case: the first
        element is a string representing an HTTP-format header value;
        the second element is a dictionary mapping names of parameters
        to values of those parameters (the parsed form of the header).
        If there is a third element, it is a list of strings which
        must occur exactly in the HTTP header value
        string which is re-generated from the parsed form.
        """
        for row in table:
            if len(row) == 2:
                rawHeaderInput, parsedHeaderData = row
                requiredGeneratedElements = []
            elif len(row) == 3:
                rawHeaderInput, parsedHeaderData, requiredGeneratedElements = row


            assert isinstance(requiredGeneratedElements, list)

            # parser
            parsed = parseHeader(headername, [rawHeaderInput,])
            self.assertEquals(parsed, parsedHeaderData)

            regeneratedHeaderValue = generateHeader(headername, parsed)

            if requiredGeneratedElements:
                # generator
                for regeneratedElement in regeneratedHeaderValue:
                    reqEle = requiredGeneratedElements[regeneratedHeaderValue.index(regeneratedElement)]
                    elementIndex = regeneratedElement.find(reqEle)
                    self.assertNotEqual(
                        elementIndex, -1,
                        "%r did not appear in generated HTTP header %r: %r" % (reqEle,
                                                                               headername,
                                                                               regeneratedElement))

            # parser/generator
            reparsed = parseHeader(headername, regeneratedHeaderValue)
            self.assertEquals(parsed, reparsed)


    def invalidParseTest(self, headername, values):
        for val in values:
            parsed = parseHeader(headername, val)
            self.assertEquals(parsed, None)

class GeneralHeaderParsingTests(HeaderParsingTestBase):
    def testCacheControl(self):
        table = (
            ("no-cache",
             {'no-cache':None}),
            ("no-cache, no-store, max-age=5, max-stale=3, min-fresh=5, no-transform, only-if-cached, blahblah-extension-thingy",
             {'no-cache': None,
              'no-store': None,
              'max-age':5,
              'max-stale':3,
              'min-fresh':5,
              'no-transform':None,
              'only-if-cached':None,
              'blahblah-extension-thingy':None}),
            ("max-stale",
             {'max-stale':None}),
            ("public, private, no-cache, no-store, no-transform, must-revalidate, proxy-revalidate, max-age=5, s-maxage=10, blahblah-extension-thingy",
             {'public':None,
              'private':None,
              'no-cache':None,
              'no-store':None,
              'no-transform':None,
              'must-revalidate':None,
              'proxy-revalidate':None,
              'max-age':5,
              's-maxage':10,
              'blahblah-extension-thingy':None}),
            ('private="Set-Cookie, Set-Cookie2", no-cache="PROXY-AUTHENTICATE"',
             {'private': ['set-cookie', 'set-cookie2'],
              'no-cache': ['proxy-authenticate']},
             ['private="Set-Cookie, Set-Cookie2"', 'no-cache="Proxy-Authenticate"']),
            )
        self.runRoundtripTest("Cache-Control", table)

    def testConnection(self):
        table = (
            ("close", ['close',]),
            ("close, foo-bar", ['close', 'foo-bar'])
            )
        self.runRoundtripTest("Connection", table)

    def testDate(self):
        # Don't need major tests since the datetime parser has its own tests
        self.runRoundtripTest("Date", (("Sun, 09 Sep 2001 01:46:40 GMT", 1000000000),))

#     def testPragma(self):
#         fail

#     def testTrailer(self):
#         fail

    def testTransferEncoding(self):
        table = (
            ('chunked', ['chunked']),
            ('gzip, chunked', ['gzip', 'chunked'])
            )
        self.runRoundtripTest("Transfer-Encoding", table)

#     def testUpgrade(self):
#         fail

#     def testVia(self):
#         fail

#     def testWarning(self):
#         fail

class RequestHeaderParsingTests(HeaderParsingTestBase):
    #FIXME test ordering too.
    def testAccept(self):
        table = (
            ("audio/*;q=0.2, audio/basic",
             {http_headers.MimeType('audio', '*'): 0.2,
              http_headers.MimeType('audio', 'basic'): 1.0}),

            ("text/plain;q=0.5, text/html, text/x-dvi;q=0.8, text/x-c",
             {http_headers.MimeType('text', 'plain'): 0.5,
              http_headers.MimeType('text', 'html'): 1.0,
              http_headers.MimeType('text', 'x-dvi'): 0.8,
              http_headers.MimeType('text', 'x-c'): 1.0}),

            ("text/*, text/html, text/html;level=1, */*",
             {http_headers.MimeType('text', '*'): 1.0,
              http_headers.MimeType('text', 'html'): 1.0,
              http_headers.MimeType('text', 'html', (('level', '1'),)): 1.0,
              http_headers.MimeType('*', '*'): 1.0}),

       ("text/*;q=0.3, text/html;q=0.7, text/html;level=1, text/html;level=2;q=0.4, */*;q=0.5",
             {http_headers.MimeType('text', '*'): 0.3,
              http_headers.MimeType('text', 'html'): 0.7,
              http_headers.MimeType('text', 'html', (('level', '1'),)): 1.0,
              http_headers.MimeType('text', 'html', (('level', '2'),)): 0.4,
              http_headers.MimeType('*', '*'): 0.5}),
            )

        self.runRoundtripTest("Accept", table)


    def testAcceptCharset(self):
        table = (
            ("iso-8859-5, unicode-1-1;q=0.8",
             {'iso-8859-5': 1.0, 'iso-8859-1': 1.0, 'unicode-1-1': 0.8},
             ["iso-8859-5", "unicode-1-1;q=0.8", "iso-8859-1"]),
            ("iso-8859-1;q=0.7",
             {'iso-8859-1': 0.7}),
            ("*;q=.7",
             {'*': 0.7},
             ["*;q=0.7"]),
            ("",
             {'iso-8859-1': 1.0},
             ["iso-8859-1"]), # Yes this is an actual change -- we'll say that's okay. :)
            )
        self.runRoundtripTest("Accept-Charset", table)

    def testAcceptEncoding(self):
        table = (
            ("compress, gzip",
             {'compress': 1.0, 'gzip': 1.0, 'identity': 0.0001}),
            ("",
             {'identity': 0.0001}),
            ("*",
             {'*': 1}),
            ("compress;q=0.5, gzip;q=1.0",
             {'compress': 0.5, 'gzip': 1.0, 'identity': 0.0001},
             ["compress;q=0.5", "gzip"]),
            ("gzip;q=1.0, identity;q=0.5, *;q=0",
             {'gzip': 1.0, 'identity': 0.5, '*':0},
             ["gzip", "identity;q=0.5", "*;q=0"]),
            )
        self.runRoundtripTest("Accept-Encoding", table)

    def testAcceptLanguage(self):
        table = (
            ("da, en-gb;q=0.8, en;q=0.7",
             {'da': 1.0, 'en-gb': 0.8, 'en': 0.7}),
            ("*",
             {'*': 1}),
            )
        self.runRoundtripTest("Accept-Language", table)

    def testAuthorization(self):
        table = (
            ("Basic dXNlcm5hbWU6cGFzc3dvcmQ=",
             ("basic", "dXNlcm5hbWU6cGFzc3dvcmQ="),
             ["basic dXNlcm5hbWU6cGFzc3dvcmQ="]),
            ('Digest nonce="bar", realm="foo", username="baz", response="bax"',
             ('digest', 'nonce="bar", realm="foo", username="baz", response="bax"'),
             ['digest', 'nonce="bar"', 'realm="foo"', 'username="baz"', 'response="bax"'])
            )

        self.runRoundtripTest("Authorization", table)

    def testCookie(self):
        table = (
            ('name=value', [Cookie('name', 'value')]),
            ('"name"="value"', [Cookie('"name"', '"value"')]),
            ('name,"blah=value,"', [Cookie('name,"blah', 'value,"')]),
            ('name,"blah  = value,"  ', [Cookie('name,"blah', 'value,"')], ['name,"blah=value,"']),
            ("`~!@#$%^&*()-_+[{]}\\|:'\",<.>/?=`~!@#$%^&*()-_+[{]}\\|:'\",<.>/?", [Cookie("`~!@#$%^&*()-_+[{]}\\|:'\",<.>/?", "`~!@#$%^&*()-_+[{]}\\|:'\",<.>/?")]),
            ('name,"blah  = value,"  ; name2=val2',
               [Cookie('name,"blah', 'value,"'), Cookie('name2', 'val2')],
               ['name,"blah=value,"', 'name2=val2']),
            )
        self.runRoundtripTest("Cookie", table)

        #newstyle RFC2965 Cookie
        table2 = (
            ('$Version="1";'
             'name="value";$Path="/foo";$Domain="www.local";$Port="80,8000";'
             'name2="value"',
             [Cookie('name', 'value', path='/foo', domain='www.local', ports=(80,8000), version=1), Cookie('name2', 'value', version=1)]),
            ('$Version="1";'
             'name="value";$Port',
             [Cookie('name', 'value', ports=(), version=1)]),
            ('$Version = 1, NAME = "qq\\"qq",Frob=boo',
             [Cookie('name', 'qq"qq', version=1), Cookie('frob', 'boo', version=1)],
             ['$Version="1";name="qq\\"qq";frob="boo"']),
            )
        self.runRoundtripTest("Cookie", table2)

        # Generate only!
        # make headers by combining oldstyle and newstyle cookies
        table3 = (
            ([Cookie('name', 'value'), Cookie('name2', 'value2', version=1)],
             '$Version="1";name=value;name2="value2"'),
            ([Cookie('name', 'value', path="/foo"), Cookie('name2', 'value2', domain="bar.baz", version=1)],
             '$Version="1";name=value;$Path="/foo";name2="value2";$Domain="bar.baz"'),
            ([Cookie('invalid,"name', 'value'), Cookie('name2', 'value2', version=1)],
             '$Version="1";name2="value2"'),
            ([Cookie('name', 'qq"qq'), Cookie('name2', 'value2', version=1)],
             '$Version="1";name="qq\\"qq";name2="value2"'),
            )
        for row in table3:
            self.assertEquals(generateHeader("Cookie", row[0]), [row[1],])



    def testSetCookie(self):
        table = (
            ('name,"blah=value,; expires=Sun, 09 Sep 2001 01:46:40 GMT; path=/foo; domain=bar.baz; secure',
             [Cookie('name,"blah', 'value,', expires=1000000000, path="/foo", domain="bar.baz", secure=True)]),
            ('name,"blah = value, ; expires="Sun, 09 Sep 2001 01:46:40 GMT"',
             [Cookie('name,"blah', 'value,', expires=1000000000)],
             ['name,"blah=value,', 'expires=Sun, 09 Sep 2001 01:46:40 GMT']),
            )
        self.runRoundtripTest("Set-Cookie", table)

    def testSetCookie2(self):
        table = (
            ('name="value"; Comment="YadaYada"; CommentURL="http://frobnotz/"; Discard; Domain="blah.blah"; Max-Age=10; Path="/foo"; Port="80,8080"; Secure; Version="1"',
             [Cookie("name", "value", comment="YadaYada", commenturl="http://frobnotz/", discard=True, domain="blah.blah", expires=1000000000, path="/foo", ports=(80,8080), secure=True, version=1)]),
            )
        self.runRoundtripTest("Set-Cookie2", table)

    def testExpect(self):
        table = (
            ("100-continue",
             {"100-continue":(None,)}),
            ('foobar=twiddle',
             {'foobar':('twiddle',)}),
            ("foo=bar;a=b;c",
             {'foo':('bar',('a', 'b'), ('c', None))})
            )
        self.runRoundtripTest("Expect", table)

    def testFrom(self):
        self.runRoundtripTest("From", (("webmaster@w3.org", "webmaster@w3.org"),))

    def testHost(self):
        self.runRoundtripTest("Host", (("www.w3.org", "www.w3.org"),))

    def testIfMatch(self):
        table = (
            ('"xyzzy"', [http_headers.ETag('xyzzy')]),
            ('"xyzzy", "r2d2xxxx", "c3piozzzz"', [http_headers.ETag('xyzzy'),
                                                    http_headers.ETag('r2d2xxxx'),
                                                    http_headers.ETag('c3piozzzz')]),
            ('*', ['*']),
            )
    def testIfModifiedSince(self):
        # Don't need major tests since the datetime parser has its own test
        # Just test stupid ; length= brokenness.
        table = (
            ("Sun, 09 Sep 2001 01:46:40 GMT", 1000000000),
            ("Sun, 09 Sep 2001 01:46:40 GMT; length=500", 1000000000, ["Sun, 09 Sep 2001 01:46:40 GMT"]),
            )

        self.runRoundtripTest("If-Modified-Since", table)

    def testIfNoneMatch(self):
        table = (
            ('"xyzzy"', [http_headers.ETag('xyzzy')]),
            ('W/"xyzzy", "r2d2xxxx", "c3piozzzz"', [http_headers.ETag('xyzzy', weak=True),
                                                    http_headers.ETag('r2d2xxxx'),
                                                    http_headers.ETag('c3piozzzz')]),
            ('W/"xyzzy", W/"r2d2xxxx", W/"c3piozzzz"', [http_headers.ETag('xyzzy', weak=True),
                                                        http_headers.ETag('r2d2xxxx', weak=True),
                                                        http_headers.ETag('c3piozzzz', weak=True)]),
            ('*', ['*']),
            )
        self.runRoundtripTest("If-None-Match", table)

    def testIfRange(self):
        table = (
            ('"xyzzy"', http_headers.ETag('xyzzy')),
            ('W/"xyzzy"', http_headers.ETag('xyzzy', weak=True)),
            ('W/"xyzzy"', http_headers.ETag('xyzzy', weak=True)),
            ("Sun, 09 Sep 2001 01:46:40 GMT", 1000000000),
            )
        self.runRoundtripTest("If-Range", table)

    def testIfUnmodifiedSince(self):
        self.runRoundtripTest("If-Unmodified-Since", (("Sun, 09 Sep 2001 01:46:40 GMT", 1000000000),))

    def testMaxForwards(self):
        self.runRoundtripTest("Max-Forwards", (("15", 15),))


#     def testProxyAuthorize(self):
#         fail

    def testRange(self):
        table = (
            ("bytes=0-499", ('bytes', [(0,499),])),
            ("bytes=500-999", ('bytes', [(500,999),])),
            ("bytes=-500",('bytes', [(None,500),])),
            ("bytes=9500-",('bytes', [(9500, None),])),
            ("bytes=0-0,-1", ('bytes', [(0,0),(None,1)])),
            )
        self.runRoundtripTest("Range", table)


    def testReferer(self):
        self.runRoundtripTest("Referer", (("http://www.w3.org/hypertext/DataSources/Overview.html",
                                           "http://www.w3.org/hypertext/DataSources/Overview.html"),))


    def testTE(self):
        table = (
            ("deflate", {'deflate':1}),
            ("", {}),
            ("trailers, deflate;q=0.5", {'trailers':1, 'deflate':0.5}),
            )
        self.runRoundtripTest("TE", table)

    def testUserAgent(self):
        self.runRoundtripTest("User-Agent", (("CERN-LineMode/2.15 libwww/2.17b3", "CERN-LineMode/2.15 libwww/2.17b3"),))


class ResponseHeaderParsingTests(HeaderParsingTestBase):
    def testAcceptRanges(self):
        self.runRoundtripTest("Accept-Ranges", (("bytes", ["bytes"]), ("none", ["none"])))

    def testAge(self):
        self.runRoundtripTest("Age", (("15", 15),))

    def testETag(self):
        table = (
            ('"xyzzy"', http_headers.ETag('xyzzy')),
            ('W/"xyzzy"', http_headers.ETag('xyzzy', weak=True)),
            ('""', http_headers.ETag('')),
            )
        self.runRoundtripTest("ETag", table)

    def testLocation(self):
        self.runRoundtripTest("Location", (("http://www.w3.org/pub/WWW/People.htm",
                                           "http://www.w3.org/pub/WWW/People.htm"),))


#     def testProxyAuthenticate(self):
#         fail

    def testRetryAfter(self):
        # time() is always 999999990 when being tested.
        table = (
            ("Sun, 09 Sep 2001 01:46:40 GMT", 1000000000, ["10"]),
            ("120", 999999990+120),
            )
        self.runRoundtripTest("Retry-After", table)

    def testServer(self):
        self.runRoundtripTest("Server", (("CERN/3.0 libwww/2.17", "CERN/3.0 libwww/2.17"),))

    def testVary(self):
        table = (
            ("*", ["*"]),
            ("Accept, Accept-Encoding", ["accept", "accept-encoding"], ["accept", "accept-encoding"])
            )
        self.runRoundtripTest("Vary", table)

    def testWWWAuthenticate(self):
        digest = ('Digest realm="digest realm", nonce="bAr", qop="auth"',
                  [('Digest', {'realm': 'digest realm', 'nonce': 'bAr', 
                               'qop': 'auth'})],
                  ['Digest', 'realm="digest realm"', 
                   'nonce="bAr"', 'qop="auth"'])

        basic = ('Basic realm="foo"',
                 [('Basic', {'realm': 'foo'})], ['Basic', 'realm="foo"'])

        ntlm = ('NTLM',
                [('NTLM', {})], ['NTLM', ''])

        negotiate = ('Negotiate SomeGssAPIData',
                     [('Negotiate', 'SomeGssAPIData')], 
                     ['Negotiate', 'SomeGssAPIData'])

        table = (digest,
                 basic,
                 (digest[0]+', '+basic[0],
                  digest[1] + basic[1],
                  [digest[2], basic[2]]),
                 ntlm,
                 negotiate,
                 (ntlm[0]+', '+basic[0],
                  ntlm[1] + basic[1],
                  [ntlm[2], basic[2]]),
                 (digest[0]+', '+negotiate[0],
                  digest[1] + negotiate[1],
                  [digest[2], negotiate[2]]),
                 (negotiate[0]+', '+negotiate[0],
                  negotiate[1] + negotiate[1],
                  [negotiate[2] + negotiate[2]]),
                 (ntlm[0]+', '+ntlm[0],
                  ntlm[1] + ntlm[1],
                  [ntlm[2], ntlm[2]]),
                 (basic[0]+', '+ntlm[0],
                  basic[1] + ntlm[1],
                  [basic[2], ntlm[2]]),
                 )

        # runRoundtripTest doesn't work because we don't generate a single
        # header

        headername = 'WWW-Authenticate'

        for row in table:
            rawHeaderInput, parsedHeaderData, requiredGeneratedElements = row

            parsed = parseHeader(headername, [rawHeaderInput,])
            self.assertEquals(parsed, parsedHeaderData)

            regeneratedHeaderValue = generateHeader(headername, parsed)

            for regeneratedElement in regeneratedHeaderValue:
                requiredElements = requiredGeneratedElements[
                    regeneratedHeaderValue.index(
                        regeneratedElement)]

                for reqEle in requiredElements:
                    elementIndex = regeneratedElement.find(reqEle)

                    self.assertNotEqual(
                        elementIndex, -1,
                        "%r did not appear in generated HTTP header %r: %r" % (reqEle,
                                                                               headername,
                                                                               regeneratedElement))

        # parser/generator
        reparsed = parseHeader(headername, regeneratedHeaderValue)
        self.assertEquals(parsed, reparsed)


class EntityHeaderParsingTests(HeaderParsingTestBase):
    def testAllow(self):
        # Allow is a silly case-sensitive header unlike all the rest
        table = (
            ("GET", ['GET', ]),
            ("GET, HEAD, PUT", ['GET', 'HEAD', 'PUT']),
            )
        self.runRoundtripTest("Allow", table)

    def testContentEncoding(self):
        table = (
            ("gzip", ['gzip',]),
            )
        self.runRoundtripTest("Content-Encoding", table)

    def testContentLanguage(self):
        table = (
            ("da", ['da',]),
            ("mi, en", ['mi', 'en']),
            )
        self.runRoundtripTest("Content-Language", table)

    def testContentLength(self):
        self.runRoundtripTest("Content-Length", (("15", 15),))
        self.invalidParseTest("Content-Length", ("asdf",))

    def testContentLocation(self):
        self.runRoundtripTest("Content-Location",
                              (("http://www.w3.org/pub/WWW/People.htm",
                                "http://www.w3.org/pub/WWW/People.htm"),))

    def testContentMD5(self):
        self.runRoundtripTest("Content-MD5", (("Q2hlY2sgSW50ZWdyaXR5IQ==", "Check Integrity!"),))
        self.invalidParseTest("Content-MD5", ("sdlaksjdfhlkaj",))

    def testContentRange(self):
        table = (
            ("bytes 0-499/1234", ("bytes", 0, 499, 1234)),
            ("bytes 500-999/1234", ("bytes", 500, 999, 1234)),
            ("bytes 500-1233/1234", ("bytes", 500, 1233, 1234)),
            ("bytes 734-1233/1234", ("bytes", 734, 1233, 1234)),
            ("bytes 734-1233/*", ("bytes", 734, 1233, None)),
            ("bytes */1234", ("bytes", None, None, 1234)),
            ("bytes */*", ("bytes", None, None, None))
            )
        self.runRoundtripTest("Content-Range", table)

    def testContentType(self):
        table = (
            ("text/html;charset=iso-8859-4", http_headers.MimeType('text', 'html', (('charset','iso-8859-4'),))),
            ("text/html", http_headers.MimeType('text', 'html')),
            )
        self.runRoundtripTest("Content-Type", table)

    def testExpires(self):
        self.runRoundtripTest("Expires", (("Sun, 09 Sep 2001 01:46:40 GMT", 1000000000),))
        # Invalid expires MUST return date in the past.
        self.assertEquals(parseHeader("Expires", ["0"]), 0)
        self.assertEquals(parseHeader("Expires", ["wejthnaljn"]), 0)


    def testLastModified(self):
        # Don't need major tests since the datetime parser has its own test
        self.runRoundtripTest("Last-Modified", (("Sun, 09 Sep 2001 01:46:40 GMT", 1000000000),))

class DateTimeTest(unittest.TestCase):
    """Test date parsing functions."""

    def testParse(self):
        timeNum = 784111777
        timeStrs = ('Sun, 06 Nov 1994 08:49:37 GMT',
                    'Sunday, 06-Nov-94 08:49:37 GMT',
                    'Sun Nov  6 08:49:37 1994',

                    # Also some non-RFC formats, for good measure.
                    'Somefakeday 6 Nov 1994 8:49:37',
                    '6 Nov 1994 8:49:37',
                    'Sun, 6 Nov 1994 8:49:37',
                    '6 Nov 1994 8:49:37 GMT',

                    '06-Nov-94 08:49:37',
                    'Sunday, 06-Nov-94 08:49:37',
                    '06-Nov-94 08:49:37 GMT',

                    'Nov  6 08:49:37 1994',
                    )
        for timeStr in timeStrs:
            self.assertEquals(http_headers.parseDateTime(timeStr), timeNum)

        # Test 2 Digit date wraparound yuckiness.
        self.assertEquals(http_headers.parseDateTime(
            'Monday, 11-Oct-04 14:56:50 GMT'), 1097506610)
        self.assertEquals(http_headers.parseDateTime(
            'Monday, 11-Oct-2004 14:56:50 GMT'), 1097506610)


    def testGenerate(self):
        self.assertEquals(http_headers.generateDateTime(784111777), 'Sun, 06 Nov 1994 08:49:37 GMT')

    def testRoundtrip(self):
        for i in range(2000):
            time = random.randint(0, 2000000000)
            timestr = http_headers.generateDateTime(time)
            time2 = http_headers.parseDateTime(timestr)
            self.assertEquals(time, time2)


class TestMimeType(unittest.TestCase):
    def testEquality(self):
        """Test that various uses of the constructer are equal
        """

        kwargMime = http_headers.MimeType('text', 'plain',
                                          key='value',
                                          param=None)
        dictMime = http_headers.MimeType('text', 'plain',
                                         {'param': None,
                                          'key': 'value'})
        tupleMime = http_headers.MimeType('text', 'plain',
                                          (('param', None),
                                           ('key', 'value')))

        stringMime = http_headers.MimeType.fromString('text/plain;key=value;param')

        self.assertEquals(kwargMime, dictMime)
        self.assertEquals(dictMime, tupleMime)
        self.assertEquals(kwargMime, tupleMime)
        self.assertEquals(kwargMime, stringMime)



class FormattingUtilityTests(unittest.TestCase):
    """
    Tests for various string formatting functionality required to generate
    headers.
    """
    def test_quoteString(self):
        """
        L{quoteString} returns a string which when interpreted according to the
        rules for I{quoted-string} (RFC 2616 section 2.2) matches the input
        string.
        """
        self.assertEqual(
            quoteString('a\\b"c'),
            '"a\\\\b\\"c"')


    def test_generateKeyValues(self):
        """
        L{generateKeyValues} accepts an iterable of parameters and returns a
        string formatted according to RFC 2045 section 5.1.
        """
        self.assertEqual(
            generateKeyValues(iter([("foo", "bar"), ("baz", "quux")])),
            "foo=bar;baz=quux")


    def test_generateKeyValuesNone(self):
        """
        L{generateKeyValues} accepts C{None} as the 2nd element of a tuple and
        includes just the 1st element in the output without an C{"="}.
        """
        self.assertEqual(
            generateKeyValues([("foo", None), ("bar", "baz")]),
            "foo;bar=baz")


    def test_generateKeyValuesQuoting(self):
        """
        L{generateKeyValues} quotes the value of the 2nd element of a tuple if
        it includes a character which cannot be in an HTTP token as defined in
        RFC 2616 section 2.2.
        """
        for needsQuote in [' ', '\t', '(', ')', '<', '>', '@', ',', ';', ':',
                           '\\', '"', '/', '[', ']', '?', '=', '{', '}']:
            self.assertEqual(
                generateKeyValues([("foo", needsQuote)]),
                'foo=%s' % (quoteString(needsQuote),))
