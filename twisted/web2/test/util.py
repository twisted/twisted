from twisted.python import components

class FakeChannel:
    def __init__(self, site):
        self.site = site


class FakeSite:
    pass


class FakeSession(components.Componentized):
    def __init__(self, avatar):
        components.Componentized.__init__(self)
        self.avatar = avatar
    def getLoggedInRoot(self):
        return self.avatar


fs = FakeSession(None)

class FakeRequest(components.Componentized):
    args = {}
    uri = ''
    path = ''
    failure = None
    context = None

    def __init__(self, headers=None, args=None, avatar=None):
        self.prepath = ['']
        self.postpath = ['']
        self.headers = headers or {}
        self.headers['referrer'] = '/'
        self.args = args or {}
        components.Componentized.__init__(self)
        self.sess = FakeSession(avatar)
        self.site = FakeSite()

    def URLPath(self):
        return url.URLPath.fromString('')

    def getSession(self):
        return self.sess

    v = ''
    def write(self, x):
        self.v += x

    finished=False
    def finish(self):
        self.finished = True

    def getHeader(self, key):
        return self.headers[key]

    def setHeader(self, key, val):
        self.headers[key] = val

    def setHost(self, host, port):
        self.headers["host"] = host

    def redirect(self, *args):
        pass

    def getRootURL(self):
        return ''

    def processingFailed(self, f):
        self.failure = f

from twisted.trial import unittest
import sys
class TestCase(unittest.TestCase):
    hasBools = (sys.version_info >= (2,3))

    # This should be migrated to Twisted.
    def failUnlessSubstring(self, containee, container, msg=None):
        self._assertions += 1
        if container.find(containee) == -1:
            raise unittest.FailTest, (msg or "%r not in %r" % (containee, container))
    def failIfSubstring(self, containee, container, msg=None):
        self._assertions += 1
        if container.find(containee) != -1:
            raise unittest.FailTest, (msg or "%r in %r" % (containee, container))
    
    assertSubstring = failUnlessSubstring
    assertNotSubstring = failIfSubstring

