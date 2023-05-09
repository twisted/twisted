from typing import Any, Callable, Optional, Union

from zope.interface import implementer

from OpenSSL.SSL import Connection, Context

from twisted.internet._sslverify import PEMObjects
from twisted.internet.defer import Deferred
from twisted.internet.endpoints import TCP6ServerEndpoint
from twisted.internet.interfaces import (
    IListeningPort,
    IOpenSSLServerConnectionCreator,
    IOpenSSLServerConnectionCreatorFactory,
    IProtocolFactory,
    IReactorCore,
    IStreamServerEndpoint,
    IStreamServerEndpointStringParser,
)
from twisted.protocols._tls_legacy import SomeConnectionCreator
from twisted.protocols.tls import TLSMemoryBIOFactory, TLSMemoryBIOProtocol
from twisted.python.filepath import FilePath


@implementer(IOpenSSLServerConnectionCreator)
class SNIConnectionCreator(object):
    def __init__(
        self,
        contextLookup: Callable[[Union[bytes, None]], Context],
        connectionSetupHook: Callable[[Connection], None],
    ):
        self.contextLookup = contextLookup
        self.connectionSetupHook = connectionSetupHook
        self.defaultContext = self.contextLookup(None)

        def selectContext(connection: Connection) -> None:
            connection.set_context(self.contextLookup(connection.get_servername()))

        self.defaultContext.set_tlsext_servername_callback(selectContext)

    def serverConnectionForTLS(
        self,
        protocol: TLSMemoryBIOProtocol,
    ) -> Connection:
        """
        Construct an OpenSSL server connection.

        @param protocol: The protocol initiating a TLS connection.

        @return: a newly-created connection.
        """
        newConnection = Connection(self.defaultContext)
        self.connectionSetupHook(newConnection)
        return newConnection


@implementer(IOpenSSLServerConnectionCreatorFactory)
class ServerNameIndictionConfiguration:
    """ """

    def __init__(
        self, contextLookup: Callable[[bytes | None], Optional[Context]]
    ) -> None:
        """
        Initialize a L{ServerNameIndictionConfiguration} with a callable that
        can do a lookup for a L{Context}.
        """
        self.contextLookup = contextLookup

    def createServerCreator(
        self,
        connectionSetupHook: Callable[[Connection], None],
        contextSetupHook: Callable[[Context], None],
    ) -> IOpenSSLServerConnectionCreator:
        """ """

        def lookupAndSetup(name: bytes | None) -> Context:
            candidate = self.contextLookup(name)
            if candidate is None:
                if name is not None:
                    segments = name.split(b".")
                    segments[0] = b"*"
                    wildcardName = b".".join(segments)
                    candidate = self.contextLookup(wildcardName)

            if candidate is None:
                raise KeyError(f"no certificate for domain {name!r}")

            contextSetupHook(candidate)
            return candidate

        return SNIConnectionCreator(lookupAndSetup, connectionSetupHook)


from twisted.plugin import IPlugin


@implementer(IStreamServerEndpoint)
class TLSEndpoint(object):
    def __init__(
        self, endpoint: IStreamServerEndpoint, contextFactory: SomeConnectionCreator
    ) -> None:
        self.endpoint = endpoint
        self.contextFactory = contextFactory

    def listen(self, factory: IProtocolFactory) -> Deferred[IListeningPort]:
        return self.endpoint.listen(
            TLSMemoryBIOFactory(self.contextFactory, False, factory)
        )


@implementer(IPlugin, IStreamServerEndpointStringParser)
class TLSParser:
    """
    TLS server endpoint parser.
    """

    prefix: str = "tls"

    def _actualParseStreamServer(
        self,
        reactor: IReactorCore,
        path: str,
        port: str = "443",
        backlog: str = "50",
        interface: str = "::",
    ) -> IStreamServerEndpoint:
        """
        Actual parsing method, with detailed signature breaking out all parameters.
        """
        subEndpoint = TCP6ServerEndpoint(reactor, int(port), int(backlog), interface)
        certMap = PEMObjects.fromDirectory(FilePath(path)).inferDomainMapping()

        def lookup(name: Optional[bytes]) -> Optional[Context]:
            if name is None:
                name = list(certMap.keys())[0].encode()
            options = certMap.get(name.decode())
            if options is None:
                return None
            ctx = options.getContext()
            return ctx

        contextFactory = ServerNameIndictionConfiguration(lookup)
        return TLSEndpoint(subEndpoint, contextFactory)

    def parseStreamServer(
        self, reactor: IReactorCore, *args: Any, **kwargs: Any
    ) -> IStreamServerEndpoint:
        """
        Parse a TLS stream server.
        """
        return self._actualParseStreamServer(reactor, *args, **kwargs)
