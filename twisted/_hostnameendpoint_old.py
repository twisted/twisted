@implementer(interfaces.IStreamClientEndpoint)
class HostnameEndpoint(object):
    """
    A name-based endpoint that connects to the fastest amongst the
    resolved host addresses.

    @ivar _getaddrinfo: A hook used for testing name resolution.

    @ivar _deferToThread: A hook used for testing deferToThread.
    """
    _getaddrinfo = socket.getaddrinfo
    _deferToThread = staticmethod(threads.deferToThread)

    def __init__(self, reactor, host, port, timeout=30, bindAddress=None):
        """
        @param host: A hostname to connect to.
        @type host: L{bytes}

        @param timeout: For each individual connection attempt, the number of
            seconds to wait before assuming the connection has failed.
        @type timeout: L{int}

        @see: L{twisted.internet.interfaces.IReactorTCP.connectTCP}
        """
        self._reactor = reactor
        self._host = host
        self._port = port
        self._timeout = timeout
        self._bindAddress = bindAddress


    def connect(self, protocolFactory):
        """
        Attempts a connection to each address returned by gai, and returns a
        connection which is established first.
        """
        wf = protocolFactory
        pending = []

        def _canceller(d):
            """
            The outgoing connection attempt was cancelled.  Fail that L{Deferred}
            with an L{error.ConnectingCancelledError}.

            @param d: The L{Deferred <defer.Deferred>} that was cancelled
            @type d: L{Deferred <defer.Deferred>}

            @return: C{None}
            """
            d.errback(error.ConnectingCancelledError(
                HostnameAddress(self._host, self._port)))
            for p in pending[:]:
                p.cancel()

        def errbackForGai(failure):
            """
            Errback for when L{_nameResolution} returns a Deferred that fires
            with failure.
            """
            return defer.fail(error.DNSLookupError(
                "Couldn't find the hostname '%s'" % (self._host,)))

        def _endpoints(gaiResult):
            """
            This method matches the host address family with an endpoint for
            every address returned by GAI.

            @param gaiResult: A list of 5-tuples as returned by GAI.
            @type gaiResult: list
            """
            for family, socktype, proto, canonname, sockaddr in gaiResult:
                if family in [AF_INET6]:
                    yield TCP6ClientEndpoint(self._reactor, sockaddr[0],
                            sockaddr[1], self._timeout, self._bindAddress)
                elif family in [AF_INET]:
                    yield TCP4ClientEndpoint(self._reactor, sockaddr[0],
                            sockaddr[1], self._timeout, self._bindAddress)
                        # Yields an endpoint for every address returned by GAI

        def attemptConnection(endpoints):
            """
            When L{endpoints} yields an endpoint, this method attempts to connect it.
            """
            # The trial attempts for each endpoints, the recording of
            # successful and failed attempts, and the algorithm to pick the
            # winner endpoint goes here.
            # Return a Deferred that fires with the endpoint that wins,
            # or `failures` if none succeed.

            endpointsListExhausted = []
            successful = []
            failures = []
            winner = defer.Deferred(canceller=_canceller)

            def usedEndpointRemoval(connResult, connAttempt):
                pending.remove(connAttempt)
                return connResult

            def afterConnectionAttempt(connResult):
                if lc.running:
                    lc.stop()

                successful.append(True)
                for p in pending[:]:
                    p.cancel()
                winner.callback(connResult)
                return None

            def checkDone():
                if endpointsListExhausted and not pending and not successful:
                    winner.errback(failures.pop())

            def connectFailed(reason):
                failures.append(reason)
                checkDone()
                return None

            def iterateEndpoint():
                try:
                    endpoint = next(endpoints)
                except StopIteration:
                    # The list of endpoints ends.
                    endpointsListExhausted.append(True)
                    lc.stop()
                    checkDone()
                else:
                    dconn = endpoint.connect(wf)
                    pending.append(dconn)
                    dconn.addBoth(usedEndpointRemoval, dconn)
                    dconn.addCallback(afterConnectionAttempt)
                    dconn.addErrback(connectFailed)

            lc = LoopingCall(iterateEndpoint)
            lc.clock = self._reactor
            lc.start(0.3)
            return winner

        d = self._nameResolution(self._host, self._port)
        d.addErrback(errbackForGai)
        d.addCallback(_endpoints)
        d.addCallback(attemptConnection)
        return d

    def _nameResolution(self, host, port):
        """
        Resolve the hostname string into a tuple containig the host
        address.
        """
        return self._deferToThread(self._getaddrinfo, host, port, 0,
                socket.SOCK_STREAM)

