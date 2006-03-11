from twisted.trial import unittest
from twisted.web2 import log, iweb, resource, http
from twisted.web2.test.test_server import BaseCase, BaseTestResource

from twisted.python import log as tlog
from twisted.test.test_log import FakeFile

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

class NoneStreamResource(resource.Resource):
    def render(self, req):
        return http.Response(200)
    
class TestLogging(BaseCase):
    def setUp(self):
        self.blo = BufferingLogObserver()
        tlog.addObserver(self.blo.emit)

        # some default resource setup
        self.resrc = BaseTestResource()
        self.resrc.child_emptystream = NoneStreamResource()
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

    def testLogNoneResponseStream(self):
        uri = 'http://localhost/emptystream'
        method = 'GET'
        
        def _cbCheckLog(response):
            self.assertLogged(method=method, uri=uri, status=200,
                              length=0)
            
        d = self.getResponseFor(self.root, uri, method=method)
        d.addCallback(_cbCheckLog)

        return d

        

