from twisted.trial import unittest
import http_headers
import random

class TokenizerTest(unittest.TestCase):
    """Test header list parsing functions."""

    def testParse(self):
        parser = http_headers.parseHeader(str)
        tests = (('foo,bar', ['foo', Token(','), 'bar']),
                 ('FOO,BAR', ['foo', Token(','), 'bar']),
                 (' \t foo  \t bar  \t  ,  \t baz   ', ['foo', Token(' '), 'bar', Token(','), 'baz']),
                 ('()<>@,;:\\/[]?={}', [Token('('), Token(')'), Token('<'), Token('>'), Token('@'), Token(','), Token(';'), Token(':'), Token('\\'), Token('/'), Token('['), Token(']'), Token('?'), Token('='), Token('{'), Token('}')])
                 (' "foo" ', ['foo']),
                 ('"FOO(),\\"BAR,"', ['FOO(),"BAR,']))

        raiseTests = ('"open quote', '"ending \\')
        
        for test,result in tests:
            self.assertEquals(tuple(parser(test)), result)
        for test in raiseTest:
            self.assertRaises(parser(raiseTest))
        
    def testGenerate(self):
        pass
    
    def testRoundtrip(self):
        pass

def parseHeader(name, val):
    head = http_headers.ReceivedHeaders(parsers=http_headers.DefaultHTTPParsers)
    head._raw_headers={name:[val,]}
    return head.getHeader(name)

class GeneralHeaderParsingTests(unittest.TestCase):
    def testCacheControl(self):
        fail

    def testConnection(self):
        fail

    def testDate(self):
        fail

    def testPragma(self):
        fail

    def testTrailer(self):
        fail

    def testTransferEncoding(self):
        fail

    def testUpgrade(self):
        fail

    def testVia(self):
        fail

    def testWarning(self):
        fail
    
class RequestHeaderParsingTests(unittest.TestCase):
    def runRoundtripTest(self, headername, table):
        for row in table:
            self.assertEquals(parseHeader(headername, row[0]), row[1])
            # other way too
    
    #FIXME test ordering too.
    def testAccept(self):
        table = (
            ("audio/*; q=0.2, audio/basic",
             {('audio', '*', ()): {'q': 0.2},
              ('audio', 'basic', ()): {'q': 1.0}}),
            
            ("text/plain; q=0.5, text/html, text/x-dvi; q=0.8, text/x-c",
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
             {'iso-8859-5': 1.0, 'iso-8859-1': 1.0, 'unicode-1-1': 0.8}),
            ("iso-8859-1;q=.7",
             {'iso-8859-1': 0.7}),
            ("*;q=.7",
             {'*': 0.7}),
            ("",
             {'iso-8859-1': 1.0}),
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
             {'compress': 0.5, 'gzip': 1.0, 'identity': 0.0001}),
            ("gzip;q=1.0, identity; q=0.5, *;q=0",
             {'gzip': 1.0, 'identity': 0.5, '*':0}),
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
        pass
        
    def testExpect(self):
        table = (
            ("100-continue",
             {"100-continue":True}),
            ('foobar="Twiddle"'))
        pass

    def testFrom(self):
        pass

    def testHost(self):
        pass

    def testIfModifiedSince(self):
        # Don't need major tests since the datetime parser has its own test
        self.runRoundtripTest("If-Modified-Since", (("Sun, 09 Sep 2001 01:46:40 GMT", 1000000000),))
        
    def testIfNoneMatch(self):
        pass

    def testIfRange(self):
        pass

    def testIfUnmodifiedSince(self):
        self.runRoundtripTest("If-Unmodified-Since", (("Sun, 09 Sep 2001 01:46:40 GMT", 1000000000),))
        pass

    def testMaxForwards(self):
        pass

    def testProxyAuthorize(self):
        pass

    def testRange(self):
        pass

    def testReferer(self):
        pass

    def testTE(self):
        pass

    def testUserAgent(self):
        pass
    
        
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
        self.assertEquals(http_headers.datetimeToString(784111777), 'Sun, 06 Nov 1994 08:49:37 GMT')
        
    def testRoundtrip(self):
        for i in range(2000):
            time = random.randint(0, 2000000000)
            timestr = http_headers.datetimeToString(time)
            time2 = http_headers.parseDateTime(timestr)
            self.assertEquals(time, time2)
            
        
        
