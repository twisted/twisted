from twisted.internet import protocol, reactor
from twisted.trial import unittest
from twisted.cred import portal, checkers
import capserver

class StupidObj:
    __implements__ = capserver.IStupid
    def remote_gunk(self, arg, arg2):
        self.arg, arg2 = arg, arg2
        self.proto.sendSuccess("hi")
    remote_gunk.sig = (int, str)

class Realm:
    o = StupidObj()
    def requestAvatar(self, *args):
        return capserver.IStupid, self.o, lambda: None

class Test(unittest.TestCase):
    def setUp(self):
        self.rpc = capserver.AuthServer()
        self.f = protocol.Factory()
        self.rpc.factory = self.f
        self.r = Realm()
        self.f.portal = portal.Portal(self.r)
        self.rpc.connectionMade()

        checker = checkers.InMemoryUsernamePasswordDatabaseDontUse(user='password')
        self.f.portal.registerChecker(checker)

    def _command(self, cmdlist, result):
        l = []
        self.rpc.sendString = l.append
        map(self.rpc.stringReceived, cmdlist)
        for _ in range(50):
            reactor.iterate()
            if len(l) >= len(result):
                break
        self.assertEquals(l, result)

    def test_auth(self):
        self._command(['auth', 'user', 'password'], ['Success', capserver.AUTH_SUCCESS])
        self._command(['gunk', '5', 'foob'], ['Success', 'hi'])
