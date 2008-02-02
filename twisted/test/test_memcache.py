# Copyright (c) 2007 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Test the memcache client protocol.
"""

from twisted.protocols.memcache import MemCacheProtocol, NoSuchCommand
from twisted.protocols.memcache import ClientError, ServerError

from twisted.trial.unittest import TestCase
from twisted.test.proto_helpers import StringTransportWithDisconnection
from twisted.internet.task import Clock
from twisted.internet.defer import Deferred, gatherResults, TimeoutError



class MemCacheTestCase(TestCase):
    """
    Test client protocol class L{MemCacheProtocol}.
    """

    def setUp(self):
        """
        Create a memcache client, connect it to a string protocol, and make it
        use a deterministic clock.
        """
        self.proto = MemCacheProtocol()
        self.clock = Clock()
        self.proto.callLater = self.clock.callLater
        self.transport = StringTransportWithDisconnection()
        self.transport.protocol = self.proto
        self.proto.makeConnection(self.transport)


    def _test(self, d, send, recv, result):
        """
        Shortcut method for classic tests.

        @param d: the resulting deferred from the memcache command.
        @type d: C{Deferred}

        @param send: the expected data to be sent.
        @type send: C{str}

        @param recv: the data to simulate as reception.
        @type recv: C{str}

        @param result: the expected result.
        @type result: C{any}
        """
        def cb(res):
            self.assertEquals(res, result)
        self.assertEquals(self.transport.value(), send)
        d.addCallback(cb)
        self.proto.dataReceived(recv)
        return d


    def test_get(self):
        """
        L{MemCacheProtocol.get} should return a L{Deferred} which is
        called back with the value and the flag associated with the given key
        if the server returns a successful result.
        """
        return self._test(self.proto.get("foo"), "get foo\r\n",
            "VALUE foo 0 3\r\nbar\r\nEND\r\n", (0, "bar"))


    def test_emptyGet(self):
        """
        Test getting a non-available key: it should succeed but return C{None}
        as value and C{0} as flag.
        """
        return self._test(self.proto.get("foo"), "get foo\r\n",
            "END\r\n", (0, None))


    def test_set(self):
        """
        L{MemCacheProtocol.set} should return a L{Deferred} which is
        called back with C{True} when the operation succeeds.
        """
        return self._test(self.proto.set("foo", "bar"),
            "set foo 0 0 3\r\nbar\r\n", "STORED\r\n", True)


    def test_add(self):
        """
        L{MemCacheProtocol.add} should return a L{Deferred} which is
        called back with C{True} when the operation succeeds.
        """
        return self._test(self.proto.add("foo", "bar"),
            "add foo 0 0 3\r\nbar\r\n", "STORED\r\n", True)


    def test_replace(self):
        """
        L{MemCacheProtocol.replace} should return a L{Deferred} which
        is called back with C{True} when the operation succeeds.
        """
        return self._test(self.proto.replace("foo", "bar"),
            "replace foo 0 0 3\r\nbar\r\n", "STORED\r\n", True)


    def test_errorAdd(self):
        """
        Test an erroneous add: if a L{MemCacheProtocol.add} is called but the
        key already exists on the server, it returns a B{NOT STORED} answer,
        which should callback the resulting L{Deferred} with C{False}.
        """
        return self._test(self.proto.add("foo", "bar"),
            "add foo 0 0 3\r\nbar\r\n", "NOT STORED\r\n", False)


    def test_errorReplace(self):
        """
        Test an erroneous replace: if a L{MemCacheProtocol.replace} is called
        but the key doesn't exist on the server, it returns a B{NOT STORED}
        answer, which should callback the resulting L{Deferred} with C{False}.
        """
        return self._test(self.proto.replace("foo", "bar"),
            "replace foo 0 0 3\r\nbar\r\n", "NOT STORED\r\n", False)


    def test_delete(self):
        """
        L{MemCacheProtocol.delete} should return a L{Deferred} which is
        called back with C{True} when the server notifies a success.
        """
        return self._test(self.proto.delete("bar"), "delete bar\r\n",
            "DELETED\r\n", True)


    def test_errorDelete(self):
        """
        Test a error during a delete: if key doesn't exist on the server, it
        returns a B{NOT FOUND} answer which should callback the resulting
        L{Deferred} with C{False}.
        """
        return self._test(self.proto.delete("bar"), "delete bar\r\n",
            "NOT FOUND\r\n", False)


    def test_increment(self):
        """
        Test incrementing a variable: L{MemCacheProtocol.increment} should
        return a L{Deferred} which is called back with the incremented value of
        the given key.
        """
        return self._test(self.proto.increment("foo"), "incr foo 1\r\n",
            "4\r\n", 4)


    def test_decrement(self):
        """
        Test decrementing a variable: L{MemCacheProtocol.decrement} should
        return a L{Deferred} which is called back with the decremented value of
        the given key.
        """
        return self._test(
            self.proto.decrement("foo"), "decr foo 1\r\n", "5\r\n", 5)


    def test_incrementVal(self):
        """
        L{MemCacheProtocol.increment} takes an optional argument C{value} which
        should replace the default value of 1 when specified.
        """
        return self._test(self.proto.increment("foo", 8), "incr foo 8\r\n",
            "4\r\n", 4)


    def test_decrementVal(self):
        """
        L{MemCacheProtocol.decrement} takes an optional argument C{value} which
        should replace the default value of 1 when specified.
        """
        return self._test(self.proto.decrement("foo", 3), "decr foo 3\r\n",
            "5\r\n", 5)


    def test_stats(self):
        """
        Test retrieving server statistics via the L{MemCacheProtocol.stats}
        command: it should parse the data sent by the server and call back the
        resulting L{Deferred} with a dictionary of the received statistics.
        """
        return self._test(self.proto.stats(), "stats\r\n",
            "STAT foo bar\r\nSTAT egg spam\r\nEND\r\n",
            {"foo": "bar", "egg": "spam"})


    def test_version(self):
        """
        Test version retrieval via the L{MemCacheProtocol.version} command: it
        should return a L{Deferred} which is called back with the version sent
        by the server.
        """
        return self._test(self.proto.version(), "version\r\n",
            "VERSION 1.1\r\n", "1.1")


    def test_flushAll(self):
        """
        L{MemCacheProtocol.flushAll} should return a L{Deferred} which is
        called back with C{True} if the server acknowledges success.
        """
        return self._test(self.proto.flushAll(), "flush_all\r\n",
            "OK\r\n", True)


    def test_invalidGetResponse(self):
        """
        If the value returned doesn't match the expected key of the current, we
        should get an error in L{MemCacheProtocol.dataReceived}.
        """
        self.proto.get("foo")
        s = "spamegg"
        self.assertRaises(RuntimeError,
            self.proto.dataReceived,
            "VALUE bar 0 %s\r\n%s\r\nEND\r\n" % (len(s), s))


    def test_timeOut(self):
        """
        Test the timeout on outgoing requests: when timeout is detected, all
        current commands should fail with a L{TimeoutError}, and the
        connection should be closed.
        """
        d1 = self.proto.get("foo")
        d2 = self.proto.get("bar")
        d3 = Deferred()
        self.proto.connectionLost = d3.callback

        self.clock.advance(self.proto.persistentTimeOut)
        self.assertFailure(d1, TimeoutError)
        self.assertFailure(d2, TimeoutError)
        def checkMessage(error):
            self.assertEquals(str(error), "Connection timeout")
        d1.addCallback(checkMessage)
        return gatherResults([d1, d2, d3])


    def test_timeoutRemoved(self):
        """
        When a request gets a response, no pending timeout call should remain
        around.
        """
        d = self.proto.get("foo")

        self.clock.advance(self.proto.persistentTimeOut - 1)
        self.proto.dataReceived("VALUE foo 0 3\r\nbar\r\nEND\r\n")

        def check(result):
            self.assertEquals(result, (0, "bar"))
            self.assertEquals(len(self.clock.calls), 0)
        d.addCallback(check)
        return d


    def test_timeOutRaw(self):
        """
        Test the timeout when raw mode was started: the timeout should not be
        reset until all the data has been received, so we can have a
        L{TimeoutError} when waiting for raw data.
        """
        d1 = self.proto.get("foo")
        d2 = Deferred()
        self.proto.connectionLost = d2.callback

        self.proto.dataReceived("VALUE foo 0 10\r\n12345")
        self.clock.advance(self.proto.persistentTimeOut)
        self.assertFailure(d1, TimeoutError)
        return gatherResults([d1, d2])


    def test_timeOutStat(self):
        """
        Test the timeout when stat command has started: the timeout should not
        be reset until the final B{END} is received.
        """
        d1 = self.proto.stats()
        d2 = Deferred()
        self.proto.connectionLost = d2.callback

        self.proto.dataReceived("STAT foo bar\r\n")
        self.clock.advance(self.proto.persistentTimeOut)
        self.assertFailure(d1, TimeoutError)
        return gatherResults([d1, d2])


    def test_timeoutPipelining(self):
        """
        When two requests are sent, a timeout call should remain around for the
        second request, and its timeout time should be correct.
        """
        d1 = self.proto.get("foo")
        d2 = self.proto.get("bar")
        d3 = Deferred()
        self.proto.connectionLost = d3.callback

        self.clock.advance(self.proto.persistentTimeOut - 1)
        self.proto.dataReceived("VALUE foo 0 3\r\nbar\r\nEND\r\n")

        def check(result):
            self.assertEquals(result, (0, "bar"))
            self.assertEquals(len(self.clock.calls), 1)
            for i in range(self.proto.persistentTimeOut):
                self.clock.advance(1)
            return self.assertFailure(d2, TimeoutError).addCallback(checkTime)
        def checkTime(ignored):
            # Check that the timeout happened C{self.proto.persistentTimeOut}
            # after the last response
            self.assertEquals(self.clock.seconds(),
                    2 * self.proto.persistentTimeOut - 1)
        d1.addCallback(check)
        return d1


    def test_timeoutNotReset(self):
        """
        Check that timeout is not resetted for every command, but keep the
        timeout from the first command without response.
        """
        d1 = self.proto.get("foo")
        d3 = Deferred()
        self.proto.connectionLost = d3.callback

        self.clock.advance(self.proto.persistentTimeOut - 1)
        d2 = self.proto.get("bar")
        self.clock.advance(1)
        self.assertFailure(d1, TimeoutError)
        self.assertFailure(d2, TimeoutError)
        return gatherResults([d1, d2, d3])


    def test_tooLongKey(self):
        """
        Test that an error is raised when trying to use a too long key: the
        called command should return a L{Deferred} which fail with a
        L{ClientError}.
        """
        d1 = self.assertFailure(self.proto.set("a" * 500, "bar"), ClientError)
        d2 = self.assertFailure(self.proto.increment("a" * 500), ClientError)
        d3 = self.assertFailure(self.proto.get("a" * 500), ClientError)
        d4 = self.assertFailure(self.proto.append("a" * 500, "bar"), ClientError)
        d5 = self.assertFailure(self.proto.prepend("a" * 500, "bar"), ClientError)
        return gatherResults([d1, d2, d3, d4, d5])


    def test_invalidCommand(self):
        """
        When an unknown command is sent directly (not through public API), the
        server answers with an B{ERROR} token, and the command should fail with
        L{NoSuchCommand}.
        """
        d = self.proto._set("egg", "foo", "bar", 0, 0, "")
        self.assertEquals(self.transport.value(), "egg foo 0 0 3\r\nbar\r\n")
        self.assertFailure(d, NoSuchCommand)
        self.proto.dataReceived("ERROR\r\n")
        return d


    def test_clientError(self):
        """
        Test the L{ClientError} error: when the server send a B{CLIENT_ERROR}
        token, the originating command should fail with L{ClientError}, and the
        error should contain the text sent by the server.
        """
        a = "eggspamm"
        d = self.proto.set("foo", a)
        self.assertEquals(self.transport.value(),
                          "set foo 0 0 8\r\neggspamm\r\n")
        self.assertFailure(d, ClientError)
        def check(err):
            self.assertEquals(str(err), "We don't like egg and spam")
        d.addCallback(check)
        self.proto.dataReceived("CLIENT_ERROR We don't like egg and spam\r\n")
        return d


    def test_serverError(self):
        """
        Test the L{ServerError} error: when the server send a B{SERVER_ERROR}
        token, the originating command should fail with L{ServerError}, and the
        error should contain the text sent by the server.
        """
        a = "eggspamm"
        d = self.proto.set("foo", a)
        self.assertEquals(self.transport.value(),
                          "set foo 0 0 8\r\neggspamm\r\n")
        self.assertFailure(d, ServerError)
        def check(err):
            self.assertEquals(str(err), "zomg")
        d.addCallback(check)
        self.proto.dataReceived("SERVER_ERROR zomg\r\n")
        return d


    def test_unicodeKey(self):
        """
        Using a non-string key as argument to commands should raise an error.
        """
        d1 = self.assertFailure(self.proto.set(u"foo", "bar"), ClientError)
        d2 = self.assertFailure(self.proto.increment(u"egg"), ClientError)
        d3 = self.assertFailure(self.proto.get(1), ClientError)
        d4 = self.assertFailure(self.proto.delete(u"bar"), ClientError)
        d5 = self.assertFailure(self.proto.append(u"foo", "bar"), ClientError)
        d6 = self.assertFailure(self.proto.prepend(u"foo", "bar"), ClientError)
        return gatherResults([d1, d2, d3, d4, d5, d6])


    def test_unicodeValue(self):
        """
        Using a non-string value should raise an error.
        """
        return self.assertFailure(self.proto.set("foo", u"bar"), ClientError)


    def test_pipelining(self):
        """
        Test that multiple requests can be sent subsequently to the server, and
        that the protocol order the responses correctly and dispatch to the
        corresponding client command.
        """
        d1 = self.proto.get("foo")
        d1.addCallback(self.assertEquals, (0, "bar"))
        d2 = self.proto.set("bar", "spamspamspam")
        d2.addCallback(self.assertEquals, True)
        d3 = self.proto.get("egg")
        d3.addCallback(self.assertEquals, (0, "spam"))
        self.assertEquals(self.transport.value(),
            "get foo\r\nset bar 0 0 12\r\nspamspamspam\r\nget egg\r\n")
        self.proto.dataReceived("VALUE foo 0 3\r\nbar\r\nEND\r\n"
                                "STORED\r\n"
                                "VALUE egg 0 4\r\nspam\r\nEND\r\n")
        return gatherResults([d1, d2, d3])


    def test_getInChunks(self):
        """
        If the value retrieved by a C{get} arrive in chunks, the protocol
        should be able to reconstruct it and to produce the good value.
        """
        d = self.proto.get("foo")
        d.addCallback(self.assertEquals, (0, "0123456789"))
        self.assertEquals(self.transport.value(), "get foo\r\n")
        self.proto.dataReceived("VALUE foo 0 10\r\n0123456")
        self.proto.dataReceived("789")
        self.proto.dataReceived("\r\nEND")
        self.proto.dataReceived("\r\n")
        return d


    def test_append(self):
        """
        L{MemCacheProtocol.append} behaves like a L{MemCacheProtocol.set}
        method: it should return a L{Deferred} which is called back with
        C{True} when the operation succeeds.
        """
        return self._test(self.proto.append("foo", "bar"),
            "append foo 0 0 3\r\nbar\r\n", "STORED\r\n", True)


    def test_prepend(self):
        """
        L{MemCacheProtocol.prepend} behaves like a L{MemCacheProtocol.set}
        method: it should return a L{Deferred} which is called back with
        C{True} when the operation succeeds.
        """
        return self._test(self.proto.prepend("foo", "bar"),
            "prepend foo 0 0 3\r\nbar\r\n", "STORED\r\n", True)


    def test_gets(self):
        """
        L{MemCacheProtocol.get} should handle an additional cas result when
        C{withIdentifier} is C{True} and forward it in the resulting
        L{Deferred}.
        """
        return self._test(self.proto.get("foo", True), "gets foo\r\n",
            "VALUE foo 0 3 1234\r\nbar\r\nEND\r\n", (0, "1234", "bar"))


    def test_emptyGets(self):
        """
        Test getting a non-available key with gets: it should succeed but
        return C{None} as value, C{0} as flag and an empty cas value.
        """
        return self._test(self.proto.get("foo", True), "gets foo\r\n",
            "END\r\n", (0, "", None))


    def test_checkAndSet(self):
        """
        L{MemCacheProtocol.checkAndSet} passes an additional cas identifier that the
        server should handle to check if the data has to be updated.
        """
        return self._test(self.proto.checkAndSet("foo", "bar", cas="1234"),
            "cas foo 0 0 3 1234\r\nbar\r\n", "STORED\r\n", True)


    def test_casUnknowKey(self):
        """
        When L{MemCacheProtocol.checkAndSet} response is C{EXISTS}, the resulting
        L{Deferred} should fire with C{False}.
        """
        return self._test(self.proto.checkAndSet("foo", "bar", cas="1234"),
            "cas foo 0 0 3 1234\r\nbar\r\n", "EXISTS\r\n", False)
