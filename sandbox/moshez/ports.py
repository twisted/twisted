def _parseTCP(factory, port, interface="", backlog=5):
    return (int(port), factory), {'interface': interface, 'backlog': backlog}

def _parseUNIX(factory, address, mode='666', backlog=5):
    return (address, factory), {'mode': int(mode, 8), 'backlog': backlog}

def _parseSSL(reactor, factory, port, privateKey="server.pem", certKey=None,
              sslmethod=None, interface='', backlog=5):
    from twisted.internet import ssl
    if certKey is None:
        certKey = privateKey
    kw = {}
    if sslmethod is not None:
        kw['sslmethod'] = getattr(ssl.SSL, sslmethod)
    cf = ssl.DefaultOpenSSLContextFactory(privateKey, certKey, **kw)
    return ((int(port), factory, contextFactory),
            {'interface': interface, 'backlog': backlog})

_funcs = {"tcp": _parseTCP,
         "unix": _parseUNIX,
         "ssl": _parseSSL}

def parse(description, factory):
    if ':' not in description:
        description = 'tcp:'+description
    dsplit = description.split(":")
    args = [arg for arg in dsplit[1:] if '=' not in arg]
    kw = {}
    for (name, val) in [arg.split('=', 1) for arg in dsplit if '=' in arg]:
        kw[name] = val
    return (dsplit[0].upper(),)+_funcs[dsplit[0]](factory, *args, **kw)

def service(description, factory):
    from twisted.application import internet
    name, args, kw = parse(description, factory)
    return getattr(internet, name+'Server')(*args, **kw)

def listen(description, factory):
    from twisted.internet import reactor
    name, args, kw = parse(description, factory)
    return getattr(reactor, 'listen'+name)(*args, **kw)

def _test():
    from twisted.protocols import wire
    from twisted.internet import protocol, reactor
    f = protocol.ServerFactory()
    f.protocol = wire.Echo
    listen("unix:lala", f)
    s = service("unix:lolo", f)
    s.startService()
    reactor.addSystemEventTrigger('before', 'shutdown', s.stopService)
    reactor.run()

if __name__ == '__main__':
    _test()
