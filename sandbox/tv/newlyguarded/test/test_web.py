from twisted.trial import unittest
from twisted.trial.util import wait
from twisted.internet import reactor, protocol, defer
from twisted.application import service, internet
from nevow import appserver, url
from login import createResource
from mechanize import Browser
import os, re
import ClientCookie

#ClientCookie.getLogger("ClientCookie").setLevel(ClientCookie.DEBUG)

class ChildProcessProtocol(protocol.ProcessProtocol):
    delayed = None
    _chldDbg = lambda self, msg: log.msg(childTimeout=msg)
    
    def __init__(self, doneLoading):
        self.doneLoading = doneLoading 
        self.errBuff = []
        self.childStdout = file('child.stdout', 'w')
        self.childStderr = file('child.stderr', 'w')
        self._processExited = defer.Deferred()

    def outReceived(self, data):
        self.childStdout.write(data)
        if 'set uid/gid' in data:
            d, self.doneLoading = self.doneLoading, None
            if d:
                d.callback("twistd ready")
        elif 'Server shut down' in data:
            d, self.shutDown = self.shutDown, None
            d.callback('server shut down')

    def errReceived(self, data):
        # something using twisted.internet.app is screwing this up
        self.childStderr.write(data)
        if 'DeprecationWarning' in data:
            return
        self.errBuff.append(data)

    def getErrBuf(self):
        buff, self.errBuff = self.errBuff, []
        return ''.join(buff)

    def processEnded(self, status):
        if self._processExited:
            self._processExited.callback(status)
        self.childStdout.close()
        self.childStderr.close()

    def shutdownOrKillYourself(self):
        # first, we'll try a SIGTERM
        import signal
        pid = self.transport.pid

        def _timeout():
            # and if that fails we STAB!
            self.transport.signalProcess('KILL')
            
        _delayed = reactor.callLater(0, _timeout)

        def _err(fail):
            # 'KILL' will cause an error to be raised, but that's okay because we
            # want it DEAD DEAD DEAD!
            from twisted.internet.error import ProcessTerminated
            fail.trap(ProcessTerminated)
            return None
        self._processExited.addErrback(_err)

        def _cleanup(ignore):
            if _delayed.active():
                _delayed.cancel()
        self._processExited.addBoth(_cleanup)

        if pid: 
            os.kill(pid, signal.SIGTERM)
        else:
            self._processExited = defer.succeed(None)

        return self._processExited

class ServerStartingMixin:
    def setUpClass(self):
        d = defer.Deferred()
        self.childProcess = ChildProcessProtocol(d)
        reactor.spawnProcess(self.childProcess,
                             'twistd',
                             ['twistd', '-l-', '-noy', 'login.tac'],
                             path='..',
                             env=None)
        wait(d)

    def tearDownClass(self):
        d = self.childProcess.shutdownOrKillYourself()
        wait(d)

class ActualTests:
    def test_main(self):
        b = self.browser
        b.open(self.url)
        self.assertEquals(b.title(), 'Main page')

    def test_unauth_secret(self):
        b = self.browser
        b.open(self.url)
        b.follow_link(text_regex=re.compile(r'deep secret'))
        self.assertEquals(b.title(), 'Log In')

    def test_unauth_another(self):
        b = self.browser
        b.open(self.url)
        b.follow_link(text_regex=re.compile(r'another deep'))
        self.assertEquals(b.title(), 'Log In')

    def test_auth_secret(self):
        b = self.browser
        b.open(self.url)
        b.follow_link(text_regex=re.compile(r'deep secret'))
        self.assertEquals(b.title(), 'Log In')
        b.select_form(name='login')
        b["username"] = "test"
        b["password"] = "test"
        b.submit()
        self.assertEquals(b.title(), "Hello!")
        url = b.geturl()
        self.failUnless(url.startswith(self.url))
        self.failUnless(url.endswith('/secret/stuff/stuff/stuff/'))

    def test_auth_another(self):
        b = self.browser
        b.open(self.url)
        b.follow_link(text_regex=re.compile(r'another deep'))
        self.assertEquals(b.title(), 'Log In')
        b.select_form(name='login')
        b["username"] = "test"
        b["password"] = "test"
        b.submit()
        self.assertEquals(b.title(), "Hello again!")
        url = b.geturl()
        self.failUnless(url.startswith(self.url))
        self.failUnless(url.endswith('/another/more/more/'))

    def test_auth_traversal(self):
        b = self.browser
        b.open(self.url)
        r=b.follow_link(text_regex=re.compile(r'secret'))
        self.assertEquals(b.title(), 'Log In')
        b.select_form(name='login')
        b["username"] = "test"
        b["password"] = "test"
        b.submit()
        self.assertEquals(b.title(), "Hello!")
        b.follow_link(text_regex=re.compile(r'up'))
        b.follow_link(text_regex=re.compile(r'another'))
        self.assertEquals(b.title(), "Hello again!")

    def test_public(self):
        b = self.browser
        b.open(self.url)
        b.follow_link(text_regex=re.compile(r'public'))
        self.assertEquals(b.title(), 'This is public')

    def test_public_secret(self):
        b = self.browser
        b.open(self.url)
        b.follow_link(text_regex=re.compile(r'public'))
        self.assertEquals(b.title(), 'This is public')
        b.follow_link(text_regex=re.compile(r'secret'))
        self.assertEquals(b.title(), 'Log In')
        b.select_form(name='login')
        b["username"] = "test"
        b["password"] = "test"
        b.submit()
        self.assertEquals(b.title(), "Hello!")
        url = b.geturl()
        self.failUnless(url.startswith(self.url))
        self.failUnless(url.endswith('/public/secret/'))


# TODO self.url = "http://localhost:8081/" won't work,
# as mechanize tries to look for cookies set by "localhost.local",
# of which there are none.

class WithCookies:
    def setUp(self):
        unittest.TestCase.setUp(self)
        self.url = "http://127.0.0.1:8081/prefix/"
        self.browser = Browser()

class TestWithCookies(WithCookies,
                      ServerStartingMixin,
                      ActualTests,
                      unittest.TestCase):
    pass

class DenyAllCookiesPolicy(ClientCookie.DefaultCookiePolicy):
    def set_ok(self, cookie, request, unverifiable):
        return False

class WithoutCookies:
    def setUp(self):
        unittest.TestCase.setUp(self)
        self.url = "http://127.0.0.1:8081/prefix/"
        self.browser = Browser()
        jar = ClientCookie.CookieJar(policy=DenyAllCookiesPolicy())
        self.browser.set_cookiejar(jar)

class TestWithoutCookies(WithoutCookies,
                         ServerStartingMixin,
                         ActualTests,
                         unittest.TestCase):
    pass

class ActualLoginTest:
    def test_login(self):
        b = self.browser
        b.open(self.url + self.path)
        self.assertEquals(b.title(), 'Log In')
        b.select_form(name='login')
        b["username"] = "test"
        b["password"] = "test"
        b.submit()
        self.assertEquals(b.title(), "Hello!")
        url = b.geturl()
        self.failUnless(url.startswith(self.url))
##         end = '/%s' % self.path
##         self.failUnless(url.endswith(end),
##                         "URL must end with %r, but was %r" % (end, url))

class LoginTest_SecretStuffStuff_noslash_cookie(ActualLoginTest,
                                                ServerStartingMixin,
                                                WithCookies,
                                                unittest.TestCase):
    path = 'secret/stuff/stuff'

class LoginTest_SecretStuffStuff_noslash_nocookie(ActualLoginTest,
                                                  ServerStartingMixin,
                                                  WithoutCookies,
                                                  unittest.TestCase):
    path = 'secret/stuff/stuff'

class LoginTest_SecretStuffStuff_slash_cookie(ActualLoginTest,
                                              ServerStartingMixin,
                                              WithCookies,
                                              unittest.TestCase):
    path = 'secret/stuff/stuff/'

class LoginTest_SecretStuffStuff_slash_nocookie(ActualLoginTest,
                                                ServerStartingMixin,
                                                WithoutCookies,
                                                unittest.TestCase):
    path = 'secret/stuff/stuff/'

class LoginTest_SecretStuff_noslash_cookie(ActualLoginTest,
                                           ServerStartingMixin,
                                           WithCookies,
                                           unittest.TestCase):
    path = 'secret/stuff'

class LoginTest_SecretStuff_noslash_nocookie(ActualLoginTest,
                                             ServerStartingMixin,
                                             WithoutCookies,
                                             unittest.TestCase):
    path = 'secret/stuff'

class LoginTest_SecretStuff_slash_cookie(ActualLoginTest,
                                         ServerStartingMixin,
                                         WithCookies,
                                         unittest.TestCase):
    path = 'secret/stuff/'

class LoginTest_SecretStuff_slash_nocookie(ActualLoginTest,
                                           ServerStartingMixin,
                                           WithoutCookies,
                                           unittest.TestCase):
    path = 'secret/stuff/'

class LoginTest_Secret_noslash_cookie(ActualLoginTest,
                                      ServerStartingMixin,
                                      WithCookies,
                                      unittest.TestCase):
    path = 'secret'

class LoginTest_Secret_noslash_nocookie(ActualLoginTest,
                                        ServerStartingMixin,
                                        WithoutCookies,
                                        unittest.TestCase):
    path = 'secret'

class LoginTest_Secret_slash_cookie(ActualLoginTest,
                                    ServerStartingMixin,
                                    WithCookies,
                                    unittest.TestCase):
    path = 'secret/'

class LoginTest_Secret_slash_nocookie(ActualLoginTest,
                                      ServerStartingMixin,
                                      WithoutCookies,
                                      unittest.TestCase):
    path = 'secret/'
