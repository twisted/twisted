from simpleconch import SimpleTransport
from twisted.internet import defer, reactor, protocol


def _bad(f):
    print f
def _connected(i):
    print i.getHostKey()
    d = i.authPublicKey('z3p', file('/home/z3p/.ssh/id_rsa').read())
#    d = i.authPassword('z3p', 'notmypassword')
    d.addCallback(_password,i)
    d.addErrback(_bad)
def _password(r,i):
    print 'worked!'
    assert i.isAuthenticated() 
    reactor.stop()

d = defer.Deferred()
protocol.ClientCreator(reactor, SimpleTransport, d).connectTCP('localhost', 22)
d.addCallback(_connected)
d.addErrback(_bad)
reactor.run()
