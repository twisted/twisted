# Twisted, the Framework of Your Internet
# Copyright (C) 2001-2003 Matthew W. Lefkowitz
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
"""Port description language

This module implements a description mini-language for ports, and provides
functions to parse it and to use it to directly construct appropriate
network server services or to directly listen on them.

API Stability: unstable

Maintainer: U{Moshe Zadka<mailto:moshez@twistedmatrix.com>}
"""

def _parseTCP(factory, port, interface="", backlog=5):
    return (int(port), factory), {'interface': interface, 'backlog': backlog}

def _parseUNIX(factory, address, mode='666', backlog=5):
    return (address, factory), {'mode': int(mode, 8), 'backlog': backlog}

def _parseSSL(factory, port, privateKey="server.pem", certKey=None,
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
    """Parse a description of a reliable virtual circuit server

    @type description: C{str}
    @type factory: C{twisted.internet.interfaces.IProtocolFactory}
    @rtype: C{tuple}
    @return: a tuple of string, tuple and dictionary. The string
    is the name of the method (sans C{'listen'}) to call, and
    the tuple and dictionary are the arguments and keyword arguments
    to the method.
    @raises: C{ValueError} if the string is formatted incorrectly,
    C{KeyError} if the type is other than unix, ssl or tcp.

    Parse the description of a reliable virtual circuit server (that is,
    a TCP port, a UNIX domain socket or an SSL port) and return the
    data necessary to call the reactor methods to listen on the given
    socket with the given factory.

    A simple numeric argument means a TCP port. Otherwise, it is a
    colon-separated string. The first part means the type -- currently,
    it can only be ssl, unix or tcp. After that, comes a list of
    arguments. Arguments can be positional or keyword, and can be mixed.
    Keyword arguments are indicated by C{'name=value'}. Obviously, a value
    which contain an C{'='} can only be given positionally.

    For TCP, the arguments are the port (port number) and, optionally the
    interface (interface on which to listen) and backlog (how many clients to
    keep in the backlog).

    For UNIX domain sockets, the arguments are address (the file name of the
    socket) and optionally the mode (the mode bits of the file, as an octal
    number) and the backlog (how many clients to keep in the backlog).

    For SSL sockets, the arguments are the port (port number) and, optionally,
    the privateKey (file in which the private key is in), certKey (file in
    which the certification is in), sslmethod (the name of the SSL method
    to allow), the interface (interface on which to listen) and the
    backlog (how many clients to keep in the backlog).
    """
    if ':' not in description:
        description = 'tcp:'+description
    dsplit = description.split(":")
    args = [arg for arg in dsplit[1:] if '=' not in arg]
    kw = {}
    for (name, val) in [arg.split('=', 1) for arg in dsplit if '=' in arg]:
        kw[name] = val
    return (dsplit[0].upper(),)+_funcs[dsplit[0]](factory, *args, **kw)

def service(description, factory):
    """Return the service corresponding to a description

    @type description: C{str}
    @type factory: C{twisted.internet.interfaces.IProtocolFactory}
    @rtype: C{twisted.application.service.IService}
    @return: the service corresponding to a description of a reliable
    virtual circuit server.

    See the documentation of the C{parse} function for description
    of the semantics of the arguments.
    """
    from twisted.application import internet
    name, args, kw = parse(description, factory)
    return getattr(internet, name+'Server')(*args, **kw)

def listen(description, factory):
    """Listen on a port corresponding to a description

    @type description: C{str}
    @type factory: C{twisted.internet.interfaces.IProtocolFactory}
    @rtype: C{twisted.internet.interfaces.IListeningPort}
    @return: the port corresponding to a description of a reliable
    virtual circuit server.

    See the documentation of the C{parse} function for description
    of the semantics of the arguments.
    """
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
