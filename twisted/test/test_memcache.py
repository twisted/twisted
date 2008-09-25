# Copyright (c) 2007 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Test the memcache client protocol.
"""

from zope.interface import verify

from twisted.trial.unittest import TestCase
from twisted.test.proto_helpers import StringTransportWithDisconnection
from twisted.internet.task import Clock
from twisted.internet.defer import Deferred, gatherResults, TimeoutError
from twisted.internet.defer import succeed, fail
from twisted.protocols.loopback import loopbackAsync

from twisted.protocols.memcache import MemCacheProtocol, NoSuchCommand
from twisted.protocols.memcache import ClientError, ServerError, CasError
from twisted.protocols.memcache import StandardBackend, MemCacheServerProtocol
from twisted.protocols.memcache import KeyFoundError, KeyNotFoundError
from twisted.protocols.memcache import ICacheBackend



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


    def test_incrementNotFound(self):
        """
        L{MemCacheProtocol.increment} should return C{False} when trying to
        increment a non-existing key.
        """
        return self._test(self.proto.increment("foo", 3), "incr foo 3\r\n",
            "NOT FOUND\r\n", False)


    def test_decrementNotFound(self):
        """
        L{MemCacheProtocol.decrement} should return C{False} when trying to
        decrement a non-existing key.
        """
        return self._test(self.proto.decrement("foo", 3), "decr foo 3\r\n",
            "NOT FOUND\r\n", False)


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
        d4 = self.assertFailure(
            self.proto.append("a" * 500, "bar"), ClientError)
        d5 = self.assertFailure(
            self.proto.prepend("a" * 500, "bar"), ClientError)
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



class StandardBackendTestCase(TestCase):
    """
    Tests for L{StandardBackend}.
    """

    def setUp(self):
        """
        Create a backend to be used in tests, and add a dumb key named
        B{testkey} with value B{testvalue}.
        """
        self.backend = StandardBackend()
        return self.backend.set("testkey", "testvalue", 0, 0)


    def test_interface(self):
        """
        Check that L{StandardBackend} implements L{ICacheBackend} and that
        its method signatures are correct.
        """
        self.assertTrue(verify.verifyObject(ICacheBackend, self.backend))
        self.assertTrue(verify.verifyClass(ICacheBackend, StandardBackend))


    def test_set(self):
        """
        L{StandardBackend.set} should add the key/value pair to the cache, so
        that a successive L{StandardBackend.get} call returns it.
        """
        def cb(result):
            self.assertTrue(result)
            return self.backend.get("foo").addCallback(
                self.assertEquals, (0, "bar"))
        return self.backend.set("foo", "bar", 0, 0).addCallback(cb)


    def test_get(self):
        """
        L{StandardBackend.get} should return a L{Deferred} which is called back
        with a tuple (flags, value).
        """
        return self.backend.get("testkey"
            ).addCallback(self.assertEquals, (0, "testvalue"))


    def test_gets(self):
        """
        L{StandardBackend.gets} should return a L{Deferred} which is called
        back with a tuple (flags, cas identifier, value).
        """
        def cb(result):
            self.assertEquals(result[0], 0)
            self.assertEquals(result[2], "testvalue")
            self.assertTrue(int(result[1]))
        return self.backend.gets("testkey").addCallback(cb)


    def test_getError(self):
        """
        L{StandardBackend.get} should return a failure with value
        L{KeyNotFoundError} if the given key is not in the cache.
        """
        d = self.backend.get("foo")
        return self.assertFailure(d, KeyNotFoundError)


    def test_getsError(self):
        """
        L{StandardBackend.gets} should return a failure with value
        L{KeyNotFoundError} if the given key is not in the cache.
        """
        d = self.backend.gets("foo")
        return self.assertFailure(d, KeyNotFoundError)


    def test_add(self):
        """
        L{StandardBackend.add} should behave the same way as
        L{StandardBackend.set} if the key is not in the cache.
        """
        def cb(result):
            self.assertTrue(result)
            return self.backend.get("foo").addCallback(
                self.assertEquals, (0, "bar"))
        return self.backend.add("foo", "bar", 0, 0).addCallback(cb)


    def test_addError(self):
        """
        L{StandardBackend.add} should return a failure with value
        L{KeyFoundError} if the given key is already in the cache.
        """
        d = self.backend.add("testkey", "bar", 0, 0)
        return self.assertFailure(d, KeyFoundError)


    def test_replace(self):
        """
        L{StandardBackend.replace} should behave the same way as
        L{StandardBackend.set} if the key is in the cache.
        """
        def cb(result):
            self.assertTrue(result)
            return self.backend.get("testkey").addCallback(
                self.assertEquals, (0, "bar"))
        return self.backend.replace("testkey", "bar", 0, 0).addCallback(cb)


    def test_replaceError(self):
        """
        L{StandardBackend.replace} should return a failure with value
        L{KeyNotFoundError} if the given key is not in the cache.
        """
        d = self.backend.replace("foo", "bar", 0, 0)
        return self.assertFailure(d, KeyNotFoundError)


    def test_append(self):
        """
        L{StandardBackend.append} should append the given value to the existing
        value of the key in the cache.
        """
        def cb(result):
            self.assertTrue(result)
            return self.backend.get("testkey").addCallback(
                self.assertEquals, (0, "testvaluebar"))
        return self.backend.append("testkey", "bar", 0, 0).addCallback(cb)


    def test_appendError(self):
        """
        L{StandardBackend.append} should return a failure with value
        L{KeyNotFoundError} if the given key is not in the cache.
        """
        d = self.backend.append("foo", "bar", 0, 0)
        return self.assertFailure(d, KeyNotFoundError)


    def test_prepend(self):
        """
        L{StandardBackend.prepend} should prepend the given value to the
        existing value of the key in the cache.
        """
        def cb(result):
            self.assertTrue(result)
            return self.backend.get("testkey").addCallback(
                self.assertEquals, (0, "bartestvalue"))
        return self.backend.prepend("testkey", "bar", 123, 0).addCallback(cb)


    def test_prependError(self):
        """
        L{StandardBackend.append} should return a failure with value
        L{KeyNotFoundError} if the given key is not in the cache.
        """
        d = self.backend.prepend("foo", "bar", 0, 0)
        return self.assertFailure(d, KeyNotFoundError)


    def test_delete(self):
        """
        L{StandardBackend.delete} should return a L{Deferred} which fires with
        C{True} if the given key has successfully been remove from the cache.
        """
        def cb(result):
            self.assertTrue(result)
            d = self.backend.get("testkey")
            return self.assertFailure(d, KeyNotFoundError)
        return self.backend.delete("testkey").addCallback(cb)


    def test_deleteError(self):
        """
        L{StandardBackend.delete} should return a failure with value
        L{KeyNotFoundError} if the given key is not in the cache.
        """
        d = self.backend.delete("foo")
        return self.assertFailure(d, KeyNotFoundError)


    def test_increment(self):
        """
        L{StandardBackend.increment} should return a L{Deferred} which fires
        with the new value of the key, incremented by the given value.
        """
        def cb(result):
            return self.backend.increment("foo", "3").addCallback(check)
        def check(result):
            self.assertEquals(result, "13")
            return self.backend.get("foo").addCallback(
                self.assertEquals, (0, "13"))
        return self.backend.set("foo", "10", 0, 0).addCallback(cb)


    def test_incrementNotFound(self):
        """
        L{StandardBackend.increment} should return a failure with value
        L{KeyNotFoundError} if the given key is not in the cache.
        """
        d = self.backend.increment("foo", "3")
        return self.assertFailure(d, KeyNotFoundError)


    def test_incrementExistingWrongType(self):
        """
        L{StandardBackend.increment} should return a failure with value
        L{ValueError} if the current type of the key can't be coerced to
        an integer.
        """
        d = self.backend.increment("testkey", "")
        return self.assertFailure(d, ValueError)


    def test_incrementGivenValueWrongType(self):
        """
        L{StandardBackend.increment} should return a failure with value
        L{ValueError} if the type of the increment can't be coerced to an
        integer.
        """
        def cb(result):
            d = self.backend.increment("foo", "bar")
            return self.assertFailure(d, ValueError)
        return self.backend.set("foo", "10", 0, 0).addCallback(cb)


    def test_decrement(self):
        """
        L{StandardBackend.decrement} should return a L{Deferred} which fires
        with the new value of the key, decremented by the given value.
        """
        def cb(result):
            return self.backend.decrement("foo", "3").addCallback(check)
        def check(result):
            self.assertEquals(result, "7")
            return self.backend.get("foo").addCallback(
                self.assertEquals, (0, "7"))
        return self.backend.set("foo", "10", 0, 0).addCallback(cb)


    def test_decrementNotFound(self):
        """
        L{StandardBackend.decrement} should return a failure with value
        L{KeyNotFoundError} if the given key is not in the cache.
        """
        d = self.backend.decrement("foo", "3")
        return self.assertFailure(d, KeyNotFoundError)


    def test_decrementExistingWrongType(self):
        """
        L{StandardBackend.decrement} should return a failure with value
        L{ValueError} if the current type of the key can't be coerced to
        an integer.
        """
        d = self.backend.decrement("testkey", "")
        return self.assertFailure(d, ValueError)


    def test_decrementGivenValueWrongType(self):
        """
        L{StandardBackend.decrement} should return a failure with value
        L{ValueError} if the type of the decrement can't be coerced to an
        integer.
        """
        def cb(result):
            d = self.backend.decrement("foo", "bar")
            return self.assertFailure(d, ValueError)
        return self.backend.set("foo", "10", 0, 0).addCallback(cb)


    def test_checkAndSet(self):
        """
        L{StandardBackend.checkAndSet} should allow a set if the identifier
        value is the one provided by a previous call to
        L{L{StandardBackend.gets}.
        """
        def cb(result):
            flags, cas, value = result
            return self.backend.checkAndSet(
                "testkey", "anothervalue", 0, 0, cas).addCallback(check)
        def check(result):
            self.assertEquals(result, True)
            return self.backend.get(
                "testkey").addCallback(self.assertEquals, (0, "anothervalue"))
        return self.backend.gets("testkey").addCallback(cb)


    def test_checkAndSetIdentifierChange(self):
        """
        If a call to a set method happens between the L{StandardBackend.gets}
        call and the L{StandardBackend.checkAndSet} call, the identifier
        should change so that the call to L{StandardBackend.checkAndSet} fails.
        """
        def cb1(result):
            flags, cas, value = result
            d = self.backend.set("testkey", "changeid", 0, 0)
            d.addCallback(cb2, cas)
            return d
        def cb2(result, cas):
            return self.assertFailure(
                self.backend.checkAndSet("testkey", "anothervalue", 0, 0, cas),
            CasError)
        return self.backend.gets("testkey").addCallback(cb1)


    def test_checkAndSetNotFound(self):
        """
        L{StandardBackend.checkAndSet} should fail with L{KeyNotFoundError} if
        the given key is not present in the cache.
        """
        return self.assertFailure(
            self.backend.checkAndSet("foo", "anothervalue", 0, 0, 0),
            KeyNotFoundError)


    def test_checkAndSetWrongIdentifier(self):
        """
        L{StandardBackend.checkAndSet} should fail with L{CasError} if the
        given cas identifier doesn't match the current identifier in the cache.
        """
        return self.assertFailure(
            self.backend.checkAndSet("testkey", "anothervalue", 0, 0, 0),
            CasError)

    def test_maxSize(self):
        """
        """



class MemCacheServerProtocolTestCase(TestCase):
    """
    Tests for L{MemCacheServerProtocol}.
    """

    def setUp(self):
        """
        Create a L{MemCacheServerProtocol} for tests, connect it to a string
        transport, and make it use a fake clock.
        """
        self.proto = MemCacheServerProtocol()
        self.clock = Clock()
        self.proto.callLater = self.clock.callLater
        self.transport = StringTransportWithDisconnection()
        self.transport.protocol = self.proto
        self.proto.makeConnection(self.transport)


    def test_get(self):
        """
        The protocol should reply to a B{get} command by calling the C{get}
        method on the backend, and sending the formatted content.
        """
        def get(*args):
            return succeed(("0", "bar"))
        self.proto.backend.get = get
        self.proto.dataReceived("get foo\r\n")
        self.assertEquals(
            self.transport.value(), "VALUE foo 0 3\r\nbar\r\nEND\r\n")


    def test_getNotFound(self):
        """
        When the backend reply to a C{get} with a L{KeyNotFoundError}, the
        protocol should send an empty response.
        """
        def get(*args):
            return fail(KeyNotFoundError("foo"))
        self.proto.backend.get = get
        self.proto.dataReceived("get foo\r\n")
        self.assertEquals(self.transport.value(), "END\r\n")


    def test_gets(self):
        """
        The protocol should reply to a B{gets} command by calling the C{gets}
        method on the backend, and sending the formatted content.
        """
        def gets(*args):
            return succeed(("0", "1234", "bar"))
        self.proto.backend.gets = gets
        self.proto.dataReceived("gets foo\r\n")
        self.assertEquals(
            self.transport.value(), "VALUE foo 0 3 1234\r\nbar\r\nEND\r\n")


    def test_getsNotFound(self):
        """
        When the backend reply to a C{gets} with a L{KeyNotFoundError}, the
        protocol should send an empty response.
        """
        def gets(*args):
            return fail(KeyNotFoundError("foo"))
        self.proto.backend.gets = gets
        self.proto.dataReceived("gets foo\r\n")
        self.assertEquals(self.transport.value(), "END\r\n")


    def test_set(self):
        """
        The protocol should reply to a C{set} command by calling the C{set}
        method on the backend, and sending the C{STORED} token.
        """
        def set(*args):
            return succeed(True)
        self.proto.backend.set = set
        self.proto.dataReceived("set foo 0 0 3\r\nbar\r\n")
        self.assertEquals(self.transport.value(), "STORED\r\n")


    def test_increment(self):
        """
        The protocol should reply to a C{incr} command by calling the C{incr}
        method on the backend, and sending the new value returned.
        """
        def increment(*args):
            return succeed("7")
        self.proto.backend.increment = increment
        self.proto.dataReceived("incr foo 4\r\n")
        self.assertEquals(self.transport.value(), "7\r\n")


    def test_decrement(self):
        """
        The protocol should reply to a C{decr} command by calling the C{decr}
        methof on the backend, and sending the new value returned.
        """
        def decrement(*args):
            return succeed("2")
        self.proto.backend.decrement = decrement
        self.proto.dataReceived("decr foo 4\r\n")
        self.assertEquals(self.transport.value(), "2\r\n")


    def test_incrementNotFound(self):
        """
        When the C{increment} command on the backend raise a
        L{KeyNotFoundError} exception, the server should respond with a
        C{NOT FOUND} token.
        """
        def increment(*args):
            return fail(KeyNotFoundError("foo"))
        self.proto.backend.increment = increment
        self.proto.dataReceived("incr foo 4\r\n")
        self.assertEquals(self.transport.value(), "NOT FOUND\r\n")


    def test_decrementNotFound(self):
        """
        When the C{decrement} command on the backend raise a L{KeyNotFoundError}
        exception, the server should respond with a C{NOT FOUND} token.
        """
        def decrement(*args):
            return fail(KeyNotFoundError("foo"))
        self.proto.backend.decrement = decrement
        self.proto.dataReceived("decr foo 4\r\n")
        self.assertEquals(self.transport.value(), "NOT FOUND\r\n")


    def test_incrementError(self):
        """
        When trying to increment with a non-integer value, the protocol should
        respond with a client error with the error message.
        """
        def increment(*args):
            try:
                int("bar")
            except:
                return fail()
        self.proto.backend.increment = increment
        self.proto.dataReceived("incr foo bar\r\n")
        self.assertIn(
            "CLIENT_ERROR invalid literal for int()", self.transport.value())


    def test_decrementError(self):
        """
        When trying to decrement with a non-integer value, the protocol should
        respond with a client error with the error message.
        """
        def decrement(*args):
            try:
                int("bar")
            except:
                return fail()
        self.proto.backend.decrement = decrement
        self.proto.dataReceived("decr foo bar\r\n")
        self.assertIn(
            "CLIENT_ERROR invalid literal for int()", self.transport.value())


    def test_stats(self):
        """
        When getting a C{stats} command, the protocol should call the
        corresponding method on the backed, and forward the key/value pairs
        returned.
        """
        def stats(*args):
            return succeed({"foo": "bar"})
        self.proto.backend.stats = stats
        self.proto.dataReceived("stats\r\n")
        self.assertEquals(self.transport.value(), "STAT foo bar\r\nEND\r\n")


    def test_flushAll(self):
        """
        The Cl{flush_all} command should forward a corresponding call on the
        backend and get the C{OK} token if everything went fine.
        """
        def flush_all(*args):
            return succeed(True)
        self.proto.backend.flush_all = flush_all
        self.proto.dataReceived("flush_all\r\n")
        self.assertEquals(self.transport.value(), "OK\r\n")


    def test_unknownCommand(self):
        """
        The reception of an unknown command should raise a C{RuntimeError} in
        the dataReceived method of the protocol.
        """
        self.assertRaises(RuntimeError, self.proto.dataReceived, "foo\r\n")


    def test_version(self):
        """
        The C{version} command should make the protocol call the corresponding
        method on the backend, and get the serialized result.
        """
        def version(*args):
            return succeed("1.1")
        self.proto.backend.version = version
        self.proto.dataReceived("version\r\n")
        self.assertEquals(self.transport.value(), "VERSION 1.1\r\n")



class IntegrationTestCase(TestCase):
    """
    Integration of L{MemcacheProtocol} and L{MemcacheServerProtocol}.
    """

    def setUp(self):
        """
        Create a client and a server, and set 2 keys in the backend.
        """
        self.server = MemCacheServerProtocol()
        self.serverClock = Clock()
        self.server.callLater = self.serverClock.callLater

        self.client = MemCacheProtocol()
        self.clientClock = Clock()
        self.client.callLater = self.clientClock.callLater

        d1 = self.server.backend.set("bar", "foo", 0, 0)
        d2 = self.server.backend.set("barint", "4", 0, 0)
        return gatherResults([d1, d2])


    def test_set(self):
        """
        Calling a set on the client should change the value in the backend.
        """
        def check(result):
            self.assertEquals(result, True)
            return self.server.backend.get("foo").addCallback(close)
        def close(result):
            self.assertEquals(result, (0, "bar"))
            self.client.transport.loseConnection()

        d1 = loopbackAsync(self.client, self.server)
        d2 = self.client.set("foo", "bar").addCallback(check)
        return gatherResults([d1, d2])


    def test_get(self):
        """
        Calling a get on the client should return the value from the cache.
        """
        def check(result):
            self.assertEquals(result, (0, "foo"))
            self.client.transport.loseConnection()
        d1 = loopbackAsync(self.client, self.server)
        d2 = self.client.get("bar").addCallback(check)
        return gatherResults([d1, d2])


    def test_getNotFound(self):
        """
        Calling a get on the client when the key doesn't exist should return
        (0, None).
        """
        def check(result):
            self.assertEquals(result, (0, None))
            self.client.transport.loseConnection()
        d1 = loopbackAsync(self.client, self.server)
        d2 = self.client.get("notexists").addCallback(check)
        return gatherResults([d1, d2])


    def test_increment(self):
        """
        Calling an increment on the client should return the new value
        associated with the key.
        """
        def check(result):
            self.assertEquals(result, 5)
            self.client.transport.loseConnection()
        d1 = loopbackAsync(self.client, self.server)
        d2 = self.client.increment("barint").addCallback(check)
        return gatherResults([d1, d2])
