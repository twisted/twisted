from typing import Callable, Union

from zope.interface import implementer

from OpenSSL.SSL import Connection, Context

from twisted.internet.interfaces import (
    IOpenSSLServerConnectionCreator,
    IOpenSSLServerConnectionCreatorFactory,
)
from twisted.protocols.tls import TLSMemoryBIOProtocol


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

    def __init__(self, contextLookup: Callable[[bytes | None], Context]) -> None:
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
            ctx = self.contextLookup(name)
            contextSetupHook(ctx)
            return ctx

        return SNIConnectionCreator(lookupAndSetup, connectionSetupHook)
