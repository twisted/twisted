from twisted.trial import unittest

from twisted.application import service, internet
from nevow import appserver
from login import createResource
from mechanize import Browser
import re
import ClientCookie

#ClientCookie.getLogger("ClientCookie").setLevel(ClientCookie.DEBUG)

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
        self.url = "http://127.0.0.1:8081/prefix/"
        self.browser = Browser()

class TestWithCookies(ActualTests, WithCookies, unittest.TestCase):
    pass

class DenyAllCookiesPolicy(ClientCookie.DefaultCookiePolicy):
    def set_ok(self, cookie, request, unverifiable):
        return False

class WithoutCookies:
    def setUp(self):
        self.url = "http://127.0.0.1:8081/prefix/"
        self.browser = Browser()
        jar = ClientCookie.CookieJar(policy=DenyAllCookiesPolicy())
        self.browser.set_cookiejar(jar)

class TestWithoutCookies(ActualTests, WithoutCookies, unittest.TestCase):
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
                                                WithCookies,
                                                unittest.TestCase):
    path = 'secret/stuff/stuff'

class LoginTest_SecretStuffStuff_noslash_nocookie(ActualLoginTest,
                                                  WithoutCookies,
                                                  unittest.TestCase):
    path = 'secret/stuff/stuff'

class LoginTest_SecretStuffStuff_slash_cookie(ActualLoginTest,
                                              WithCookies,
                                              unittest.TestCase):
    path = 'secret/stuff/stuff/'

class LoginTest_SecretStuffStuff_slash_nocookie(ActualLoginTest,
                                                WithoutCookies,
                                                unittest.TestCase):
    path = 'secret/stuff/stuff/'

class LoginTest_SecretStuff_noslash_cookie(ActualLoginTest,
                                           WithCookies,
                                           unittest.TestCase):
    path = 'secret/stuff'

class LoginTest_SecretStuff_noslash_nocookie(ActualLoginTest,
                                             WithoutCookies,
                                             unittest.TestCase):
    path = 'secret/stuff'

class LoginTest_SecretStuff_slash_cookie(ActualLoginTest,
                                         WithCookies,
                                         unittest.TestCase):
    path = 'secret/stuff/'

class LoginTest_SecretStuff_slash_nocookie(ActualLoginTest,
                                           WithoutCookies,
                                           unittest.TestCase):
    path = 'secret/stuff/'

class LoginTest_Secret_noslash_cookie(ActualLoginTest,
                                      WithCookies,
                                      unittest.TestCase):
    path = 'secret'

class LoginTest_Secret_noslash_nocookie(ActualLoginTest,
                                        WithoutCookies,
                                        unittest.TestCase):
    path = 'secret'

class LoginTest_Secret_slash_cookie(ActualLoginTest,
                                    WithCookies,
                                    unittest.TestCase):
    path = 'secret/'

class LoginTest_Secret_slash_nocookie(ActualLoginTest,
                                      WithoutCookies,
                                      unittest.TestCase):
    path = 'secret/'
