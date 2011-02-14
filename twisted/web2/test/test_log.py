# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

from twisted.web2 import log, resource, http
from twisted.web2.test.test_server import BaseCase, BaseTestResource

from twisted.python import log as tlog

class BufferingLogObserver(log.BaseCommonAccessLoggingObserver):
    """
    A web2 log observer that buffer messages.
    """
    messages = []
    def logMessage(self, message):
        self.messages.append(message)

class SetDateWrapperResource(resource.WrapperResource):
    """
    A resource wrapper which sets the date header.
    """
    def hook(self, req):
        def _filter(req, resp):
            resp.headers.setHeader('date', 0.0)
            return resp
        _filter.handleErrors = True

        req.addResponseFilter(_filter, atEnd=True)

class NoneStreamResource(resource.Resource):
    """
    A basic empty resource.
    """
    def render(self, req):
        return http.Response(200)

class TestLogging(BaseCase):
    def setUp(self):
        self.blo = BufferingLogObserver()
        tlog.addObserver(self.blo.emit)

        # some default resource setup
        self.resrc = BaseTestResource()
        self.resrc.child_emptystream = NoneStreamResource()

        self.root = SetDateWrapperResource(log.LogWrapperResource(self.resrc))

    def tearDown(self):
        tlog.removeObserver(self.blo.emit)

    def assertLogged(self, **expected):
        """
        Check that logged messages matches expected format.
        """
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

        messages = self.blo.messages[:]
        del self.blo.messages[:]

        expectedLog = ('%(remotehost)s - %(user)s [%(date)s] "%(method)s '
                       '%(uri)s HTTP/%(version)s" %(status)d %(length)d '
                       '"%(referer)s" "%(user-agent)s"')

        if expected.get('logged', True):
            # Ensure there weren't other messages hanging out
            self.assertEquals(len(messages), 1, "len(%r) != 1" % (messages, ))
            self.assertEquals(messages[0], expectedLog % expected)
        else:
            self.assertEquals(len(messages), 0, "len(%r) != 0" % (messages, ))

    def test_logSimpleRequest(self):
        """
        Check the log for a simple request.
        """
        uri = 'http://localhost/'
        method = 'GET'

        def _cbCheckLog(response):
            self.assertLogged(method=method, uri=uri, status=response[0],
                              length=response[1].getHeader('content-length'))

        d = self.getResponseFor(self.root, uri, method=method)
        d.addCallback(_cbCheckLog)

        return d

    def test_logErrors(self):
        """
        Test the error log.
        """
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

    def test_logNoneResponseStream(self):
        """
        Test the log of an empty resource.
        """
        uri = 'http://localhost/emptystream'
        method = 'GET'

        def _cbCheckLog(response):
            self.assertLogged(method=method, uri=uri, status=200,
                              length=0)

        d = self.getResponseFor(self.root, uri, method=method)
        d.addCallback(_cbCheckLog)

        return d

