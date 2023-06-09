"""
Handler for the various legacy things that a C{contextFactory} can be.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Union
from warnings import warn

from OpenSSL.SSL import Connection, Context

from twisted.internet.interfaces import (
    IOpenSSLClientConnectionCreator,
    IOpenSSLClientConnectionCreatorFactory,
    IOpenSSLContextFactory,
    IOpenSSLServerConnectionCreator,
    IOpenSSLServerConnectionCreatorFactory,
)

if TYPE_CHECKING:
    # Circular import.
    from twisted.protocols.tls import TLSMemoryBIOProtocol

SomeConnectionCreator = Union[
    IOpenSSLContextFactory,
    IOpenSSLClientConnectionCreator,
    IOpenSSLClientConnectionCreatorFactory,
    IOpenSSLServerConnectionCreator,
    IOpenSSLServerConnectionCreatorFactory,
]


ConnectionHook = Callable[[Connection], None]
ContextHook = Callable[[Context], None]
CreatorFactory = Callable[
    [ConnectionHook, ContextHook],
    Connection,
]


SingleArgFactory = Callable[["TLSMemoryBIOProtocol"], Connection]


def old(
    oldMethod: SingleArgFactory,
    connectionSetup: ConnectionHook,
    contextSetup: ContextHook,
) -> SingleArgFactory:
    """
    Compatibility shim for (client/server)ConnectionForTLS to
    create(Client/Server)Creator signature.
    """

    def convert(p: TLSMemoryBIOProtocol) -> Connection:
        connection = oldMethod(p)
        connectionSetup(connection)
        contextSetup(connection.get_context())
        return connection

    return convert


def older(
    olderMethod: Callable[[], Context],
    connectionSetup: ConnectionHook,
    contextSetup: ContextHook,
) -> SingleArgFactory:
    """
    Compatibility shim for L{IOpenSSLContextFactory.getContext}-style method to
    create(Client/Server)Creator.
    """

    def convert(p: TLSMemoryBIOProtocol) -> Connection:
        context = olderMethod()
        connection = Connection(context, None)
        connectionSetup(connection)
        contextSetup(context)
        return connection

    return convert


def oldest(
    isClient: bool,
    creator: object,
    connectionSetup: ConnectionHook,
    contextSetup: ContextHook,
) -> SingleArgFactory:
    """
    Comptibility shim that does largely the same thing as L{older} but for
    things that don't even properly implement the old-style interface; check
    explicitly for the method and try to provide a useful assert if the object
    is just the wrong type rather than simply using an older API.
    """
    itype = "Client" if isClient else "Server"
    warn(
        f"{creator} does not explicitly provide any OpenSSL connection-"
        f"creator {itype} interface; "
        f"neither IOpenSSL{itype}ConnectionCreatorFactory, nor IOpenSSL"
        f"{itype}ConnectionCreator, nor IOpenSSLContextFactory."
    )
    getContext = getattr(creator, "getContext", None)
    assert getContext is not None, f"{creator} does not even have a `getContext` method"
    assert isinstance(
        getContext(), Context
    ), f"{creator}'s `getContext` method doesn't return a `Context`"

    return older(getContext, connectionSetup, contextSetup)


def _convertToAppropriateFactory(
    isClient: bool,
    creator: SomeConnectionCreator,
    connectionSetup: ConnectionHook,
    contextSetup: ContextHook,
) -> SingleArgFactory:
    """
    Upgrade a connection creator / context-factory-ish object into something
    with a signature like the most recent interface for building OpenSSL
    context objects (L{IOpenSSLClientCreationCreatorFactory}), accounting for
    all the various interfaces older versions of Twisted used for context
    configuration.
    """

    if isClient:
        if IOpenSSLClientConnectionCreatorFactory.providedBy(creator):
            return creator.createClientCreator(
                connectionSetup, contextSetup
            ).clientConnectionForTLS
        if IOpenSSLClientConnectionCreator.providedBy(creator):
            return old(creator.clientConnectionForTLS, connectionSetup, contextSetup)
    else:
        if IOpenSSLServerConnectionCreatorFactory.providedBy(creator):
            return creator.createServerCreator(
                connectionSetup, contextSetup
            ).serverConnectionForTLS
        if IOpenSSLServerConnectionCreator.providedBy(creator):
            return old(creator.serverConnectionForTLS, connectionSetup, contextSetup)
    if IOpenSSLContextFactory.providedBy(creator):
        return older(creator.getContext, connectionSetup, contextSetup)

    return oldest(isClient, creator, connectionSetup, contextSetup)
