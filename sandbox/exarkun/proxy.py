# -*- coding: Latin-1 -*-

from twisted.python import usage

def URLDescriptor(s):
    """URLDescriptor(protocol%state%details)"""
    descriptors = {
        'unix': UNIXDescriptor,
        'tcp': TCPDescriptor,
        'udp': UDPDescriptor,
        'ssl': SSLDescriptor,
        'ipv6': IPV6Descriptor,
    }
    modes = {
        'C': 'connect%s',
        'c': 'connect%s',
        'S': 'listen%s',
        's': 'listen%s',
    }

    parts = s.split('%', 2)
    if len(parts) != 3:
        raise usage.UsageError, "illegal descriptor"
    if parts[0] not in descriptors:
        raise usage.UsageError, "unknown descriptor: %r" % (parts[0],)
    if parts[1] not in modes:
        raise usage.UsageError, "Mode must be C or S, not %r" % (parts[1],)

    result = {'method': modes[parts[1]] % (parts[0].upper(),)}
    result.update(descriptors[parts[0]](parts[2:], isClient=(parts[1] in 'Cc')))
    return result

def UNIXDescriptor(s, isClient):
    """UNIXDescriptor(unix socket filename)"""
    return {'filename': s[0]}

def TCPDescriptor(s, isClient):
    """TCPDescriptor(hostname:port)"""
    s = s.split(':', 1)
    if len(s) != 2:
        raise usage.UsageError, "not enough arguments"
    s[1] = int(s[1])
    return {isClient and 'interface' or 'host': s[0], 'port': s[1]}

UDPDescriptor = IPV6Descriptor = TCPDescriptor

def SSLDescriptor(s, isClient):
    """SSLDescriptor(private key file!certificate file!hostname:port)"""
    if isClient:
        raise usage.UsageError, "client ssl not yet supported"
    else:
        s = s.split('!', 2)
        if len(s) != 2:
            raise usage.UsageError, "not enough arguments"
        from twisted.internet.ssl import DefaultOpenSSLContextFactory
        ctx = DefaultOpenSSLContextFactory(s[0], s[1])
        results = {'ctxFactory': ctx}
        results.update(TCPDescriptor(s[2:]))
        return results

class Options(usage.Options):
    optParameters = [
        ["input", "i", None, "descriptor url to serve from"],
    ]
    
    def __init__(self):
        usage.Options.__init__(self)
        self.outputs = []
    
    def opt_output(self, arg):
        """descriptor url to serve to"""
        self.outputs.append(arg)
    
    def postOptions(self):
        if not self.input:
            raise usage.UsageError, "input is required"
        self.input = URLDescriptor(self['input'])
        if not self.outputs:
            raise usage.UsageError, "output is required"
        self.outputs = map(URLDescriptor, self.outputs)

from twisted.web import distrib
from twisted.web import server

def updateApplication(app, config):
    # We just need one factory, serving the input to the output
    # ResourceSubscriber sucks

    #del config.input['method']
    #root = distrib.ResourceSubscription(**config.input)
    root = distrib.ResourceSubscription('unix', 'proxy.pub')
    site = server.Site(root)

    # method = config.input['method']
    # del config.input['method']
    # getattr(app, method)(factory=site, **config.input)

    for o in config.outputs:
        method = o['method']
        del o['method']
        getattr(app, method)(factory=site, **o)
