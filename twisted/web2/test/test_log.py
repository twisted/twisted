from twisted.trial import unittest
from twisted.web2 import log, iweb, resource, http, http_headers
from twisted.web2.test.test_server import BaseCase, BaseTestResource

from twisted.internet import address
from twisted.python import log as tlog

import time

from zope.interface import implements

class TestRequest:
    implements(iweb.IRequest)

    def __init__(self, method='GET', uri='/', clientproto=(1, 1),
                 remoteHost='127.0.0.1', headers={}):

        self.method = method
        self.uri = uri
        self.clientproto = (1, 1)

        self.headers = http_headers.Headers(headers)

        self.remoteAddr = address.IPv4Address('TCP', remoteHost, 0)


class BufferingLogObserver(log.BaseCommonAccessLoggingObserver):
    messages = ['']
    def logMessage(self, message):
        self.messages.append(message)


class TestLogWrapperResource(resource.WrapperResource):
    def hook(self, req):
        def _logFilter(req, resp):
            resp.headers.setHeader('date', 0.0)
            return log.logFilter(req, resp)

        _logFilter.handleErrors = True
                                 
        req.addResponseFilter(_logFilter, atEnd=True)


class TestLogWrapper(BaseCase):
    def setUp(self):
        self.blo = BufferingLogObserver()
        tlog.addObserver(self.blo.emit)

        # some default resource setup
        self.resrc = BaseTestResource()
        self.resrc.addSlash = True
        self.resrc.responseHeaders = {'Date': 0.0}
        
        self.root = TestLogWrapperResource(self.resrc)

    def assertLogged(self, **expected):
        if 'date' not in expected:
            epoch = log.BaseCommonAccessLoggingObserver().logDateString(0)
            expected['date'] = epoch

        if 'user' not in expected:
            expected['user'] = '-'
            
        if 'referer' not in expected:
            expected['referer'] = '-'
            
        if 'user-agent' not in expected:
            expected['user-agent'] = '-'

        if 'version' not in expected:
            expected['version'] = '1.1'

        if 'remotehost' not in expected:
            expected['remotehost'] = 'remotehost'
        
        if 'message' in expected:
            message = message
        else:
            message = self.blo.messages[-1]

        expectedLog = ('%(remotehost)s - %(user)s [%(date)s] "%(method)s '
                       '%(uri)s HTTP/%(version)s" %(status)d %(length)d '
                       '"%(referer)s" "%(user-agent)s"')

        if expected.get('logged', True):
            self.assertEquals(message, expectedLog % expected)
        else:
            self.failIfEquals(message, expectedLog % expected)

    def testLogSimpleRequest(self):
        uri = 'http://localhost/'
        method = 'GET'
        
        def _cbCheckLog(response):
            self.assertLogged(method=method, uri=uri, status=response[0],
                              length=response[1].getHeader('content-length'))
            
        d = self.getResponseFor(self.root, uri, method=method)
        d.addCallback(_cbCheckLog)

        return d

    def testLogErrors(self):

        def test(_, uri, method, **expected):
            expected['uri'] = uri
            expected['method'] = method
            
            def _cbCheckLog(response):
                self.assertEquals(response[0], expected['status'])
                self.assertLogged(
                    length=response[1].getHeader('content-length'), **expected)
            
            return self.getResponseFor(self.root,
                                       uri,
                                       method=method).addCallback(_cbCheckLog)
        

        uri = 'http://localhost/foo' # doesn't exist
        method = 'GET'
    
        d = test(None, uri, method, status=404, logged=True)

        # no host. this should result in a 400 which doesn't get logged
        uri = 'http:///' 

        d.addCallback(test, uri, method, status=400, logged=False)

        return d


class TestLogObserver(unittest.TestCase):
    def setUp(self):
        self.timeDaylight = time.daylight
        self.blo = BufferingLogObserver()
        self.blo.tzForLog = 0
        self.blo.tzForLogAlt = 0

    def tearDown(self):
        time.daylight = self.timeDaylight

    def testLogDateString(self):
        times = ((0.0, '31/Dec/1969:16:00:00 0'),
                 (111111111.0, '9/Jul/1973:17:11:51 0'),
                 (123456789.0, '29/Nov/1973:13:33:09 -0700',
                  ('-0700', None, 0)),
                 (555555555.5, '9/Aug/1987:17:59:15 0'))
        
        for t in times:
            if len(t) == 3:
                (self.blo.tzForLog, self.blo.tzForLogAlt,
                 time.daylight) = t[2]
            else:
                self.blo.tzForLog = 0
                self.blo.tzForLogAlt = 0
                time.daylight = 0
                
            self.assertEquals(self.blo.logDateString(t[0]),
                              t[1])

    def testEmit(self):
        self.blo.tzForLog = 0
        self.blo.tzForLogAlt = 0
        time.daylight = 0

        req = TestRequest(headers={'user-agent': 'NotARealBrowser/1.0',
                                   'referer': 'not-a-real-website'})
        resp = http.Response(200, stream='Foo')
        loginfo = log.LogInfo()
        loginfo.bytesSent = 3
        loginfo.secondsTaken = 0
        loginfo.resposneCompleted = True
        
        self.blo.emit({'interface': iweb.IRequest,
                       'request': req,
                       'response': resp,
                       'loginfo': loginfo})

        logLine = '127.0.0.1 - - [31/Dec/1969:16:00:00 0] '
        logLine += '"GET / HTTP/1.1" 200 3 "not-a-real-website" '
        logLine += '"NotARealBrowser/1.0"'
        
        self.assertEquals(
            self.blo.messages[-1],
            logLine)
