def _parseTCP(factory, port, interface=""):
    return 'TCP', (int(port), factory), {'interface': interface}

def _parseUNIX(factory, address, mode='666'):
    return 'UNIX', (address, factory), {'mode': mode}

def _parseSSL(reactor, factory, port, privateKey="server.pem", certKey=None):
    from twisted.internet import ssl
    if certKey is None:
        certKey = privateKey
    cf = ssl.DefaultOpenSSLContextFactory(privateKey, certKey)
    return 'SSL', (port, factory, contextFactory)

funcs = {"tcp": _parseTCP,
         "unix": _parseUNIX,
         "ssl": _parseSSL}

def parse(description, factory):
    if ':' not in description:
        description = 'tcp:'+description
    dsplit = description.split(":")
    args = []
    kw = {}
    for arg in dsplit[1:]:
        kv = arg.split('=', 1)
        if len(kv) == 2:
            kw[kv[0]]=kv[1]
        else:
            args.append(arg)
    return funcs[dsplit[0]](factory, *args, **kw)

def service(description, factory):
    from twisted.application import internet
    name, args, kw = parse(description, factory)
    return getattr(internet, name+'Server')(*args, **kw)

def listen(description, factory):
    from twisted.internet import reactor
    name, args, kw = parse(description, factory)
    return getattr(reactor, 'listen'+name)(*args, **kw)
