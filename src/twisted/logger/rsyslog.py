import os
import platform
from datetime import datetime
from typing import Optional

from zope.interface import Interface, implementer

from twisted.internet import protocol
from twisted.logger import ILogObserver, LogEvent, LogLevel


def rsyslog(server="localhost", port=514, protocol="udp", facility=8):
    if protocol == "udp":
        transport = UDPSyslogTransport((server, port))
    else:
        raise ValueError("Invalid Protocol")

    return RemoteSyslogObserver(transport, facility)


class ISyslogTransport(Interface):
    def send(self, data: bytes) -> None:
        """
        Sends a single syslog message.

        @param data: encoded message to send.
        """


@implementer(ISyslogTransport)
class UDPSyslogTransport(protocol.DatagramProtocol):
    """
    UDP Transport for C{RemoteSyslogObserver}.
    """

    def __init__(self, address: tuple[str, int], *, maxDatagramBytes: int = 1024, reactor = None):
        """
        @param address: host and port of the remote syslog server.

        @param maxDatagramBytes: override maximum length of transported messages.
        """
        self.address = address
        self.maxDatagramBytes = maxDatagramBytes

        if reactor is None:
            from twisted.internet import reactor
        self._reactor = reactor

    def send(self, data: bytes) -> None:
        if not self.transport:
            self._reactor.listenUDP(0, self)

        self._reactor.callFromThread(
            self.transport.write, data[:self.maxDatagramBytes], self.address
        )


@implementer(ILogObserver)
class RemoteSyslogObserver:
    """
    Log observer that forwards to an RFC 3164 remote syslog server.

    @cvar severities: translates Twisted's C{LogLevel}s to syslog's.
    """

    # NOTE: we avoid importing Python's syslog module just for its LOG_*
    # constants, since that is not available on non-Unix systems.

    severities = {
        # no LogLevel equivalent for LOG_EMERG (0)
        # no LogLevel equivalent for LOG_ALERT (1)
        LogLevel.critical: 2,  # LOG_CRIT
        LogLevel.error: 3,  # LOG_ERR
        LogLevel.warn: 4,  # LOG_WARNING
        # no LogLevel equivalent for LOG_NOTICE (5)
        LogLevel.info: 6,  # LOG_INFO
        LogLevel.debug: 7,  # LOG_DEBUG
    }

    def __init__(
        self,
        transport: ISyslogTransport,
        facility: int = 8, # LOG_USER
        *,
        pid: Optional[int] = None,
        client_name: Optional[str] = None,
        encoding: str = "ASCII",
    ):
        """
        @param transport: Instance of a class implementing C{ISyslogTransport}.

        @param facility: Syslog facility number. See Python's C{syslog} module.
            Defaults to LOG_USER.

        @param pid: Optionally overwrite the process ID sent in syslog messages.
            Defaults to the actual PID.

        @param client_name: Optionally overwrite the client identifier sent in
            syslog messages. Defaults to the actual hostname.

        @param encoding: Encoding to use for log messages. Unrepresentable
            characters are dropped from the message.
        """
        self.transport = transport
        self.facility = facility  # syslog.LOG_* (already is n * 8)
        if self.facility & 0b111 != 0:
            raise ValueError("syslog facility must have lowest three bits cleared")
        if pid is None:
            pid = os.getpid()
        self.pid = pid
        if client_name is None:
            client_name, _, _ = platform.node().partition(".")
        self.client_name = client_name
        self.encoding = encoding

    def __call__(self, event: LogEvent) -> None:
        """
        Forward an event over syslog.

        @param event: An event.
        """
        severity = self.severities[event["log_level"]]
        program = event["log_namespace"]
        timestamp = datetime.fromtimestamp(event["log_time"]).strftime("%b %d %H:%M:%S")

        # message is broken up into lines, sent separately (as in twisted.python.syslog)
        for i, message in enumerate(event["log_format"].splitlines()):
            leader = "\t" if i else ""
            d = "<%d>%s %s %s[%d]: %s\n" % (
                self.facility + severity,
                timestamp,
                self.client_name,
                program,
                self.pid,
                leader + message,
            )

            self.transport.send(d.encode(self.encoding, "ignore"))
