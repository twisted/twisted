# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Benchmark for SSH connection setup between a Conch client and server using RSA
keys.
"""
from twisted.conch.ssh.factory import SSHFactory
from twisted.conch.ssh.keys import Key
from twisted.conch.ssh.transport import SSHClientTransport
from twisted.internet import reactor
from twisted.internet.defer import Deferred, inlineCallbacks, succeed
from twisted.internet.endpoints import (
    TCP4ClientEndpoint,
    connectProtocol,
    serverFromString,
)

PUBLIC_KEY = (
    b"ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAGEArzJx8OYOnJmzf4tfBEvLi8DVPrJ3/c9k2I/Az6"
    b"4fxjHf9imyRJbixtQhlH9lfNjUIx+4LmrJH5QNRsFporcHDKOTwTTYLh5KmRpslkYHRivcJSkb"
    b"h/C+BR3utDS555mV"
)

PRIVATE_KEY = b"""-----BEGIN RSA PRIVATE KEY-----
MIIByAIBAAJhAK8ycfDmDpyZs3+LXwRLy4vA1T6yd/3PZNiPwM+uH8Yx3/YpskSW
4sbUIZR/ZXzY1CMfuC5qyR+UDUbBaaK3Bwyjk8E02C4eSpkabJZGB0Yr3CUpG4fw
vgUd7rQ0ueeZlQIBIwJgbh+1VZfr7WftK5lu7MHtqE1S1vPWZQYE3+VUn8yJADyb
Z4fsZaCrzW9lkIqXkE3GIY+ojdhZhkO1gbG0118sIgphwSWKRxK0mvh6ERxKqIt1
xJEJO74EykXZV4oNJ8sjAjEA3J9r2ZghVhGN6V8DnQrTk24Td0E8hU8AcP0FVP+8
PQm/g/aXf2QQkQT+omdHVEJrAjEAy0pL0EBH6EVS98evDCBtQw22OZT52qXlAwZ2
gyTriKFVoqjeEjt3SZKKqXHSApP/AjBLpF99zcJJZRq2abgYlf9lv1chkrWqDHUu
DZttmYJeEfiFBBavVYIF1dOlZT0G8jMCMBc7sOSZodFnAiryP+Qg9otSBjJ3bQML
pSTqy7c3a2AScC/YyOwkDaICHnnD3XyjMwIxALRzl0tQEKMXs6hH8ToUdlLROCrP
EhQ0wahUTCk1gKA4uPD6TMTChavbh4K63OvbKg==
-----END RSA PRIVATE KEY-----"""


class BenchmarkSSHClientTransport(SSHClientTransport):
    """
    The client used in the tests.
    """

    def verifyHostKey(self, hostKey, fingerprint):
        """
        For this test, we don't validate the server identity.
        """
        return succeed(True)

    def connectionSecure(self):
        """
        As soon as the SSH handshake is done, we disconnect,
        without requesting for any SSH service.
        """
        self.transport.loseConnection()

    def connectionLost(self, reason):
        self.factory.clientDisconnected.callback(None)


class BenchmarkSSHServerFactory(SSHFactory):
    """
    A simple SSH server factory with static RSA keys.
    """

    publicKeys = {b"ssh-rsa": Key.fromString(data=PUBLIC_KEY)}
    privateKeys = {b"ssh-rsa": Key.fromString(data=PRIVATE_KEY)}

    def __init__(self):
        # Called by the client once disconnected.
        self.clientDisconnected = Deferred()


def _runReactor(callback):
    """
    (re)Start a reactor that might have been previously started.
    """
    deferred = callback()
    deferred.addBoth(lambda _: _stopReactor())
    reactor._startedBefore = False
    reactor._started = False
    reactor._justStopped = False
    reactor.run(installSignalHandlers=False)


def _stopReactor():
    """
    Stop the reactor and allow it to be re-started later.
    """
    reactor.stop()
    reactor.iterate()
    reactor._startedBefore = False
    reactor._started = False
    reactor._justStopped = False
    reactor.running = False
    # Start running has consumed the startup events, so we need
    # to restore them.
    reactor.addSystemEventTrigger("during", "startup", reactor._reallyStartRunning)


def benchmarkWithReactor(test_target):
    """
    Decorator for running the test with the benchmark.
    """

    def benchmark_test(benchmark):
        benchmark(_runReactor, test_target)

    return benchmark_test


@benchmarkWithReactor
@inlineCallbacks
def test_connect_and_disconnect():
    """
    This is the test for key exchange for both client and server.
    Once KEX is done the client disconnects.
    """
    serverFactory = BenchmarkSSHServerFactory()
    serverEndpoint = serverFromString(reactor, "tcp:0:interface=127.0.0.1")
    serverPort = yield serverEndpoint.listen(serverFactory)

    clientProtocol = BenchmarkSSHClientTransport()
    clientProtocol.factory = serverFactory

    clientEndpoint = TCP4ClientEndpoint(
        reactor,
        "127.0.0.1",
        serverPort.getHost().port,
        timeout=5,
    )
    yield connectProtocol(clientEndpoint, clientProtocol)
    yield serverFactory.clientDisconnected
    yield serverPort.stopListening()
