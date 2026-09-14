# -*- test-case-name: twisted.web.test.test_websocket -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Websocket (rfc6455) client and server support.

For websocket servers, place a L{WebSocketResource} into your Twisted Web
resource hierarchy.

For websocket clients, create a new endpoint via L{WebSocketClientEndpoint.new}
with the WebSocket server URL and then, on the newly created endpoint, call
L{WebSocketClientEndpoint.connect}.

Both client-side and server-side application code must conform to
L{WebSocketProtocol}.

@note: To use this module, you must install Twisted's C{websocket} extra, i.e.
    C{pip install twisted[websocket]}.
"""

from ._websocket_impl import (
    ConnectionRejected,
    WebSocketClientEndpoint,
    WebSocketClientFactory,
    WebSocketProtocol,
    WebSocketResource,
    WebSocketServerFactory,
    WebSocketTransport,
)

__all__ = [
    "ConnectionRejected",
    "WebSocketClientEndpoint",
    "WebSocketClientFactory",
    "WebSocketProtocol",
    "WebSocketResource",
    "WebSocketServerFactory",
    "WebSocketTransport",
]
