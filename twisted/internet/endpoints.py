# -*- test-case-name: twisted.internet.test.test_endpoints -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.
"""
Implementations of L{IStreamServerEndpoint} and L{IStreamClientEndpoint} that
wrap the L{IReactorTCP}, L{IReactorSSL}, and L{IReactorUNIX} interfaces.

This also implements an extensible mini-language for describing endpoints,
parsed by the L{clientFromString} and L{serverFromString} functions.

@since: 10.1
"""

from zope.interface import implements, directlyProvides
import warnings

from twisted.internet import interfaces, defer, error
from twisted.internet.protocol import ClientFactory, Protocol
from twisted.plugin import getPlugins
from twisted.internet.interfaces import IStreamServerEndpointStringParser
from twisted.internet.interfaces import IStreamClientEndpointStringParser
from twisted.python.filepath import FilePath



__all__ = ["clientFromString", "serverFromString",
           "TCP4ServerEndpoint", "TCP4ClientEndpoint",
           "UNIXServerEndpoint", "UNIXClientEndpoint",
           "SSL4ServerEndpoint", "SSL4ClientEndpoint"]


class _WrappingProtocol(Protocol):
    """
    Wrap another protocol in order to notify my user when a connection has
    been made.

    @ivar _connectedDeferred: The L{Deferred} that will callback
        with the C{wrappedProtocol} when it is connected.

    @ivar _wrappedProtocol: An L{IProtocol} provider that will be
        connected.
    """

    def __init__(self, connectedDeferred, wrappedProtocol):
        """
        @param connectedDeferred: The L{Deferred} that will callback
            with the C{wrappedProtocol} when it is connected.

        @param wrappedProtocol: An L{IProtocol} provider that will be
            connected.
        """
        self._connectedDeferred = connectedDeferred
        self._wrappedProtocol = wrappedProtocol

        if interfaces.IHalfCloseableProtocol.providedBy(
            self._wrappedProtocol):
            directlyProvides(self, interfaces.IHalfCloseableProtocol)

    def connectionMade(self):
        """
        Connect the C{self._wrappedProtocol} to our C{self.transport} and
        callback C{self._connectedDeferred} with the C{self._wrappedProtocol}
        """
        self._wrappedProtocol.makeConnection(self.transport)
        self._connectedDeferred.callback(self._wrappedProtocol)


    def dataReceived(self, data):
        """
        Proxy C{dataReceived} calls to our C{self._wrappedProtocol}
        """
        return self._wrappedProtocol.dataReceived(data)


    def connectionLost(self, reason):
        """
        Proxy C{connectionLost} calls to our C{self._wrappedProtocol}
        """
        return self._wrappedProtocol.connectionLost(reason)


    def readConnectionLost(self):
        """
        Proxy L{IHalfCloseableProtocol.readConnectionLost} to our
        C{self._wrappedProtocol}
        """
        self._wrappedProtocol.readConnectionLost()


    def writeConnectionLost(self):
        """
        Proxy L{IHalfCloseableProtocol.writeConnectionLost} to our
        C{self._wrappedProtocol}
        """
        self._wrappedProtocol.writeConnectionLost()



class _WrappingFactory(ClientFactory):
    """
    Wrap a factory in order to wrap the protocols it builds.

    @ivar _wrappedFactory:  A provider of I{IProtocolFactory} whose
        buildProtocol method will be called and whose resulting protocol
        will be wrapped.

    @ivar _onConnection: An L{Deferred} that fires when the protocol is
        connected
    """
    protocol = _WrappingProtocol

    def __init__(self, wrappedFactory, canceller):
        """
        @param wrappedFactory: A provider of I{IProtocolFactory} whose
            buildProtocol method will be called and whose resulting protocol
            will be wrapped.
        @param canceller: An object that will be called to cancel the
            L{self._onConnection} L{Deferred}
        """
        self._wrappedFactory = wrappedFactory
        self._onConnection = defer.Deferred(canceller=canceller)


    def buildProtocol(self, addr):
        """
        Proxy C{buildProtocol} to our C{self._wrappedFactory} or errback
        the C{self._onConnection} L{Deferred}.

        @return: An instance of L{_WrappingProtocol} or C{None}
        """
        try:
            proto = self._wrappedFactory.buildProtocol(addr)
        except:
            self._onConnection.errback()
        else:
            return self.protocol(self._onConnection, proto)


    def clientConnectionFailed(self, connector, reason):
        """
        Errback the C{self._onConnection} L{Deferred} when the
        client connection fails.
        """
        self._onConnection.errback(reason)



class TCP4ServerEndpoint(object):
    """
    TCP server endpoint with an IPv4 configuration

    @ivar _reactor: An L{IReactorTCP} provider.

    @type _port: int
    @ivar _port: The port number on which to listen for incoming connections.

    @type _backlog: int
    @ivar _backlog: size of the listen queue

    @type _interface: str
    @ivar _interface: the hostname to bind to, defaults to '' (all)
    """
    implements(interfaces.IStreamServerEndpoint)

    def __init__(self, reactor, port, backlog=50, interface=''):
        """
        @param reactor: An L{IReactorTCP} provider.
        @param port: The port number used listening
        @param backlog: size of the listen queue
        @param interface: the hostname to bind to, defaults to '' (all)
        """
        self._reactor = reactor
        self._port = port
        self._listenArgs = dict(backlog=50, interface='')
        self._backlog = backlog
        self._interface = interface


    def listen(self, protocolFactory):
        """
        Implement L{IStreamServerEndpoint.listen} to listen on a TCP socket
        """
        return defer.execute(self._reactor.listenTCP,
                             self._port,
                             protocolFactory,
                             backlog=self._backlog,
                             interface=self._interface)



class TCP4ClientEndpoint(object):
    """
    TCP client endpoint with an IPv4 configuration.

    @ivar _reactor: An L{IReactorTCP} provider.

    @type _host: str
    @ivar _host: The hostname to connect to as a C{str}

    @type _port: int
    @ivar _port: The port to connect to as C{int}

    @type _timeout: int
    @ivar _timeout: number of seconds to wait before assuming the
        connection has failed.

    @type _bindAddress: tuple
    @type _bindAddress: a (host, port) tuple of local address to bind
        to, or None.
    """
    implements(interfaces.IStreamClientEndpoint)

    def __init__(self, reactor, host, port, timeout=30, bindAddress=None):
        """
        @param reactor: An L{IReactorTCP} provider
        @param host: A hostname, used when connecting
        @param port: The port number, used when connecting
        @param timeout: number of seconds to wait before assuming the
            connection has failed.
        @param bindAddress: a (host, port tuple of local address to bind to,
            or None.
        """
        self._reactor = reactor
        self._host = host
        self._port = port
        self._timeout = timeout
        self._bindAddress = bindAddress


    def connect(self, protocolFactory):
        """
        Implement L{IStreamClientEndpoint.connect} to connect via TCP.
        """
        def _canceller(deferred):
            connector.stopConnecting()
            deferred.errback(
                error.ConnectingCancelledError(connector.getDestination()))

        try:
            wf = _WrappingFactory(protocolFactory, _canceller)
            connector = self._reactor.connectTCP(
                self._host, self._port, wf,
                timeout=self._timeout, bindAddress=self._bindAddress)
            return wf._onConnection
        except:
            return defer.fail()



class SSL4ServerEndpoint(object):
    """
    SSL secured TCP server endpoint with an IPv4 configuration.

    @ivar _reactor: An L{IReactorSSL} provider.

    @type _host: str
    @ivar _host: The hostname to connect to as a C{str}

    @type _port: int
    @ivar _port: The port to connect to as C{int}

    @type _sslContextFactory: L{OpenSSLCertificateOptions}
    @var _sslContextFactory: SSL Configuration information as an
        L{OpenSSLCertificateOptions}

    @type _backlog: int
    @ivar _backlog: size of the listen queue

    @type _interface: str
    @ivar _interface: the hostname to bind to, defaults to '' (all)
    """
    implements(interfaces.IStreamServerEndpoint)

    def __init__(self, reactor, port, sslContextFactory,
                 backlog=50, interface=''):
        """
        @param reactor: An L{IReactorSSL} provider.
        @param port: The port number used listening
        @param sslContextFactory: An instance of
            L{twisted.internet._sslverify.OpenSSLCertificateOptions}.
        @param timeout: number of seconds to wait before assuming the
            connection has failed.
        @param bindAddress: a (host, port tuple of local address to bind to,
            or None.
        """
        self._reactor = reactor
        self._port = port
        self._sslContextFactory = sslContextFactory
        self._backlog = backlog
        self._interface = interface


    def listen(self, protocolFactory):
        """
        Implement L{IStreamServerEndpoint.listen} to listen for SSL on a
        TCP socket.
        """
        return defer.execute(self._reactor.listenSSL, self._port,
                             protocolFactory,
                             contextFactory=self._sslContextFactory,
                             backlog=self._backlog,
                             interface=self._interface)



class SSL4ClientEndpoint(object):
    """
    SSL secured TCP client endpoint with an IPv4 configuration

    @ivar _reactor: An L{IReactorSSL} provider.

    @type _host: str
    @ivar _host: The hostname to connect to as a C{str}

    @type _port: int
    @ivar _port: The port to connect to as C{int}

    @type _sslContextFactory: L{OpenSSLCertificateOptions}
    @var _sslContextFactory: SSL Configuration information as an
        L{OpenSSLCertificateOptions}

    @type _timeout: int
    @ivar _timeout: number of seconds to wait before assuming the
        connection has failed.

    @type _bindAddress: tuple
    @ivar _bindAddress: a (host, port) tuple of local address to bind
        to, or None.
    """
    implements(interfaces.IStreamClientEndpoint)

    def __init__(self, reactor, host, port, sslContextFactory,
                 timeout=30, bindAddress=None):
        """
        @param reactor: An L{IReactorSSL} provider.
        @param host: A hostname, used when connecting
        @param port: The port number, used when connecting
        @param sslContextFactory: SSL Configuration information as An instance
            of L{OpenSSLCertificateOptions}.
        @param timeout: number of seconds to wait before assuming the
            connection has failed.
        @param bindAddress: a (host, port tuple of local address to bind to,
            or None.
        """
        self._reactor = reactor
        self._host = host
        self._port = port
        self._sslContextFactory = sslContextFactory
        self._timeout = timeout
        self._bindAddress = bindAddress


    def connect(self, protocolFactory):
        """
        Implement L{IStreamClientEndpoint.connect} to connect with SSL over
        TCP.
        """
        def _canceller(deferred):
            connector.stopConnecting()
            deferred.errback(
                error.ConnectingCancelledError(connector.getDestination()))

        try:
            wf = _WrappingFactory(protocolFactory, _canceller)
            connector = self._reactor.connectSSL(
                self._host, self._port, wf, self._sslContextFactory,
                timeout=self._timeout, bindAddress=self._bindAddress)
            return wf._onConnection
        except:
            return defer.fail()



class UNIXServerEndpoint(object):
    """
    UnixSocket server endpoint.

    @type path: str
    @ivar path: a path to a unix socket on the filesystem.

    @type _listenArgs: dict
    @ivar _listenArgs: A C{dict} of keyword args that will be passed
        to L{IReactorUNIX.listenUNIX}

    @var _reactor: An L{IReactorTCP} provider.
    """
    implements(interfaces.IStreamServerEndpoint)

    def __init__(self, reactor, address, backlog=50, mode=0666, wantPID=0):
        """
        @param reactor: An L{IReactorUNIX} provider.
        @param address: The path to the Unix socket file, used when listening
        @param listenArgs: An optional dict of keyword args that will be
            passed to L{IReactorUNIX.listenUNIX}
        @param backlog: number of connections to allow in backlog.
        @param mode: mode to set on the unix socket.  This parameter is
            deprecated.  Permissions should be set on the directory which
            contains the UNIX socket.
        @param wantPID: if True, create a pidfile for the socket.
        """
        self._reactor = reactor
        self._address = address
        self._backlog = backlog
        self._mode = mode
        self._wantPID = wantPID


    def listen(self, protocolFactory):
        """
        Implement L{IStreamServerEndpoint.listen} to listen on a UNIX socket.
        """
        return defer.execute(self._reactor.listenUNIX, self._address,
                             protocolFactory,
                             backlog=self._backlog,
                             mode=self._mode,
                             wantPID=self._wantPID)



class UNIXClientEndpoint(object):
    """
    UnixSocket client endpoint.

    @type _path: str
    @ivar _path: a path to a unix socket on the filesystem.

    @type _timeout: int
    @ivar _timeout: number of seconds to wait before assuming the connection
        has failed.

    @type _checkPID: bool
    @ivar _checkPID: if True, check for a pid file to verify that a server
        is listening.

    @var _reactor: An L{IReactorUNIX} provider.
    """
    implements(interfaces.IStreamClientEndpoint)

    def __init__(self, reactor, path, timeout=30, checkPID=0):
        """
        @param reactor: An L{IReactorUNIX} provider.
        @param path: The path to the Unix socket file, used when connecting
        @param timeout: number of seconds to wait before assuming the
            connection has failed.
        @param checkPID: if True, check for a pid file to verify that a server
            is listening.
        """
        self._reactor = reactor
        self._path = path
        self._timeout = timeout
        self._checkPID = checkPID


    def connect(self, protocolFactory):
        """
        Implement L{IStreamClientEndpoint.connect} to connect via a
        UNIX Socket
        """
        def _canceller(deferred):
            connector.stopConnecting()
            deferred.errback(
                error.ConnectingCancelledError(connector.getDestination()))

        try:
            wf = _WrappingFactory(protocolFactory, _canceller)
            connector = self._reactor.connectUNIX(
                self._path, wf,
                timeout=self._timeout,
                checkPID=self._checkPID)
            return wf._onConnection
        except:
            return defer.fail()



def _parseTCP(factory, port, interface="", backlog=50):
    """
    Internal parser function for L{_parseServer} to convert the string
    arguments for a TCP(IPv4) stream endpoint into the structured arguments.

    @param factory: the protocol factory being parsed, or C{None}.  (This was a
        leftover argument from when this code was in C{strports}, and is now
        mostly None and unused.)

    @type factory: L{IProtocolFactory} or C{NoneType}

    @param port: the integer port number to bind
    @type port: C{str}

    @param interface: the interface IP to listen on
    @param backlog: the length of the listen queue
    @type backlog: C{str}

    @return: a 2-tuple of (args, kwargs), describing  the parameters to
        L{IReactorTCP.listenTCP} (or, modulo argument 2, the factory, arguments
        to L{TCP4ServerEndpoint}.
    """
    return (int(port), factory), {'interface': interface,
                                  'backlog': int(backlog)}



def _parseUNIX(factory, address, mode='666', backlog=50, lockfile=True):
    """
    Internal parser function for L{_parseServer} to convert the string
    arguments for a UNIX (AF_UNIX/SOCK_STREAM) stream endpoint into the
    structured arguments.

    @param factory: the protocol factory being parsed, or C{None}.  (This was a
        leftover argument from when this code was in C{strports}, and is now
        mostly None and unused.)

    @type factory: L{IProtocolFactory} or C{NoneType}

    @param address: the pathname of the unix socket
    @type address: C{str}

    @param backlog: the length of the listen queue
    @type backlog: C{str}

    @param lockfile: A string '0' or '1', mapping to True and False
        respectively.  See the C{wantPID} argument to C{listenUNIX}

    @return: a 2-tuple of (args, kwargs), describing  the parameters to
        L{IReactorTCP.listenUNIX} (or, modulo argument 2, the factory,
        arguments to L{UNIXServerEndpoint}.
    """
    return (
        (address, factory),
        {'mode': int(mode, 8), 'backlog': int(backlog),
         'wantPID': bool(int(lockfile))})



def _parseSSL(factory, port, privateKey="server.pem", certKey=None,
              sslmethod=None, interface='', backlog=50):
    """
    Internal parser function for L{_parseServer} to convert the string
    arguments for an SSL (over TCP/IPv4) stream endpoint into the structured
    arguments.

    @param factory: the protocol factory being parsed, or C{None}.  (This was a
        leftover argument from when this code was in C{strports}, and is now
        mostly None and unused.)

    @type factory: L{IProtocolFactory} or C{NoneType}

    @param port: the integer port number to bind
    @type port: C{str}

    @param interface: the interface IP to listen on
    @param backlog: the length of the listen queue
    @type backlog: C{str}

    @param privateKey: The file name of a PEM format private key file.
    @type privateKey: C{str}

    @param certKey: The file name of a PEM format certificate file.
    @type certKey: C{str}

    @param sslmethod: The string name of an SSL method, based on the name of a
        constant in C{OpenSSL.SSL}.  Must be one of: "SSLv23_METHOD",
        "SSLv2_METHOD", "SSLv3_METHOD", "TLSv1_METHOD".
    @type sslmethod: C{str}

    @return: a 2-tuple of (args, kwargs), describing  the parameters to
        L{IReactorSSL.listenSSL} (or, modulo argument 2, the factory, arguments
        to L{SSL4ServerEndpoint}.
    """
    from twisted.internet import ssl
    if certKey is None:
        certKey = privateKey
    kw = {}
    if sslmethod is not None:
        kw['sslmethod'] = getattr(ssl.SSL, sslmethod)
    cf = ssl.DefaultOpenSSLContextFactory(privateKey, certKey, **kw)
    return ((int(port), factory, cf),
            {'interface': interface, 'backlog': int(backlog)})

_serverParsers = {"tcp": _parseTCP,
                  "unix": _parseUNIX,
                  "ssl": _parseSSL}

_OP, _STRING = range(2)

def _tokenize(description):
    """
    Tokenize a strports string and yield each token.

    @param description: a string as described by L{serverFromString} or
        L{clientFromString}.

    @return: an iterable of 2-tuples of (L{_OP} or L{_STRING}, string).  Tuples
        starting with L{_OP} will contain a second element of either ':' (i.e.
        'next parameter') or '=' (i.e. 'assign parameter value').  For example,
        the string 'hello:greet\=ing=world' would result in a generator
        yielding these values::

            _STRING, 'hello'
            _OP, ':'
            _STRING, 'greet=ing'
            _OP, '='
            _STRING, 'world'
    """
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
        elif n == '\\':
            current += description.next()
        else:
            current += n
    yield _STRING, current



def _parse(description):
    """
    Convert a description string into a list of positional and keyword
    parameters, using logic vaguely like what Python does.

    @param description: a string as described by L{serverFromString} or
        L{clientFromString}.

    @return: a 2-tuple of C{(args, kwargs)}, where 'args' is a list of all
        ':'-separated C{str}s not containing an '=' and 'kwargs' is a map of
        all C{str}s which do contain an '='.  For example, the result of
        C{_parse('a:b:d=1:c')} would be C{(['a', 'b', 'c'], {'d': '1'})}.
    """
    args, kw = [], {}
    def add(sofar):
        if len(sofar) == 1:
            args.append(sofar[0])
        else:
            kw[sofar[0]] = sofar[1]
    sofar = ()
    for (type, value) in _tokenize(description):
        if type is _STRING:
            sofar += (value,)
        elif value == ':':
            add(sofar)
            sofar = ()
    add(sofar)
    return args, kw


# Mappings from description "names" to endpoint constructors.
_endpointServerFactories = {
    'TCP': TCP4ServerEndpoint,
    'SSL': SSL4ServerEndpoint,
    'UNIX': UNIXServerEndpoint,
    }

_endpointClientFactories = {
    'TCP': TCP4ClientEndpoint,
    'SSL': SSL4ClientEndpoint,
    'UNIX': UNIXClientEndpoint,
    }


_NO_DEFAULT = object()

def _parseServer(description, factory, default=None):
    """
    Parse a stports description into a 2-tuple of arguments and keyword values.

    @param description: A description in the format explained by
        L{serverFromString}.
    @type description: C{str}

    @param factory: A 'factory' argument; this is left-over from
        twisted.application.strports, it's not really used.
    @type factory: L{IProtocolFactory} or L{None}

    @param default: Deprecated argument, specifying the default parser mode to
        use for unqualified description strings (those which do not have a ':'
        and prefix).
    @type default: C{str} or C{NoneType}

    @return: a 3-tuple of (plugin or name, arguments, keyword arguments)
    """
    args, kw = _parse(description)
    if not args or (len(args) == 1 and not kw):
        deprecationMessage = (
            "Unqualified strport description passed to 'service'."
            "Use qualified endpoint descriptions; for example, 'tcp:%s'."
            % (description,))
        if default is None:
            default = 'tcp'
            warnings.warn(
                deprecationMessage, category=DeprecationWarning, stacklevel=4)
        elif default is _NO_DEFAULT:
            raise ValueError(deprecationMessage)
        # If the default has been otherwise specified, the user has already
        # been warned.
        args[0:0] = [default]
    endpointType = args[0]
    parser = _serverParsers.get(endpointType)
    if parser is None:
        for plugin in getPlugins(IStreamServerEndpointStringParser):
            if plugin.prefix == endpointType: 
                return (plugin, args[1:], kw)
        raise ValueError("Unknown endpoint type: '%s'" % (endpointType,))
    return (endpointType.upper(),) + parser(factory, *args[1:], **kw)



def _serverFromStringLegacy(reactor, description, default):
    """
    Underlying implementation of L{serverFromString} which avoids exposing the
    deprecated 'default' argument to anything but L{strports.service}.
    """
    nameOrPlugin, args, kw = _parseServer(description, None, default)
    if type(nameOrPlugin) is not str:
        plugin = nameOrPlugin
        return plugin.parseStreamServer(reactor, *args, **kw)
    else:
        name = nameOrPlugin
    # Chop out the factory.
    args = args[:1] + args[2:]
    return _endpointServerFactories[name](reactor, *args, **kw)



def serverFromString(reactor, description):
    """
    Construct a stream server endpoint from an endpoint description string.

    The format for server endpoint descriptions is a simple string.  It is a
    prefix naming the type of endpoint, then a colon, then the arguments for
    that endpoint.

    For example, you can call it like this to create an endpoint that will
    listen on TCP port 80::

        serverFromString(reactor, "tcp:80")

    Additional arguments may be specified as keywords, separated with colons.
    For example, you can specify the interface for a TCP server endpoint to
    bind to like this::

        serverFromString(reactor, "tcp:80:interface=127.0.0.1")

    SSL server endpoints may be specified with the 'ssl' prefix, and the
    private key and certificate files may be specified by the C{privateKey} and
    C{certKey} arguments::

        serverFromString(reactor, "ssl:443:privateKey=key.pem:certKey=crt.pem")

    If a private key file name (C{privateKey}) isn't provided, a "server.pem"
    file is assumed to exist which contains the private key. If the certificate
    file name (C{certKey}) isn't provided, the private key file is assumed to
    contain the certificate as well.

    You may escape colons in arguments with a backslash, which you will need to
    use if you want to specify a full pathname argument on Windows::

        serverFromString(reactor,
            "ssl:443:privateKey=C\\:/key.pem:certKey=C\\:/cert.pem")

    finally, the 'unix' prefix may be used to specify a filesystem UNIX socket,
    optionally with a 'mode' argument to specify the mode of the socket file
    created by C{listen}::

        serverFromString(reactor, "unix:/var/run/finger")
        serverFromString(reactor, "unix:/var/run/finger:mode=660")

    This function is also extensible; new endpoint types may be registered as
    L{IStreamServerEndpointStringParser} plugins.  See that interface for more
    information.

    @param reactor: The server endpoint will be constructed with this reactor.

    @param description: The strports description to parse.

    @return: A new endpoint which can be used to listen with the parameters
        given by by C{description}.

    @rtype: L{IStreamServerEndpoint<twisted.internet.interfaces.IStreamServerEndpoint>}

    @raise ValueError: when the 'description' string cannot be parsed.

    @since: 10.2
    """
    return _serverFromStringLegacy(reactor, description, _NO_DEFAULT)



def quoteStringArgument(argument):
    """
    Quote an argument to L{serverFromString} and L{clientFromString}.  Since
    arguments are separated with colons and colons are escaped with
    backslashes, some care is necessary if, for example, you have a pathname,
    you may be tempted to interpolate into a string like this::

        serverFromString("ssl:443:privateKey=%s" % (myPathName,))

    This may appear to work, but will have portability issues (Windows
    pathnames, for example).  Usually you should just construct the appropriate
    endpoint type rather than interpolating strings, which in this case would
    be L{SSL4ServerEndpoint}.  There are some use-cases where you may need to
    generate such a string, though; for example, a tool to manipulate a
    configuration file which has strports descriptions in it.  To be correct in
    those cases, do this instead::

        serverFromString("ssl:443:privateKey=%s" %
                         (quoteStringArgument(myPathName),))

    @param argument: The part of the endpoint description string you want to
        pass through.

    @type argument: C{str}

    @return: The quoted argument.

    @rtype: C{str}
    """
    return argument.replace('\\', '\\\\').replace(':', '\\:')



def _parseClientTCP(**kwargs):
    """
    Perform any argument value coercion necessary for TCP client parameters.

    Valid keyword arguments to this function are all L{IReactorTCP.connectTCP}
    arguments.

    @return: The coerced values as a C{dict}.
    """
    kwargs['port'] = int(kwargs['port'])
    try:
        kwargs['timeout'] = int(kwargs['timeout'])
    except KeyError:
        pass
    return kwargs



def _loadCAsFromDir(directoryPath):
    """
    Load certificate-authority certificate objects in a given directory.

    @param directoryPath: a L{FilePath} pointing at a directory to load .pem
        files from.

    @return: a C{list} of L{OpenSSL.crypto.X509} objects.
    """
    from twisted.internet import ssl

    caCerts = {}
    for child in directoryPath.children():
        if not child.basename().split('.')[-1].lower() == 'pem':
            continue
        try:
            data = child.getContent()
        except IOError:
            # Permission denied, corrupt disk, we don't care.
            continue
        try:
            theCert = ssl.Certificate.loadPEM(data)
        except ssl.SSL.Error:
            # Duplicate certificate, invalid certificate, etc.  We don't care.
            pass
        else:
            caCerts[theCert.digest()] = theCert.original
    return caCerts.values()



def _parseClientSSL(**kwargs):
    """
    Perform any argument value coercion necessary for SSL client parameters.

    Valid keyword arguments to this function are all L{IReactorSSL.connectSSL}
    arguments except for C{contextFactory}.  Instead, C{certKey} (the path name
    of the certificate file) C{privateKey} (the path name of the private key
    associated with the certificate) are accepted and used to construct a
    context factory.
    
    @param caCertsDir: The one parameter which is not part of
        L{IReactorSSL.connectSSL}'s signature, this is a path name used to
        construct a list of certificate authority certificates.  The directory
        will be scanned for files ending in C{.pem}, all of which will be
        considered valid certificate authorities for this connection.

    @type caCertsDir: C{str}

    @return: The coerced values as a C{dict}.
    """
    from twisted.internet import ssl
    kwargs = _parseClientTCP(**kwargs)
    certKey = kwargs.pop('certKey', None)
    privateKey = kwargs.pop('privateKey', None)
    caCertsDir = kwargs.pop('caCertsDir', None)
    if certKey is not None:
        certx509 = ssl.Certificate.loadPEM(
            FilePath(certKey).getContent()).original
    else:
        certx509 = None
    if privateKey is not None:
        privateKey = ssl.PrivateCertificate.loadPEM(
            FilePath(privateKey).getContent()).privateKey.original
    else:
        privateKey = None
    if caCertsDir is not None:
        verify = True
        caCerts = _loadCAsFromDir(FilePath(caCertsDir))
    else:
        verify = False
        caCerts = None
    kwargs['sslContextFactory'] = ssl.CertificateOptions(
        method=ssl.SSL.SSLv23_METHOD,
        certificate=certx509,
        privateKey=privateKey,
        verify=verify,
        caCerts=caCerts
    )
    return kwargs



def _parseClientUNIX(**kwargs):
    """
    Perform any argument value coercion necessary for UNIX client parameters.

    Valid keyword arguments to this function are all L{IReactorUNIX.connectUNIX}
    arguments except for C{checkPID}.  Instead, C{lockfile} is accepted and has
    the same meaning.

    @return: The coerced values as a C{dict}.
    """
    try:
        kwargs['checkPID'] = bool(int(kwargs.pop('lockfile')))
    except KeyError:
        pass
    try:
        kwargs['timeout'] = int(kwargs['timeout'])
    except KeyError:
        pass
    return kwargs

_clientParsers = {
    'TCP': _parseClientTCP,
    'SSL': _parseClientSSL,
    'UNIX': _parseClientUNIX,
    }



def clientFromString(reactor, description):
    """
    Construct a client endpoint from a description string.

    Client description strings are much like server description strings,
    although they take all of their arguments as keywords, since even the
    simplest client endpoint (plain TCP) requires at least 2 arguments (host
    and port) to construct.

    You can create a TCP client endpoint with the 'host' and 'port' arguments,
    like so::

        clientFromString(reactor, "tcp:host=www.example.com:port=80")

    or an SSL client endpoint with those arguments, plus the arguments used by
    the server SSL, for a client certificate::

        clientFromString(reactor, "ssl:host=web.example.com:port=443:"
                                  "privateKey=foo.pem:certKey=foo.pem")

    to specify your certificate trust roots, you can identify a directory with
    PEM files in it with the C{caCertsDir} argument::

        clientFromString(reactor, "ssl:host=web.example.com:port=443:"
                                  "caCertsDir=/etc/ssl/certs")

    This function is also extensible; new endpoint types may be registered as
    L{IStreamClientEndpointStringParser} plugins.  See that interface for more
    information.

    @param reactor: The client endpoint will be constructed with this reactor.

    @param description: The strports description to parse.

    @return: A new endpoint which can be used to connect with the parameters
        given by by C{description}.
    @rtype: L{IStreamClientEndpoint<twisted.internet.interfaces.IStreamClientEndpoint>}

    @since: 10.2
    """
    args, kwargs = _parse(description)
    aname = args.pop(0)
    name = aname.upper()
    for plugin in getPlugins(IStreamClientEndpointStringParser):
        if plugin.prefix.upper() == name:
            return plugin.parseStreamClient(*args, **kwargs)
    if name not in _clientParsers:
        raise ValueError("Unknown endpoint type: %r" % (aname,))
    kwargs = _clientParsers[name](*args, **kwargs)
    return _endpointClientFactories[name](reactor, **kwargs)
