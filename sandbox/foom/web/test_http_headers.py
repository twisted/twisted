from twisted.trial import unittest
import random


# Heh heh. Too Evil to pass up. ;)
import __builtin__
__builtin__._http_headers_isBeingTested=True
import http_headers
del __builtin__._http_headers_isBeingTested


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

def parseHeader(name, val):
    head = http_headers.Headers(parsers=http_headers.DefaultHTTPParsers)
    head.setRawHeader(name,val)
    return head.getHeader(name)

def generateHeader(name, val):
    head = http_headers.Headers(generators=http_headers.DefaultHTTPGenerators)
    head.setHeader(name, val)
    return head.getRawHeader(name)


class HeaderParsingTestBase(unittest.TestCase):
    def runRoundtripTest(self, headername, table):
        for row in table:
            # parser
            parsed = parseHeader(headername, [row[0],])
            self.assertEquals(parsed, row[1])
            # generator
            self.assertEquals(generateHeader(headername, parsed), len(row) > 2 and [row[2],] or [row[0],])

class GeneralHeaderParsingTests(HeaderParsingTestBase):
#     def testCacheControl(self):
#         fail

    def testConnection(self):
        table = (
            ("close", ['close',]),
            ("close, foo-bar", ['close', 'foo-bar'])
            )
        self.runRoundtripTest("Connection", table)

#     def testDate(self):
#         fail

#     def testPragma(self):
#         fail

#     def testTrailer(self):
#         fail

#     def testTransferEncoding(self):
#         fail

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
             {('audio', '*', ()): {'q': 0.2},
              ('audio', 'basic', ()): {'q': 1.0}}),
            
            ("text/plain;q=0.5, text/html, text/x-dvi;q=0.8, text/x-c",
             {('text', 'plain', ()): {'q': 0.5},
              ('text', 'html', ()): {'q': 1.0},
              ('text', 'x-dvi', ()): {'q': 0.8},
              ('text', 'x-c', ()): {'q': 1.0}}),
            
            ("text/*, text/html, text/html;level=1, */*",
             {('text', '*', ()): {'q': 1.0},
              ('text', 'html', ()): {'q': 1.0},
              ('text', 'html', (('level', '1'),)): {'q': 1.0},
              ('*', '*', ()): {'q': 1.0}}),
            
       ("text/*;q=0.3, text/html;q=0.7, text/html;level=1, text/html;level=2;q=0.4, */*;q=0.5",
             {('text', '*', ()): {'q': 0.3},
              ('text', 'html', ()): {'q': 0.7},
              ('text', 'html', (('level', '1'),)): {'q': 1.0},
              ('text', 'html', (('level', '2'),)): {'q': 0.4},
              ('*', '*', ()): {'q': 0.5}}),
            )
        
        self.runRoundtripTest("Accept", table)

            
    def testAcceptCharset(self):
        table = (
            ("iso-8859-5, unicode-1-1;q=0.8",
             {'iso-8859-5': 1.0, 'iso-8859-1': 1.0, 'unicode-1-1': 0.8},
             "iso-8859-5, unicode-1-1;q=0.8, iso-8859-1"),
            ("iso-8859-1;q=0.7",
             {'iso-8859-1': 0.7}),
            ("*;q=.7",
             {'*': 0.7},
             "*;q=0.7"),
            ("",
             {'iso-8859-1': 1.0},
             "iso-8859-1"), # Yes this is an actual change -- we'll say that's okay. :)
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
             "compress;q=0.5, gzip"),
            ("gzip;q=1.0, identity;q=0.5, *;q=0",
             {'gzip': 1.0, 'identity': 0.5, '*':0},
             "gzip, identity;q=0.5, *;q=0"),
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

#     def testAuthorization(self):
#         fail
        
    def testExpect(self):
        table = (
            ("100-continue",
             {"100-continue":(True,)}),
            ('foobar=twiddle',
             {'foobar':('twiddle',)}),
            ("foo=bar;a=b;c",
             {'foo':('bar',('a', 'b'), ('c', True))})
            )
        self.runRoundtripTest("Expect", table)

#     def testFrom(self):
#         fail

#     def testHost(self):
#         fail

    def testIfModifiedSince(self):
        # Don't need major tests since the datetime parser has its own test
        self.runRoundtripTest("If-Modified-Since", (("Sun, 09 Sep 2001 01:46:40 GMT", 1000000000),))
        
#     def testIfNoneMatch(self):
#         fail

#     def testIfRange(self):
#         fail

    def testIfUnmodifiedSince(self):
        self.runRoundtripTest("If-Unmodified-Since", (("Sun, 09 Sep 2001 01:46:40 GMT", 1000000000),))
        pass
    
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
        

#     def testReferer(self):
#         fail

#     def testTE(self):
#         fail

#     def testUserAgent(self):
#         fail
    
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
        self.runRoundtripTest("Content-Encoding", table)
        
#     def testContentLength(self):
#         fail
#     def testContentLocation(self):
#         fail

#     def testContentMD5(self):
#         fail
    
#     def testContentRange(self):
#         fail
#     def testContentType(self):
#         fail
#     def testExpires(self):
#         fail
#     def testLastModified(self):
#         fail
    
class DateTimeTest(unittest.TestCase):
    """Test date parsing functions."""

    def testParse(self):
        timeNum = 784111777
        timeStrs = ('Sun, 06 Nov 1994 08:49:37 GMT',
                    'Sunday, 06-Nov-94 08:49:37 GMT',
                    'Sun Nov  6 08:49:37 1994')
        for timeStr in timeStrs:
            self.assertEquals(http_headers.parseDateTime(timeStr), timeNum)

    def testGenerate(self):
        self.assertEquals(http_headers.generateDateTime(784111777), 'Sun, 06 Nov 1994 08:49:37 GMT')
        
    def testRoundtrip(self):
        for i in range(2000):
            time = random.randint(0, 2000000000)
            timestr = http_headers.generateDateTime(time)
            time2 = http_headers.parseDateTime(timestr)
            self.assertEquals(time, time2)
            
        
        
