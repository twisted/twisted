from twisted.trial import unittest
from nevow import url
from login import getActionURL

class TestActionURL(unittest.TestCase):
    def test_sss(self):
        self.assertEquals(
            str(getActionURL(url.URL.fromString('http://127.0.0.1:8081/secret/stuff/stuff'),
                             ['secret', 'stuff', 'stuff'])),
            'http://127.0.0.1:8081/__login__/secret/stuff/stuff')
            #'http://127.0.0.1:8081/secret/__login__/secret/stuff/stuff'

    def test_nocookie_sss(self):
        self.assertEquals(
            str(getActionURL(url.URL.fromString('http://127.0.0.1:8081/__session_key__xyzzy/secret/stuff/stuff'),
                             ['secret', 'stuff', 'stuff'])),
            'http://127.0.0.1:8081/__session_key__xyzzy/__login__/secret/stuff/stuff')
            #http://127.0.0.1:8081/__login__/secret/stuff/stuff

    def test_sss_slash(self):
        self.assertEquals(
            str(getActionURL(url.URL.fromString('http://127.0.0.1:8081/secret/stuff/stuff/'),
                             ['secret', 'stuff', 'stuff', ''])),
            'http://127.0.0.1:8081/__login__/secret/stuff/stuff/')

    def test_ss(self):
        self.assertEquals(
            str(getActionURL(url.URL.fromString('http://127.0.0.1:8081/secret/stuff'),
                             ['secret', 'stuff'])),
            'http://127.0.0.1:8081/__login__/secret/stuff')
            #'http://127.0.0.1:8081/secret/__login__/secret/stuff'

    def test_ss_slash(self):
        self.assertEquals(
            str(getActionURL(url.URL.fromString('http://127.0.0.1:8081/secret/stuff/'),
                             ['secret', 'stuff', ''])),
            'http://127.0.0.1:8081/__login__/secret/stuff/')

    def test_s(self):
        self.assertEquals(
            str(getActionURL(url.URL.fromString('http://127.0.0.1:8081/secret'),
                             ['secret'])),
            'http://127.0.0.1:8081/__login__/secret')

    def test_ss_slash(self):
        self.assertEquals(
            str(getActionURL(url.URL.fromString('http://127.0.0.1:8081/secret/'),
                             ['secret', ''])),
            'http://127.0.0.1:8081/__login__/secret/')
