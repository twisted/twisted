from twisted.trial import unittest

from twisted.application import service, internet
from nevow import appserver
from login import createResource
from mechanize import Browser
import re

class BrowsingTest(unittest.TestCase):
    def setUp(self):
        self.url = "http://localhost:8081/"

    def test_main(self):
        b = Browser()
        b.open(self.url)
        self.assertEquals(b.title(), 'Main page')

    def test_unauth_secret(self):
        b = Browser()
        b.open(self.url)
        b.follow_link(text_regex=re.compile(r'deep secret'))
        self.assertEquals(b.title(), 'Log In')

    def test_unauth_another(self):
        b = Browser()
        b.open(self.url)
        b.follow_link(text_regex=re.compile(r'another deep'))
        self.assertEquals(b.title(), 'Log In')

    def test_auth_secret(self):
        b = Browser()
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
        b = Browser()
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
        b = Browser()
        b.open(self.url)
        b.follow_link(text_regex=re.compile(r'secret'))
        self.assertEquals(b.title(), 'Log In')
        b.select_form(name='login')
        b["username"] = "test"
        b["password"] = "test"
        b.submit()
        self.assertEquals(b.title(), "Hello!")
        b.follow_link(text_regex=re.compile(r'up'))
        b.follow_link(text_regex=re.compile(r'another'))
        self.assertEquals(b.title(), "Hello again!")
