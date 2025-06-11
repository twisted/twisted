import os
import platform
from datetime import datetime
from typing import Optional

from zope.interface import implementer

from twisted.internet import protocol, reactor
from twisted.logger import ILogObserver, LogEvent, LogLevel


class UDPSyslog(protocol.DatagramProtocol):
    def __init__(self, address: tuple[str, int]):
        self.address = address
        reactor.listenUDP(0, self)

    def send(self, data: bytes) -> None:
        self.transport.write(data, self.address)


@implementer(ILogObserver)
class RemoteSyslogObserver:
    """
    Log observer that forwards to an RFC 3164 remote syslog server.

    @cvar severities: translates Twisted's C{LogLevel}s to syslog's.
    """

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
        server: str,
        facility: int = 8,
        *,
        port: int = 514,
        handler: type[UDPSyslog] = UDPSyslog,
        pid: Optional[int] = None,
        client_name: Optional[str] = None,
        encoding: str = "ASCII",
    ):
        """
        @param server: Hostname or address of the remote syslog server.

        @param facility: Syslog facility number. See Python's C{syslog} module.
            Defaults to LOG_USER.

        @param port: Port the remote syslog server is listening on. Defaults to
            514.

        @param handler: Class implementing C{UDPSyslog}.

        @param pid: Optionally overwrite the process ID sent in syslog messages.
            Defaults to the actual PID.

        @param client_name: Optionally overwrite the client identifier sent in
            syslog messages. Defaults to the actual hostname.

        @param encoding: Encoding to use for log messages. Unrepresentable
            characters are dropped from the message.
        """
        # NOTE: facility=8 is LOG_USER.
        self.handler = handler((server, port))
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

            self.handler.send(d.encode(self.encoding, "ignore")[:1024])
