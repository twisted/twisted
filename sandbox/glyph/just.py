from twisted.python import context

def _getReactor():
    from twisted.internet import reactor
    return reactor

def _listenTCP(reactor, factory, port, interface=""):
    # we don't really need to specify backlog, do we?
    return reactor.listenTCP(int(port), factory, interface=interface)

def _parsemode(m):
    return int(m,8)

def _listenUNIX(reactor, factory, address, mode='666'):
    return reactor.listenUNIX(address, factory, mode=mode)

from twisted.internet.ssl import DefaultOpenSSLContextFactory

def _listenSSL(reactor, factory, port, privateKey="server.pem", certKey=None):
    # ssl method, maybe?
    port = int(port)
    if certKey is None:
        certKey = privateKey
    cf = DefaultOpenSSLContextFactory(privateKey, certKey)
    return reactor.listenSSL(port, factory, contextFactory)

funcs = {"tcp": _listenTCP,
         "unix": _listenUNIX,
         "ssl": _listenSSL}

def listen(description, factory, reactor=None):
    reactor = reactor or context.get("reactor") or _getReactor()
    try:
        tcpPortNum = int(description)
    except ValueError:
        pass
    else:
        return reactor.listenTCP(tcpPortNum, factory)
    dsplit = description.split(":")
    args = []
    kw = {}
    for arg in dsplit[1:]:
        kv = arg.split('=')
        if len(kv) == 2:
            kw[kv[0]]=kv[1]
        else:
            args.append(arg)
    return funcs[dsplit[0]](reactor, factory, *args, **kw)


class Printermethod:
    def __init__(self, name):
        self.name = name
    def __call__(self, *args, **kw):
        print self.name, args, kw

class Printerooni:
    def __getattr__(self, name):
        return Printermethod(name)
    def __nonzero__(self):
        return 1

def test():
    p = Printerooni()
    f = None
    for s in ['80',
              'tcp:80',
              'tcp:80:127.0.0.1',
              'tcp:interface=127.0.0.1:port=80',
              # 'ssl:80', bleh ssl needs a real server.pem
              'unix:/home/bob/.twistd-web-pb']:
        listen(s,f,p)

test()
