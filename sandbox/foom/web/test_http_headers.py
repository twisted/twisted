from twisted.trial import unittest
import http_headers

class HeaderListTest(unittest.TestCase):
    """Test header list parsing functions."""

    def testParse(self):
		self.assertEquals(http_headers.parseDelimList("foo,bar"), ('foo', 'bar'))
		self.assertEquals(http_headers.parseDelimList("foo,bar;baz", delim=';'), ('foo,bar', 'baz'))
		self.assertEquals(http_headers.parseDelimList(" \t foo  \t,  \t bar   "), ('foo', 'bar'))
		self.assertEquals(http_headers.parseDelimList(",foo,bar,"), ('', 'foo', 'bar', ''))
		self.assertEquals(http_headers.parseDelimList("foo bar, baz frob"), ('foo bar', 'baz frob'))
		
    def testGenerate(self):
        pass
	
    def testRoundtrip(self):
		pass
        

class DateTimeTest(unittest.TestCase):
    """Test date parsing functions."""

    def testParse(self):
        timeNum = 784111777
        timeStrs = ('Sun, 06 Nov 1994 08:49:37 GMT',
                    'Sunday, 06-Nov-94 08:49:37 GMT',
                    'Sun Nov  6 08:49:37 1994')
        for timeStr in timeStrs:
            self.assertEquals(http.stringToDatetime(timeStr), timeNum)

    def testGenerate(self):
        self.assertEquals(http.datetimeToString(784111777), 'Sun, 06 Nov 1994 08:49:37 GMT')
        
    def testRoundtrip(self):
        for i in range(10000):
            time = random.randint(0, 2000000000)
            timestr = http.datetimeToString(time)
            time2 = http.stringToDatetime(timestr)
            self.assertEquals(time, time2)
            
        
        
