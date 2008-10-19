# -*- test-case-name: twisted.test.test_strports -*-

# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

#
"""
Port description language

This module implements a description mini-language for ports, and provides
functions to parse it and to use it to directly construct appropriate
network server services or to directly listen on them.

Here are some examples::
 >>> s=service("80", server.Site())
 >>> s=service("tcp:80", server.Site())
 >>> s=service("tcp:80:interface=127.0.0.1", server.Site())
 >>> s=service("ssl:443", server.Site())
 >>> s=service("ssl:443:privateKey=mykey.pem", server.Site())
 >>> s=service("ssl:443:privateKey=mykey.pem:certKey=cert.pem", server.Site())
 >>> s=service("unix:/var/run/finger", FingerFactory())
 >>> s=service("unix:/var/run/finger:mode=660", FingerFactory())
 >>> p=listen("80", server.Site())
 >>> p=listen("tcp:80", server.Site())
 >>> p=listen("tcp:80:interface=127.0.0.1", server.Site())
 >>> p=listen("ssl:443", server.Site())
 >>> p=listen("ssl:443:privateKey=mykey.pem", server.Site())
 >>> p=listen("ssl:443:privateKey=mykey.pem:certKey=cert.pem", server.Site())
 >>> p=listen("unix:/var/run/finger", FingerFactory())
 >>> p=listen("unix:/var/run/finger:mode=660", FingerFactory())
 >>> p=listen("unix:/var/run/finger:lockfile=0", FingerFactory())

See specific function documentation for more information.

Maintainer: Moshe Zadka
"""
from __future__ import generators

def _parseTCP(factory, port, interface="", backlog=50):
    return (int(port), factory), {'interface': interface,
                                  'backlog': int(backlog)}



def _parseUNIX(factory, address, mode='666', backlog=50, lockfile=True):
    return (
        (address, factory),
        {'mode': int(mode, 8), 'backlog': int(backlog),
         'wantPID': bool(int(lockfile))})



def _parseSSL(factory, port, privateKey="server.pem", certKey=None,
              sslmethod=None, interface='', backlog=50):
    from twisted.internet import ssl
    if certKey is None:
        certKey = privateKey
    kw = {}
    if sslmethod is not None:
        kw['sslmethod'] = getattr(ssl.SSL, sslmethod)
    cf = ssl.DefaultOpenSSLContextFactory(privateKey, certKey, **kw)
    return ((int(port), factory, cf),
            {'interface': interface, 'backlog': int(backlog)})

_funcs = {"tcp": _parseTCP,
          "unix": _parseUNIX,
          "ssl": _parseSSL}

_OP, _STRING = range(2)
def _tokenize(description):
    current = ''
    ops = ':='
    nextOps = {':': ':=', '=': ':'}
    description = iter(description)
    for n in description:
        if n in ops:
            yield _STRING, current
            yield _OP, n
            current = ''
            ops = nextOps[n]
        elif n=='\\':
            current += description.next()
        else:
            current += n
    yield _STRING, current

def _parse(description):
    args, kw = [], {}
    def add(sofar):
        if len(sofar)==1:
            args.append(sofar[0])
        else:
            kw[sofar[0]] = sofar[1]
    sofar = ()
    for (type, value) in _tokenize(description):
        if type is _STRING:
            sofar += (value,)
        elif value==':':
            add(sofar)
            sofar = ()
    add(sofar)
    return args, kw 

def parse(description, factory, default=None):
    """
    Parse the description of a reliable virtual circuit server (that is, a
    TCP port, a UNIX domain socket or an SSL port) and return the data
    necessary to call the reactor methods to listen on the given socket with
    the given factory.

    An argument with no colons means a default port. Usually the default
    type is C{tcp}, but passing a non-C{None} value as C{default} will set
    that as the default. Otherwise, it is a colon-separated string.  The
    first part means the type -- currently, it can only be ssl, unix or tcp.
    After that, comes a list of arguments. Arguments can be positional or
    keyword, and can be mixed.  Keyword arguments are indicated by
    C{'name=value'}. If a value is supposed to contain a C{':'}, a C{'='} or
    a C{'\\'}, escape it with a C{'\\'}.

    For TCP, the arguments are the port (port number) and, optionally the
    interface (interface on which to listen) and backlog (how many clients
    to keep in the backlog).

    For UNIX domain sockets, the arguments are address (the file name of the
    socket) and optionally the mode (the mode bits of the file, as an octal
    number) and the backlog (how many clients to keep in the backlog).

    For SSL sockets, the arguments are the port (port number) and,
    optionally, the privateKey (file in which the private key is in),
    certKey (file in which the certification is in), sslmethod (the name of
    the SSL method to allow), the interface (interface on which to listen)
    and the backlog (how many clients to keep in the backlog).

    @type description: C{str}
    @type factory: L{twisted.internet.interfaces.IProtocolFactory}
    @type default: C{str} or C{None}
    @rtype: C{tuple}
    @return: a tuple of string, tuple and dictionary. The string is the name
    of the method (sans C{'listen'}) to call, and the tuple and dictionary
    are the arguments and keyword arguments to the method.
    @raises ValueError: if the string is formatted incorrectly.
    @raises KeyError: if the type is other than unix, ssl or tcp.
    """
    args, kw = _parse(description)
    if not args or (len(args)==1 and not kw):
        args[0:0] = [default or 'tcp']
    return (args[0].upper(),)+_funcs[args[0]](factory, *args[1:], **kw)

def service(description, factory, default=None):
    """Return the service corresponding to a description

    @type description: C{str}
    @type factory: L{twisted.internet.interfaces.IProtocolFactory}
    @type default: C{str} or C{None}
    @rtype: C{twisted.application.service.IService}
    @return: the service corresponding to a description of a reliable
    virtual circuit server.

    See the documentation of the C{parse} function for description
    of the semantics of the arguments.
    """
    from twisted.application import internet
    name, args, kw = parse(description, factory, default)
    return getattr(internet, name+'Server')(*args, **kw)

def listen(description, factory, default=None):
    """Listen on a port corresponding to a description

    @type description: C{str}
    @type factory: L{twisted.internet.interfaces.IProtocolFactory}
    @type default: C{str} or C{None}
    @rtype: C{twisted.internet.interfaces.IListeningPort}
    @return: the port corresponding to a description of a reliable
    virtual circuit server.

    See the documentation of the C{parse} function for description
    of the semantics of the arguments.
    """
    from twisted.internet import reactor
    name, args, kw = parse(description, factory, default)
    return getattr(reactor, 'listen'+name)(*args, **kw)

__all__ = ['parse', 'service', 'listen']
