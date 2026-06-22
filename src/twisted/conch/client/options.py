# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

from __future__ import annotations

import sys

#
from twisted.conch.ssh.transport import SSHCiphers, SSHClientTransport
from twisted.python import usage


class ConchOptions(usage.Options):
    """
    Common command-line options for conch clients.
    """

    optParameters: list[list[str | int | None]] = [
        ["user", "l", None, "Log in using this user name."],
        ["identity", "i", None],
        ["ciphers", "c", None],
        ["macs", "m", None, "Specify MAC algorithms for protocol version 2."],
        ["port", "p", None, "Connect to this port.  Server must be on the same port."],
        ["option", "o", None, "Ignored OpenSSH options"],
        ["host-key-algorithms", "", None],
        ["known-hosts", "", None, "File to check for host keys"],
        ["user-authentications", "", None, "Types of user authentications to use."],
        ["logfile", "", None, "File to log to, or - for stdout"],
    ]

    optFlags = [
        ["version", "V", "Display version number only."],
        ["compress", "C", "Enable compression."],
        ["log", "v", "Enable logging (defaults to stderr)"],
        ["nox11", "x", "Disable X11 connection forwarding (default)"],
        ["agent", "A", "Enable authentication agent forwarding"],
        ["noagent", "a", "Disable authentication agent forwarding (default)"],
        ["reconnect", "r", "Reconnect to the server if the connection is lost."],
    ]

    compData = usage.Completions(
        mutuallyExclusive=[("agent", "noagent")],
        optActions={
            "user": usage.CompleteUsernames(),
            "ciphers": usage.CompleteMultiList(
                [v.decode() for v in SSHCiphers.cipherMap.keys()],
                descr="ciphers to choose from",
            ),
            "macs": usage.CompleteMultiList(
                [v.decode() for v in SSHCiphers.macMap.keys()],
                descr="macs to choose from",
            ),
            "host-key-algorithms": usage.CompleteMultiList(
                [v.decode() for v in SSHClientTransport.supportedPublicKeys],
                descr="host key algorithms to choose from",
            ),
            # "user-authentications": usage.CompleteMultiList(?
            # descr='user authentication types' ),
        },
        extraActions=[
            usage.CompleteUserAtHost(),
            usage.Completer(descr="command"),
            usage.Completer(descr="argument", repeat=True),
        ],
    )

    def __init__(self, *args: object, **kw: object) -> None:
        super().__init__()
        self.identitys: list[str] = []
        self.conns = None

    def opt_identity(self, i: str) -> None:
        """Identity for public-key authentication"""
        self.identitys.append(i)

    def opt_ciphers(self, ciphers: str) -> None:
        "Select encryption algorithms"
        cipherList = ciphers.split(",")
        for cipher in cipherList:
            if cipher not in SSHCiphers.cipherMap:
                sys.exit("Unknown cipher type '%s'" % cipher)
        self["ciphers"] = cipherList

    def opt_macs(self, macs: str | bytes) -> None:
        "Specify MAC algorithms"
        macsBytes = macs.encode("utf-8") if isinstance(macs, str) else macs
        macsList = macsBytes.split(b",")
        for mac in macsList:
            if mac not in SSHCiphers.macMap:
                sys.exit("Unknown mac type '%r'" % mac)
        self["macs"] = macsList

    def opt_host_key_algorithms(self, hkas):
        "Select host key algorithms"
        if isinstance(hkas, str):
            hkas = hkas.encode("utf-8")
        hkas = hkas.split(b",")
        for hka in hkas:
            if hka not in SSHClientTransport.supportedPublicKeys:
                sys.exit("Unknown host key type '%r'" % hka)
        self["host-key-algorithms"] = hkas

    def opt_user_authentications(self, uas):
        "Choose how to authenticate to the remote server"
        if isinstance(uas, str):
            uas = uas.encode("utf-8")
        self["user-authentications"] = uas.split(b",")


#    def opt_compress(self):
#        "Enable compression"
#        self.enableCompression = 1
#        SSHClientTransport.supportedCompressions[0:1] = ['zlib']


def _parseForwardSpec(f: str) -> tuple[tuple[str, int], tuple[str, int]] | None:
    """
    Parse a forward spec string like C{([lhost:]lport:host:port)} and return
    C{((lhost, lport), (host, port))}.  Returns None if spec string is invalid.
    Defaults lhost to 127.0.0.1 if not provided.
    """
    *maybeLhost, lport, host, port = f.split(":")
    if len(maybeLhost) not in (0, 1):
        return None
    [lhost, *_] = [*maybeLhost, "127.0.0.1"]
    if not (lport.isdigit() and port.isdigit()):
        return None
    return ((lhost, int(lport)), (host, int(port)))


class CommonOptions(ConchOptions):
    synopsis = """
    Usage: {cli} [options] host [command]
    """
    optParameters = [
        ["escape", "e", "~", "Set escape character; ``none'' = disable"],
        [
            "localforward",
            "L",
            None,
            "[listen-addr:]listen-port:host:port   Forward local port to remote address",
        ],
        [
            "remoteforward",
            "R",
            None,
            "[listen-addr:]listen-port:host:port   Forward remote port to local address",
        ],
    ]

    optFlags = [
        ["tty", "t", "TTY; allocate a TTY even if command is given."],
        ["notty", "T", "Do not allocate a TTY."],
        ["noshell", "N", "Do not execute a shell or command."],
        ["subsystem", "s", "Invoke command (mandatory) as SSH2 subsystem."],
    ]

    compData = usage.Completions(
        mutuallyExclusive=[("tty", "notty")],
        optActions={
            "localforward": usage.Completer(
                descr="[listen-addr:]listen-port:host:port"
            ),
            "remoteforward": usage.Completer(
                descr="[listen-addr:]listen-port:host:port"
            ),
        },
        extraActions=[
            usage.CompleteUserAtHost(),
            usage.Completer(descr="command"),
            usage.Completer(descr="argument", repeat=True),
        ],
    )

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.localForwards: list[tuple[tuple[str, int], tuple[str, int]]] = []
        self.remoteForwards: list[tuple[tuple[str, int], tuple[str, int]]] = []

    def opt_escape(self, esc: str) -> None:
        """
        Set escape character; ``none'' = disable
        """
        if esc == "none":
            self["escape"] = None
        elif esc[0] == "^" and len(esc) == 2:
            self["escape"] = chr(ord(esc[1]) - 64)
        elif len(esc) == 1:
            self["escape"] = esc
        else:
            sys.exit(f"Bad escape character '{esc}'.")

    def opt_localforward(self, f: str) -> None:
        """
        Forward local port to remote address ([lhost:]lport:host:port)
        """
        forwardSpec = _parseForwardSpec(f)
        if forwardSpec is None:
            sys.exit(
                f"Invalid local forward '{f}' (expected [listen-addr:]listen-port:host:port; IPv6 addresses not supported)."
            )
        self.localForwards.append(forwardSpec)

    def opt_remoteforward(self, f: str) -> None:
        """
        Forward remote port to local address ([rhost:]rport:host:port)
        """
        forwardSpec = _parseForwardSpec(f)
        if forwardSpec is None:
            sys.exit(
                f"Invalid remote forward '{f}' (expected [listen-addr:]listen-port:host:port; IPv6 addresses not supported)."
            )
        self.remoteForwards.append(forwardSpec)

    def parseArgs(self, host: str = "", *command: str) -> None:
        self["host"] = host
        self["command"] = " ".join(command)
