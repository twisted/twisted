# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
The parent class for all the SSH services.  Currently implemented services
are ssh-userauth and ssh-connection.

Maintainer: Paul Swartz
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Dict

from twisted.logger import Logger

if TYPE_CHECKING:
    from twisted.conch.ssh import transport as transport_module


class SSHService:
    # this is the ssh name for the service:
    name: bytes = None  # type:ignore[assignment]

    protocolMessages: Dict[int, str] = {}  # map #'s -> protocol names
    transport: transport_module.SSHTransportBase | None = None  # gets set later

    _log = Logger()

    def serviceStarted(self):
        """
        called when the service is active on the transport.
        """

    def serviceStopped(self):
        """
        called when the service is stopped, either by the connection ending
        or by another service being started
        """

    def logPrefix(self):
        return "SSHService {!r} on {}".format(
            self.name, self.transport.transport.logPrefix()
        )

    def packetReceived(self, messageNum, packet):
        """
        called when we receive a packet on the transport
        """
        # print self.protocolMessages
        if messageNum in self.protocolMessages:
            messageType = self.protocolMessages[messageNum]
            f = getattr(self, "ssh_%s" % messageType[4:], None)
            if f is not None:
                return f(packet)
        self._log.info(
            "couldn't handle {messageNum} {packet!r}",
            messageNum=messageNum,
            packet=packet,
        )
        self.transport.sendUnimplemented()
