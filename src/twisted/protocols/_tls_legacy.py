# -*- test-case-name: twisted.internet.test.test_endpoints.TLSEndpointsTests -*-
"""
Handler for the various legacy things that a C{contextFactory} can be.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Union
from warnings import warn

from OpenSSL.SSL import Connection, Context

from twisted.internet.interfaces import (
    IOpenSSLClientConnectionCreator,
    IOpenSSLContextFactory,
    IOpenSSLServerConnectionCreator,
)

if TYPE_CHECKING:
    # Circular import.
    from twisted.protocols.tls import TLSMemoryBIOProtocol

SomeConnectionCreator = Union[
    IOpenSSLContextFactory,
    IOpenSSLClientConnectionCreator,
    IOpenSSLServerConnectionCreator,
]


SingleArgFactory = Callable[["TLSMemoryBIOProtocol"], Connection]


class LegacyContextFactoryWarning(Warning):
    """
    You should be using a newer TLS context configuration interface.
    """


def older(olderMethod: Callable[[], Context]) -> SingleArgFactory:
    """
    Compatibility shim for L{IOpenSSLContextFactory.getContext}-style method to
    create(Client/Server)Creator.
    """

    def convert(p: TLSMemoryBIOProtocol) -> Connection:
        context = olderMethod()
        connection = Connection(context, None)
        return connection

    return convert


def oldest(isClient: bool, creator: object) -> SingleArgFactory:
    """
    Comptibility shim that does largely the same thing as L{older} but for
    things that don't even properly implement the old-style interface; check
    explicitly for the method and try to provide a useful assert if the object
    is just the wrong type rather than simply using an older API.
    """
    itype = "Client" if isClient else "Server"
    warn(
        f"{creator} does not explicitly provide any OpenSSL connection-"
        f"creator {itype} interface; neither IOpenSSL{itype}ConnectionCreator,"
        f" nor IOpenSSLContextFactory.",
        LegacyContextFactoryWarning,
        stacklevel=4,
    )
    getContext = getattr(creator, "getContext", None)
    if getContext is None:
        raise TypeError(f"{creator} does not even have a `getContext` method")
    if not isinstance(getContext(), Context):
        raise TypeError(f"{creator}'s `getContext` method doesn't return a `Context`")
    return older(getContext)


def _convertToAppropriateFactory(
    isClient: bool, creator: SomeConnectionCreator
) -> SingleArgFactory:
    """
    Upgrade a connection creator / context-factory-ish object into something
    with a signature like the most recent interface for building OpenSSL
    connection objects (i.e. like the methods on
    L{IOpenSSLClientConnectionCreator} and L{IOpenSSLServerConnectionCreator}),
    accounting for all the various interfaces older versions of Twisted used
    for context configuration.
    """
    baseCallable = (
        creator.clientConnectionForTLS
        if (isClient and IOpenSSLClientConnectionCreator.providedBy(creator))
        else (
            creator.serverConnectionForTLS
            if ((not isClient) and IOpenSSLServerConnectionCreator.providedBy(creator))
            else (
                older(creator.getContext)
                if IOpenSSLContextFactory.providedBy(creator)
                else oldest(isClient, creator)
            )
        )
    )

    def connectionFactory(protocol: TLSMemoryBIOProtocol) -> Connection:
        connection = baseCallable(protocol)
        if isClient:
            connection.set_connect_state()
        else:
            connection.set_accept_state()
        connection.set_app_data(protocol)
        return connection

    return connectionFactory
