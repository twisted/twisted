# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twext.enterprise.adbapi2}.
"""

import gc

from zope.interface.verify import verifyObject

from twisted.python.failure import Failure

from twisted.trial.unittest import TestCase

from twisted.internet.defer import Deferred, fail, succeed, inlineCallbacks

from twisted.test.proto_helpers import StringTransport

from twext.enterprise.ienterprise import ConnectionError
from twext.enterprise.ienterprise import AlreadyFinishedError
from twext.enterprise.adbapi2 import ConnectionPoolClient
from twext.enterprise.adbapi2 import ConnectionPoolConnection
from twext.enterprise.ienterprise import IAsyncTransaction
from twext.enterprise.ienterprise import ICommandBlock
from twext.enterprise.adbapi2 import FailsafeException
from twext.enterprise.adbapi2 import ConnectionPool
from twext.enterprise.fixtures import ConnectionPoolHelper
from twext.enterprise.fixtures import resultOf
from twext.enterprise.fixtures import ClockWithThreads
from twext.enterprise.fixtures import FakeConnectionError
from twext.enterprise.fixtures import RollbackFail
from twext.enterprise.fixtures import CommitFail
from twext.enterprise.adbapi2 import Commit
from twext.enterprise.adbapi2 import _HookableOperation



class TrashCollector(object):
    """
    Test helper for monitoring gc.garbage.
    """
    def __init__(self, testCase):
        self.testCase = testCase
        testCase.addCleanup(self.checkTrash)
        self.start()


    def start(self):
        gc.collect()
        self.garbageStart = len(gc.garbage)


    def checkTrash(self):
        """
        Ensure that the test has added no additional garbage.
        """
        gc.collect()
        newGarbage = gc.garbage[self.garbageStart:]
        if newGarbage:
            # Don't clean up twice.
            self.start()
            self.testCase.fail("New garbage: " + repr(newGarbage))



class AssertResultHelper(object):
    """
    Mixin for asserting about synchronous Deferred results.
    """

    def assertResultList(self, resultList, expected):
        """
        Assert that a list created with L{resultOf} contais the expected
        result.

        @param resultList: The return value of L{resultOf}.
        @type resultList: L{list}

        @param expected: The expected value that should be present in the list;
            a L{Failure} if an exception is expected to be raised.
        """
        if not resultList:
            self.fail("No result; Deferred didn't fire yet.")
        else:
            if isinstance(resultList[0], Failure):
                if isinstance(expected, Failure):
                    resultList[0].trap(expected.type)
                else:
                    resultList[0].raiseException()
            else:
                self.assertEqual(resultList, [expected])



class ConnectionPoolBootTests(TestCase):
    """
    Tests for the start-up phase of L{ConnectionPool}.
    """

    def test_threadCount(self):
        """
        The reactor associated with a L{ConnectionPool} will have its maximum
        thread count adjusted when L{ConnectionPool.startService} is called, to
        accomodate for L{ConnectionPool.maxConnections} additional threads.

        Stopping the service should restore it to its original value, so that a
        repeatedly re-started L{ConnectionPool} will not cause the thread
        ceiling to grow without bound.
        """
        defaultMax = 27
        connsMax = 45
        combinedMax = defaultMax + connsMax
        pool = ConnectionPool(None, maxConnections=connsMax)
        pool.reactor = ClockWithThreads()
        threadpool = pool.reactor.getThreadPool()
        pool.reactor.suggestThreadPoolSize(defaultMax)
        self.assertEquals(threadpool.max, defaultMax)
        pool.startService()
        self.assertEquals(threadpool.max, combinedMax)
        justChecking = []
        pool.stopService().addCallback(justChecking.append)
        # No SQL run, so no threads started, so this deferred should fire
        # immediately.  If not, we're in big trouble, so sanity check.
        self.assertEquals(justChecking, [None])
        self.assertEquals(threadpool.max, defaultMax)


    def test_isRunning(self):
        """
        L{ConnectionPool.startService} should set its C{running} attribute to
        true.
        """
        pool = ConnectionPool(None)
        pool.reactor = ClockWithThreads()
        self.assertEquals(pool.running, False)
        pool.startService()
        self.assertEquals(pool.running, True)



class ConnectionPoolNameTests(TestCase):
    """
    Tests for L{ConnectionPool}'s C{name} attribute.
    """
    def test_default(self):
        """
        If no value is given for the C{name} parameter to L{ConnectionPool}'s
        initializer then L{ConnectionPool.name} is C{None}.
        """
        pool = ConnectionPool(None)
        self.assertIs(None, pool.name)


    def test_specified(self):
        """
        If a value is given for the C{name} parameter to L{ConnectionPool}'s
        initializer then it is used as the value for L{ConnectionPool.name}.
        """
        name = "some test pool"
        pool = ConnectionPool(None, name=name)
        self.assertEqual(name, pool.name)



class ConnectionPoolTests(ConnectionPoolHelper, TestCase, AssertResultHelper):
    """
    Tests for L{ConnectionPool}.
    """

    def test_tooManyConnections(self):
        """
        When the number of outstanding busy transactions exceeds the number of
        slots specified by L{ConnectionPool.maxConnections},
        L{ConnectionPool.connection} will return a pooled transaction that is
        not backed by any real database connection; this object will queue its
        SQL statements until an existing connection becomes available.
        """
        a = self.createTransaction()

        alphaResult = self.resultOf(a.execSQL("alpha"))
        [[_ignore_counter, _ignore_echo]] = alphaResult[0]

        b = self.createTransaction()
        # "b" should have opened a connection.
        self.assertEquals(len(self.factory.connections), 2)
        betaResult = self.resultOf(b.execSQL("beta"))
        [[bcounter, _ignore_becho]] = betaResult[0]

        # both "a" and "b" are holding open a connection now; let's try to open
        # a third one.  (The ordering will be deterministic even if this fails,
        # because those threads are already busy.)
        c = self.createTransaction()
        gammaResult = self.resultOf(c.execSQL("gamma"))

        # Did "c" open a connection?  Let's hope not...
        self.assertEquals(len(self.factory.connections), 2)
        # SQL shouldn't be executed too soon...
        self.assertEquals(gammaResult, [])

        commitResult = self.resultOf(b.commit())

        # Now that "b" has committed, "c" should be able to complete.
        [[ccounter, _ignore_cecho]] = gammaResult[0]

        # The connection for "a" ought to still be busy, so let's make sure
        # we're using the one for "c".
        self.assertEquals(ccounter, bcounter)

        # Sanity check: the commit should have succeeded!
        self.assertEquals(commitResult, [None])


    def test_stopService(self):
        """
        L{ConnectionPool.stopService} stops all the associated L{ThreadHolder}s
        and thereby frees up the resources it is holding.
        """
        a = self.createTransaction()
        alphaResult = self.resultOf(a.execSQL("alpha"))
        [[[_ignore_counter, _ignore_echo]]] = alphaResult
        self.assertEquals(len(self.factory.connections), 1)
        self.assertEquals(len(self.holders), 1)
        [holder] = self.holders
        self.assertEquals(holder.started, True)
        self.assertEquals(holder.stopped, False)
        self.pool.stopService()
        self.assertEquals(self.pool.running, False)
        self.assertEquals(len(self.holders), 1)
        self.assertEquals(holder.started, True)
        self.assertEquals(holder.stopped, True)
        # Closing fake connections removes them from the list.
        self.assertEquals(len(self.factory.connections), 1)
        self.assertEquals(self.factory.connections[0].closed, True)


    def test_retryAfterConnectError(self):
        """
        When the C{connectionFactory} passed to L{ConnectionPool} raises an
        exception, the L{ConnectionPool} will log the exception and delay
        execution of a new connection's SQL methods until an attempt succeeds.
        """
        self.factory.willFail()
        self.factory.willFail()
        self.factory.willConnect()
        c = self.createTransaction()

        def checkOneFailure():
            errors = self.flushLoggedErrors(FakeConnectionError)
            self.assertEquals(len(errors), 1)

        checkOneFailure()
        d = c.execSQL("alpha")
        happened = []
        d.addBoth(happened.append)
        self.assertEquals(happened, [])
        self.clock.advance(self.pool.RETRY_TIMEOUT + 0.01)
        checkOneFailure()
        self.assertEquals(happened, [])
        self.clock.advance(self.pool.RETRY_TIMEOUT + 0.01)
        self.flushHolders()
        self.assertEquals(happened, [[[1, "alpha"]]])


    def test_shutdownDuringRetry(self):
        """
        If a L{ConnectionPool} is attempting to shut down while it's in the
        process of re-trying a connection attempt that received an error, the
        connection attempt should be cancelled and the shutdown should complete
        as normal.
        """
        self.factory.defaultFail()
        self.createTransaction()
        errors = self.flushLoggedErrors(FakeConnectionError)
        self.assertEquals(len(errors), 1)
        stopd = []
        self.pool.stopService().addBoth(stopd.append)
        self.assertResultList(stopd, None)
        self.assertEquals(self.clock.calls, [])
        [holder] = self.holders
        self.assertEquals(holder.started, True)
        self.assertEquals(holder.stopped, True)


    def test_shutdownDuringAttemptSuccess(self):
        """
        If L{ConnectionPool.stopService} is called while a connection attempt
        is outstanding, the resulting L{Deferred} won't be fired until the
        connection attempt has finished; in this case, succeeded.
        """
        self.pauseHolders()
        self.createTransaction()
        stopd = []
        self.pool.stopService().addBoth(stopd.append)
        self.assertEquals(stopd, [])
        self.flushHolders()
        self.assertResultList(stopd, None)
        [holder] = self.holders
        self.assertEquals(holder.started, True)
        self.assertEquals(holder.stopped, True)


    def test_shutdownDuringAttemptFailed(self):
        """
        If L{ConnectionPool.stopService} is called while a connection attempt
        is outstanding, the resulting L{Deferred} won't be fired until the
        connection attempt has finished; in this case, failed.
        """
        self.factory.defaultFail()
        self.pauseHolders()
        self.createTransaction()
        stopd = []
        self.pool.stopService().addBoth(stopd.append)
        self.assertEquals(stopd, [])
        self.flushHolders()
        errors = self.flushLoggedErrors(FakeConnectionError)
        self.assertEquals(len(errors), 1)
        self.assertResultList(stopd, None)
        [holder] = self.holders
        self.assertEquals(holder.started, True)
        self.assertEquals(holder.stopped, True)


    def test_stopServiceMidAbort(self):
        """
        When L{ConnectionPool.stopService} is called with deferreds from
        C{abort} still outstanding, it will wait for the currently-aborting
        transaction to fully abort before firing the L{Deferred} returned from
        C{stopService}.
        """
        # TODO: commit() too?
        self.pauseHolders()
        c = self.createTransaction()
        abortResult = self.resultOf(c.abort())
        # Should abort instantly, as it hasn't managed to unspool anything yet.
        # FIXME: kill all Deferreds associated with this thing, make sure that
        # any outstanding query callback chains get nuked.
        self.assertEquals(abortResult, [None])
        stopResult = self.resultOf(self.pool.stopService())
        self.assertEquals(stopResult, [])
        self.flushHolders()
        # self.assertEquals(abortResult, [None])
        self.assertResultList(stopResult, None)


    def test_stopServiceWithSpooled(self):
        """
        When L{ConnectionPool.stopService} is called when spooled transactions
        are outstanding, any pending L{Deferreds} returned by those
        transactions will be failed with L{ConnectionError}.
        """
        # Use up the free slots so we have to spool.
        hold = []
        hold.append(self.createTransaction())
        hold.append(self.createTransaction())

        c = self.createTransaction()
        se = self.resultOf(c.execSQL("alpha"))
        ce = self.resultOf(c.commit())
        self.assertEquals(se, [])
        self.assertEquals(ce, [])
        self.resultOf(self.pool.stopService())
        self.assertEquals(se[0].type, self.translateError(ConnectionError))
        self.assertEquals(ce[0].type, self.translateError(ConnectionError))


    def test_repoolSpooled(self):
        """
        Regression test for a somewhat tricky-to-explain bug: when a spooled
        transaction which has already had commit() called on it before it's
        received a real connection to start executing on, it will not leave
        behind any detritus that prevents stopService from working.
        """
        self.pauseHolders()
        c = self.createTransaction()
        c2 = self.createTransaction()
        c3 = self.createTransaction()
        c.commit()
        c2.commit()
        c3.commit()
        self.flushHolders()
        self.assertEquals(len(self.factory.connections), 2)
        stopResult = self.resultOf(self.pool.stopService())
        self.assertEquals(stopResult, [None])
        self.assertEquals(len(self.factory.connections), 2)
        self.assertEquals(self.factory.connections[0].closed, True)
        self.assertEquals(self.factory.connections[1].closed, True)


    def test_connectAfterStop(self):
        """
        Calls to connection() after stopService() result in transactions which
        immediately fail all operations.
        """
        stopResults = self.resultOf(self.pool.stopService())
        self.assertEquals(stopResults, [None])
        self.pauseHolders()
        postClose = self.createTransaction()
        queryResult = self.resultOf(postClose.execSQL("hello"))
        self.assertEquals(len(queryResult), 1)
        self.assertEquals(queryResult[0].type,
                          self.translateError(ConnectionError))


    def test_connectAfterStartedStopping(self):
        """
        Calls to connection() after stopService() has been called but before it
        has completed will result in transactions which immediately fail all
        operations.
        """
        self.pauseHolders()
        preClose = self.createTransaction()
        preCloseResult = self.resultOf(preClose.execSQL("statement"))
        stopResult = self.resultOf(self.pool.stopService())
        postClose = self.createTransaction()
        queryResult = self.resultOf(postClose.execSQL("hello"))
        self.assertEquals(stopResult, [])
        self.assertEquals(len(queryResult), 1)
        self.assertEquals(
            queryResult[0].type,
            self.translateError(ConnectionError)
        )
        self.assertEquals(len(preCloseResult), 1)
        self.assertEquals(
            preCloseResult[0].type,
            self.translateError(ConnectionError)
        )


    def test_abortFailsDuringStopService(self):
        """
        L{IAsyncTransaction.abort} might fail, most likely because the
        underlying database connection has already been disconnected.  If this
        happens, shutdown should continue.
        """
        txns = []
        txns.append(self.createTransaction())
        txns.append(self.createTransaction())
        for txn in txns:
            # Make sure rollback will actually be executed.
            results = self.resultOf(txn.execSQL("maybe change something!"))
            [[[_ignore_counter, echo]]] = results
            self.assertEquals("maybe change something!", echo)
        # Fail one (and only one) call to rollback().
        self.factory.rollbackFail = True
        stopResult = self.resultOf(self.pool.stopService())
        self.assertEquals(stopResult, [None])
        self.assertEquals(len(self.flushLoggedErrors(RollbackFail)), 1)
        self.assertEquals(self.factory.connections[0].closed, True)
        self.assertEquals(self.factory.connections[1].closed, True)


    def test_partialTxnFailsDuringStopService(self):
        """
        Using the logic in L{ConnectionPool.stopService}, make sure that an
        L{_ConnectedTxn} cannot continue to process SQL after L{_ConnectedTxn.abort}
        is called and before L{_ConnectedTxn.reset} is called.
        """
        txn = self.createTransaction()
        if hasattr(txn, "_baseTxn"):
            # Send initial statement
            txn.execSQL("maybe change something!")

            # Make it look like the service is stopping
            txn._baseTxn._connection.close()
            txn._baseTxn.terminate()

            # Try to send more SQL - must fail
            self.failUnlessRaises(RuntimeError, txn.execSQL, "maybe change something else!")


    def test_abortRecycledTransaction(self):
        """
        L{ConnectionPool.stopService} will shut down if a recycled transaction
        is still pending.
        """
        recycled = self.createTransaction()
        self.resultOf(recycled.commit())
        remember = []
        remember.append(self.createTransaction())
        self.assertEquals(self.resultOf(self.pool.stopService()), [None])


    def test_abortSpooled(self):
        """
        Aborting a still-spooled transaction (one which has no statements being
        executed) will result in all of its Deferreds immediately failing and
        none of the queued statements being executed.
        """
        active = []
        # Use up the available connections ...
        for _ignore in xrange(self.pool.maxConnections):
            active.append(self.createTransaction())

        # ... so that this one has to be spooled.
        spooled = self.createTransaction()
        result = self.resultOf(spooled.execSQL("alpha"))

        # sanity check, it would be bad if this actually executed.
        self.assertEqual(result, [])
        self.resultOf(spooled.abort())
        self.assertEqual(result[0].type, self.translateError(ConnectionError))


    def test_waitForAlreadyAbortedTransaction(self):
        """
        L{ConnectionPool.stopService} will wait for all transactions to shut
        down before exiting, including those which have already been stopped.
        """
        it = self.createTransaction()
        self.pauseHolders()
        abortResult = self.resultOf(it.abort())

        # steal it from the queue so we can do it out of order
        d, _ignore_work = self.holders[0]._q.get()

        # that should be the only work unit so don't continue if something else
        # got in there
        self.assertEquals(list(self.holders[0]._q.queue), [])
        self.assertEquals(len(self.holders), 1)
        self.flushHolders()
        stopResult = self.resultOf(self.pool.stopService())

        # Sanity check that we haven't actually stopped it yet
        self.assertEquals(abortResult, [])

        # We haven't fired it yet, so the service had better not have
        # stopped...
        self.assertEquals(stopResult, [])

        d.callback(None)
        self.flushHolders()
        self.assertEquals(abortResult, [None])
        self.assertEquals(stopResult, [None])


    def test_garbageCollectedTransactionAborts(self):
        """
        When an L{IAsyncTransaction} is garbage collected, it ought to abort
        itself.
        """
        t = self.createTransaction()
        self.resultOf(t.execSQL("echo", []))
        conns = self.factory.connections
        self.assertEquals(len(conns), 1)
        self.assertEquals(conns[0]._rollbackCount, 0)
        del t
        gc.collect()
        self.flushHolders()
        self.assertEquals(len(conns), 1)
        self.assertEquals(conns[0]._rollbackCount, 1)
        self.assertEquals(conns[0]._commitCount, 0)


    def circularReferenceTest(self, finish, hook):
        """
        Collecting a completed (committed or aborted) L{IAsyncTransaction}
        should not leak any circular references.
        """
        tc = TrashCollector(self)
        commitExecuted = []

        def carefullyManagedScope():
            t = self.createTransaction()

            def holdAReference():
                """
                This is a hook that holds a reference to "t".
                """
                commitExecuted.append(True)
                return t.execSQL("teardown", [])

            hook(t, holdAReference)
            finish(t)

        self.failIf(commitExecuted, "Commit hook executed.")
        carefullyManagedScope()
        tc.checkTrash()


    def test_noGarbageOnCommit(self):
        """
        Committing a transaction does not cause gc garbage.
        """
        self.circularReferenceTest(
            lambda txn: txn.commit(),
            lambda txn, hook: txn.preCommit(hook)
        )


    def test_noGarbageOnCommitWithAbortHook(self):
        """
        Committing a transaction does not cause gc garbage.
        """
        self.circularReferenceTest(
            lambda txn: txn.commit(),
            lambda txn, hook: txn.postAbort(hook)
        )


    def test_noGarbageOnAbort(self):
        """
        Aborting a transaction does not cause gc garbage.
        """
        self.circularReferenceTest(
            lambda txn: txn.abort(),
            lambda txn, hook: txn.preCommit(hook)
        )


    def test_noGarbageOnAbortWithPostCommitHook(self):
        """
        Aborting a transaction does not cause gc garbage.
        """
        self.circularReferenceTest(
            lambda txn: txn.abort(),
            lambda txn, hook: txn.postCommit(hook)
        )


    def test_tooManyConnectionsWhileOthersFinish(self):
        """
        L{ConnectionPool.connection} will not spawn more than the maximum
        connections if there are finishing transactions outstanding.
        """
        a = self.createTransaction()
        b = self.createTransaction()
        self.pauseHolders()
        a.abort()
        b.abort()

        # Remove the holders for the existing connections, so that the "extra"
        # connection() call wins the race and gets executed first.
        self.holders[:] = []
        self.createTransaction()
        self.flushHolders()
        self.assertEquals(len(self.factory.connections), 2)


    def setParamstyle(self, paramstyle):
        """
        Change the paramstyle of the transaction under test.
        """
        self.pool.paramstyle = paramstyle


    def test_propagateParamstyle(self):
        """
        Each different type of L{ISQLExecutor} relays the C{paramstyle}
        attribute from the L{ConnectionPool}.
        """
        TEST_PARAMSTYLE = "justtesting"
        self.setParamstyle(TEST_PARAMSTYLE)
        normaltxn = self.createTransaction()
        self.assertEquals(normaltxn.paramstyle, TEST_PARAMSTYLE)
        self.assertEquals(normaltxn.commandBlock().paramstyle, TEST_PARAMSTYLE)
        self.pauseHolders()
        extra = []
        extra.append(self.createTransaction())
        waitingtxn = self.createTransaction()
        self.assertEquals(waitingtxn.paramstyle, TEST_PARAMSTYLE)
        self.flushHolders()
        self.pool.stopService()
        notxn = self.createTransaction()
        self.assertEquals(notxn.paramstyle, TEST_PARAMSTYLE)


    def setDialect(self, dialect):
        """
        Change the dialect of the transaction under test.
        """
        self.pool.dialect = dialect


    def test_propagateDialect(self):
        """
        Each different type of L{ISQLExecutor} relays the C{dialect}
        attribute from the L{ConnectionPool}.
        """
        TEST_DIALECT = "otherdialect"
        self.setDialect(TEST_DIALECT)
        normaltxn = self.createTransaction()
        self.assertEquals(normaltxn.dialect, TEST_DIALECT)
        self.assertEquals(normaltxn.commandBlock().dialect, TEST_DIALECT)
        self.pauseHolders()
        extra = []
        extra.append(self.createTransaction())
        waitingtxn = self.createTransaction()
        self.assertEquals(waitingtxn.dialect, TEST_DIALECT)
        self.flushHolders()
        self.pool.stopService()
        notxn = self.createTransaction()
        self.assertEquals(notxn.dialect, TEST_DIALECT)


    def test_reConnectWhenFirstExecFails(self):
        """
        Generally speaking, DB-API 2.0 adapters do not provide information
        about the cause of a failed C{execute} method; they definitely don't
        provide it in a way which can be identified as related to the syntax of
        the query, the state of the database itself, the state of the
        connection, etc.

        Therefore the best general heuristic for whether the connection to the
        database has been lost and needs to be re-established is to catch
        exceptions which are raised by the I{first} statement executed in a
        transaction.
        """
        # Allow C{connect} to succeed.  This should behave basically the same
        # whether connect() happened to succeed in some previous transaction
        # and it's recycling the underlying transaction, or connect() just
        # succeeded.  Either way you just have a _SingleTxn wrapping a
        # _ConnectedTxn.
        txn = self.createTransaction()
        self.assertEquals(len(self.factory.connections), 1,
                          "Sanity check failed.")

        class CustomExecuteFailed(Exception):
            """
            Custom "execute-failed" exception.
            """

        self.factory.connections[0].executeWillFail(CustomExecuteFailed)
        results = self.resultOf(txn.execSQL("hello, world!"))
        [[[_ignore_counter, echo]]] = results
        self.assertEquals("hello, world!", echo)

        # Two execution attempts should have been made, one on each connection.
        # The first failed with a RuntimeError, but that is deliberately
        # obscured, because then we tried again and it succeeded.
        self.assertEquals(
            len(self.factory.connections), 2,
            "No new connection opened."
        )
        self.assertEquals(self.factory.connections[0].executions, 1)
        self.assertEquals(self.factory.connections[1].executions, 1)
        self.assertEquals(self.factory.connections[0].closed, True)
        self.assertEquals(self.factory.connections[1].closed, False)

        # Nevertheless, since there is currently no classification of "safe"
        # errors, we should probably log these messages when they occur.
        self.assertEquals(len(self.flushLoggedErrors(CustomExecuteFailed)), 1)


    def test_reConnectWhenFirstExecOnExistingConnectionFails(
        self, moreFailureSetup=lambda factory: None
    ):
        """
        Another situation that might arise is that a connection will be
        successfully connected, executed and recycled into the connection pool;
        then, the database server will shut down and the connections will die,
        but we will be none the wiser until we try to use them.
        """
        txn = self.createTransaction()
        moreFailureSetup(self.factory)
        self.assertEquals(
            len(self.factory.connections), 1, "Sanity check failed."
        )
        results = self.resultOf(txn.execSQL("hello, world!"))
        txn.commit()
        [[[_ignore_counter, echo]]] = results
        self.assertEquals("hello, world!", echo)
        txn2 = self.createTransaction()
        self.assertEquals(
            len(self.factory.connections), 1, "Sanity check failed."
        )

        class CustomExecFail(Exception):
            """
            Custom C{execute()} failure.
            """

        self.factory.connections[0].executeWillFail(CustomExecFail)
        results = self.resultOf(txn2.execSQL("second try!"))
        txn2.commit()
        [[[_ignore_counter, echo]]] = results
        self.assertEquals("second try!", echo)
        self.assertEquals(len(self.flushLoggedErrors(CustomExecFail)), 1)


    def test_closeExceptionDoesntHinderReconnection(self):
        """
        In some database bindings, if the server closes the connection,
        C{close()} will fail.  If C{close} fails, there's not much that could
        mean except that the connection is already closed, so similar to the
        condition described in
        L{test_reConnectWhenFirstExecOnExistingConnectionFails}, the
        failure should be logged, but transparent to application code.
        """

        class BindingSpecificException(Exception):
            """
            Exception that's a placeholder for something that a database
            binding might raise.
            """

        def alsoFailClose(factory):
            factory.childCloseWillFail(BindingSpecificException())

        t = self.test_reConnectWhenFirstExecOnExistingConnectionFails(
            alsoFailClose
        )
        errors = self.flushLoggedErrors(BindingSpecificException)
        self.assertEquals(len(errors), 1)
        return t


    def test_preCommitSuccess(self):
        """
        Callables passed to L{IAsyncTransaction.preCommit} will be invoked upon
        commit.
        """
        txn = self.createTransaction()

        def simple():
            simple.done = True

        simple.done = False
        txn.preCommit(simple)
        self.assertEquals(simple.done, False)
        result = self.resultOf(txn.commit())
        self.assertEquals(len(result), 1)
        self.assertEquals(simple.done, True)


    def test_deferPreCommit(self):
        """
        If callables passed to L{IAsyncTransaction.preCommit} return
        L{Deferred}s, they will defer the actual commit operation until it has
        fired.
        """
        txn = self.createTransaction()
        d = Deferred()

        def wait():
            wait.started = True

            def executed(it):
                wait.sqlResult = it

            # To make sure the _underlying_ commit operation was Deferred, we
            # have to execute some SQL to make sure it happens.
            d.addCallback(lambda ignored: txn.execSQL("some test sql"))
            d.addCallback(executed)
            return d

        wait.started = False
        wait.sqlResult = None
        txn.preCommit(wait)
        result = self.resultOf(txn.commit())
        self.flushHolders()
        self.assertEquals(wait.started, True)
        self.assertEquals(wait.sqlResult, None)
        self.assertEquals(result, [])
        d.callback(None)
        # allow network I/O for pooled / networked implementation; there should
        # be the commit message now.
        self.flushHolders()
        self.assertEquals(len(result), 1)
        self.assertEquals(wait.sqlResult, [[1, "some test sql"]])


    def test_failPreCommit(self):
        """
        If callables passed to L{IAsyncTransaction.preCommit} raise an
        exception or return a Failure, subsequent callables will not be run,
        and the transaction will be aborted.
        """
        def test(flawedCallable, exc):
            # Set up.
            test.committed = False
            test.aborted = False
            # Create transaction and add monitoring hooks.
            txn = self.createTransaction()

            def didCommit():
                test.committed = True

            def didAbort():
                test.aborted = True

            txn.postCommit(didCommit)
            txn.postAbort(didAbort)
            txn.preCommit(flawedCallable)
            result = self.resultOf(txn.commit())
            self.flushHolders()
            self.assertResultList(result, Failure(exc()))
            self.assertEquals(test.committed, False)
            self.assertEquals(test.aborted, True)

        def failer():
            return fail(ZeroDivisionError())

        def raiser():
            raise EOFError()

        test(failer, ZeroDivisionError)
        test(raiser, EOFError)


    def test_noOpCommitDoesntHinderReconnection(self):
        """
        Until you've executed a query or performed a statement on an ADBAPI
        connection, the connection is semantically idle (between transactions).
        A .commit() or .rollback() followed immediately by a .commit() is
        therefore pointless, and can be ignored.  Furthermore, actually
        executing the commit and propagating a possible connection-oriented
        error causes clients to see errors, when, if those clients had actually
        executed any statements, the connection would have been recycled and
        the statement transparently re-executed by the logic tested by
        L{test_reConnectWhenFirstExecFails}.
        """
        txn = self.createTransaction()
        self.factory.commitFail = True
        self.factory.rollbackFail = True
        [x] = self.resultOf(txn.commit())

        # No statements have been executed, so C{commit} will *not* be
        # executed.
        self.assertEquals(self.factory.commitFail, True)
        self.assertIdentical(x, None)
        self.assertEquals(len(self.pool._free), 1)
        self.assertEquals(self.pool._finishing, [])
        self.assertEquals(len(self.factory.connections), 1)
        self.assertEquals(self.factory.connections[0].closed, False)


    def test_reConnectWhenSecondExecFailsThenFirstExecFails(self):
        """
        Other connection-oriented errors might raise exceptions if they occur
        in the middle of a transaction, but that should cause the error to be
        caught, the transaction to be aborted, and the (closed) connection to
        be recycled, where the next transaction that attempts to do anything
        with it will encounter the error immediately and discover it needs to
        be recycled.

        It would be better if this behavior were invisible, but that could only
        be accomplished with more precise database exceptions.  We may come up
        with support in the future for more precisely identifying exceptions,
        but I{unknown} exceptions should continue to be treated in this manner,
        relaying the exception back to application code but attempting a
        re-connection on the next try.
        """
        txn = self.createTransaction()
        [[[_ignore_counter, _ignore_echo]]] = self.resultOf(txn.execSQL("hello, world!", []))
        self.factory.connections[0].executeWillFail(ZeroDivisionError)
        [f] = self.resultOf(txn.execSQL("divide by zero", []))
        f.trap(self.translateError(ZeroDivisionError))
        self.assertEquals(self.factory.connections[0].executions, 2)

        # Reconnection should work exactly as before.
        self.assertEquals(self.factory.connections[0].closed, False)

        # Application code has to roll back its transaction at this point,
        # since it failed (and we don't necessarily know why it failed: not
        # enough information).
        self.resultOf(txn.abort())
        self.factory.connections[0].executions = 0  # re-set for next test
        self.assertEquals(len(self.factory.connections), 1)
        self.test_reConnectWhenFirstExecFails()


    def test_disconnectOnFailedRollback(self):
        """
        When C{rollback} fails for any reason on a connection object, then we
        don't know what state it's in.  Most likely, it's already been
        disconnected, so the connection should be closed and the transaction
        de-pooled instead of recycled.

        Also, a new connection will immediately be established to keep the pool
        size the same.
        """
        txn = self.createTransaction()
        results = self.resultOf(txn.execSQL("maybe change something!"))
        [[[_ignore_counter, echo]]] = results
        self.assertEquals("maybe change something!", echo)
        self.factory.rollbackFail = True
        [x] = self.resultOf(txn.abort())

        # Abort does not propagate the error on, the transaction merely gets
        # disposed of.
        self.assertIdentical(x, None)
        self.assertEquals(len(self.pool._free), 1)
        self.assertEquals(self.pool._finishing, [])
        self.assertEquals(len(self.factory.connections), 2)
        self.assertEquals(self.factory.connections[0].closed, True)
        self.assertEquals(self.factory.connections[1].closed, False)
        self.assertEquals(len(self.flushLoggedErrors(RollbackFail)), 1)


    def test_exceptionPropagatesFailedCommit(self):
        """
        A failed C{rollback} is fine (the premature death of the connection
        without C{commit} means that the changes are surely gone), but a failed
        C{commit} has to be relayed to client code, since that actually means
        some changes didn't hit the database.
        """
        txn = self.createTransaction()
        self.factory.commitFail = True
        results = self.resultOf(txn.execSQL("maybe change something!"))
        [[[_ignore_counter, echo]]] = results
        self.assertEquals("maybe change something!", echo)
        [x] = self.resultOf(txn.commit())
        x.trap(self.translateError(CommitFail))

        self.assertEquals(len(self.pool._free), 1)
        self.assertEquals(self.pool._finishing, [])
        self.assertEquals(len(self.factory.connections), 2)
        self.assertEquals(self.factory.connections[0].closed, True)
        self.assertEquals(self.factory.connections[1].closed, False)


    def test_commandBlock(self):
        """
        L{IAsyncTransaction.commandBlock} returns an L{IAsyncTransaction}
        provider which ensures that a block of commands are executed together.
        """
        txn = self.createTransaction()
        a = self.resultOf(txn.execSQL("a"))
        cb = txn.commandBlock()
        verifyObject(ICommandBlock, cb)
        b = self.resultOf(cb.execSQL("b"))
        d = self.resultOf(txn.execSQL("d"))
        c = self.resultOf(cb.execSQL("c"))
        cb.end()
        e = self.resultOf(txn.execSQL("e"))

        self.assertEquals(
            self.factory.connections[0].cursors[0].allExecutions,
            [("a", []), ("b", []), ("c", []), ("d", []), ("e", [])]
        )
        self.assertEquals(len(a), 1)
        self.assertEquals(len(b), 1)
        self.assertEquals(len(c), 1)
        self.assertEquals(len(d), 1)
        self.assertEquals(len(e), 1)


    def test_commandBlockWithLatency(self):
        """
        A block returned by L{IAsyncTransaction.commandBlock} won't start
        executing until all SQL statements scheduled before it have completed.
        """
        self.pauseHolders()
        txn = self.createTransaction()
        a = self.resultOf(txn.execSQL("a"))
        b = self.resultOf(txn.execSQL("b"))
        cb = txn.commandBlock()
        c = self.resultOf(cb.execSQL("c"))
        d = self.resultOf(cb.execSQL("d"))
        e = self.resultOf(txn.execSQL("e"))
        cb.end()
        self.flushHolders()

        self.assertEquals(
            self.factory.connections[0].cursors[0].allExecutions,
            [("a", []), ("b", []), ("c", []), ("d", []), ("e", [])]
        )

        self.assertEquals(len(a), 1)
        self.assertEquals(len(b), 1)
        self.assertEquals(len(c), 1)
        self.assertEquals(len(d), 1)
        self.assertEquals(len(e), 1)


    def test_twoCommandBlocks(self, flush=lambda: None):
        """
        When execution of one command block is complete, it will proceed to the
        next queued block, then to regular SQL executed on the transaction.
        """
        txn = self.createTransaction()
        cb1 = txn.commandBlock()
        cb2 = txn.commandBlock()
        txn.execSQL("e")
        cb1.execSQL("a")
        cb2.execSQL("c")
        cb1.execSQL("b")
        cb2.execSQL("d")
        cb2.end()
        cb1.end()
        flush()
        self.flushHolders()
        self.assertEquals(
            self.factory.connections[0].cursors[0].allExecutions,
            [("a", []), ("b", []), ("c", []), ("d", []), ("e", [])]
        )


    def test_twoCommandBlocksLatently(self):
        """
        Same as L{test_twoCommandBlocks}, but with slower callbacks.
        """
        self.pauseHolders()
        self.test_twoCommandBlocks(self.flushHolders)


    def test_commandBlockEndTwice(self):
        """
        L{CommandBlock.end} will raise L{AlreadyFinishedError} when called more
        than once.
        """
        txn = self.createTransaction()
        block = txn.commandBlock()
        block.end()
        self.assertRaises(AlreadyFinishedError, block.end)


    def test_commandBlockDelaysCommit(self):
        """
        Some command blocks need to run asynchronously, without the overall
        transaction-managing code knowing how far they've progressed.
        Therefore when you call {IAsyncTransaction.commit}(), it should not
        actually take effect if there are any pending command blocks.
        """
        txn = self.createTransaction()
        block = txn.commandBlock()
        commitResult = self.resultOf(txn.commit())
        self.resultOf(block.execSQL("in block"))
        self.assertEquals(commitResult, [])
        self.assertEquals(
            self.factory.connections[0].cursors[0].allExecutions,
            [("in block", [])]
        )
        block.end()
        self.flushHolders()
        self.assertEquals(commitResult, [None])


    def test_commandBlockDoesntDelayAbort(self):
        """
        A L{CommandBlock} can't possibly have anything interesting to say about
        a transaction that gets rolled back, so C{abort} applies immediately;
        all outstanding C{execSQL}s will fail immediately, on both command
        blocks and on the transaction itself.
        """
        txn = self.createTransaction()
        block = txn.commandBlock()
        block2 = txn.commandBlock()
        abortResult = self.resultOf(txn.abort())
        self.assertEquals(abortResult, [None])
        self.assertRaises(AlreadyFinishedError, block2.execSQL, "bar")
        self.assertRaises(AlreadyFinishedError, block.execSQL, "foo")
        self.assertRaises(AlreadyFinishedError, txn.execSQL, "baz")
        self.assertEquals(
            self.factory.connections[0].cursors[0].allExecutions, []
        )
        # end() should _not_ raise an exception, because this is the sort of
        # thing that might be around a try/finally or try/except; it's just
        # putting the commandBlock itself into a state consistent with the
        # transaction.
        block.end()
        block2.end()


    def test_endedBlockDoesntExecuteMoreSQL(self):
        """
        Attempting to execute SQL on a L{CommandBlock} which has had C{end}
        called on it will result in an L{AlreadyFinishedError}.
        """
        txn = self.createTransaction()
        block = txn.commandBlock()
        block.end()
        self.assertRaises(AlreadyFinishedError, block.execSQL, "hello")
        self.assertEquals(
            self.factory.connections[0].cursors[0].allExecutions, []
        )


    def test_commandBlockAfterCommitRaises(self):
        """
        Once an L{IAsyncTransaction} has been committed, L{commandBlock} raises
        an exception.
        """
        txn = self.createTransaction()
        txn.commit()
        self.assertRaises(AlreadyFinishedError, txn.commandBlock)


    def test_commandBlockAfterAbortRaises(self):
        """
        Once an L{IAsyncTransaction} has been committed, L{commandBlock} raises
        an exception.
        """
        txn = self.createTransaction()
        self.resultOf(txn.abort())
        self.assertRaises(AlreadyFinishedError, txn.commandBlock)


    def test_raiseOnZeroRowCount(self):
        """
        L{IAsyncTransaction.execSQL} will return a L{Deferred} failing with the
        exception passed as its raiseOnZeroRowCount argument if the underlying
        query returns no rows.
        """
        self.factory.hasResults = False
        txn = self.createTransaction()
        f = self.resultOf(
            txn.execSQL("hello", raiseOnZeroRowCount=ZeroDivisionError)
        )[0]
        self.assertRaises(ZeroDivisionError, f.raiseException)
        txn.commit()


    def test_raiseOnZeroRowCountWithUnreliableRowCount(self):
        """
        As it turns out, some databases can't reliably tell you how many rows
        they're going to fetch via the C{rowcount} attribute before the rows
        have actually been fetched, so the C{raiseOnZeroRowCount} will I{not}
        raise an exception if C{rowcount} is zero but C{description} and
        C{fetchall} indicates the presence of some rows.
        """
        self.factory.hasResults = True
        self.factory.shouldUpdateRowcount = False
        txn = self.createTransaction()
        r = self.resultOf(
            txn.execSQL("some-rows", raiseOnZeroRowCount=RuntimeError)
        )
        [[[_ignore_counter, echo]]] = r
        self.assertEquals(echo, "some-rows")



class IOPump(object):
    """
    Connect a client and a server.

    @ivar client: a client protocol

    @ivar server: a server protocol
    """

    def __init__(self, client, server):
        self.client = client
        self.server = server
        self.clientTransport = StringTransport()
        self.serverTransport = StringTransport()
        self.client.makeConnection(self.clientTransport)
        self.server.makeConnection(self.serverTransport)
        self.c2s = [self.clientTransport, self.server]
        self.s2c = [self.serverTransport, self.client]


    def moveData(self, (outTransport, inProtocol)):
        """
        Move data from a L{StringTransport} to an L{IProtocol}.

        @return: C{True} if any data was moved, C{False} if no data was moved.
        """
        data = outTransport.io.getvalue()
        outTransport.io.seek(0)
        outTransport.io.truncate()
        if data:
            inProtocol.dataReceived(data)
            return True
        else:
            return False


    def pump(self):
        """
        Deliver all input from the client to the server, then from the server
        to the client.
        """
        a = self.moveData(self.c2s)
        b = self.moveData(self.s2c)
        return a or b


    def flush(self, maxTurns=100):
        """
        Continue pumping until no more data is flowing.
        """
        turns = 0
        while self.pump():
            turns += 1
            if turns > maxTurns:
                raise RuntimeError("Ran too long!")



class NetworkedPoolHelper(ConnectionPoolHelper):
    """
    An extension of L{ConnectionPoolHelper} that can set up a
    L{ConnectionPoolClient} and L{ConnectionPoolConnection} attached to each
    other.
    """

    def setUp(self):
        """
        Do the same setup from L{ConnectionPoolBase}, but also establish a
        loopback connection between a L{ConnectionPoolConnection} and a
        L{ConnectionPoolClient}.
        """
        super(NetworkedPoolHelper, self).setUp()
        self.pump = IOPump(
            ConnectionPoolClient(
                dialect=self.dialect,
                paramstyle=self.paramstyle
            ),
            ConnectionPoolConnection(self.pool)
        )


    def flushHolders(self):
        """
        In addition to flushing the L{ThreadHolder} stubs, also flush any
        pending network I/O.
        """
        self.pump.flush()
        super(NetworkedPoolHelper, self).flushHolders()
        self.pump.flush()


    def createTransaction(self):
        txn = self.pump.client.newTransaction()
        self.pump.flush()
        return txn


    def translateError(self, err):
        """
        All errors raised locally will unfortunately be translated into
        UnknownRemoteError, since AMP requires specific enumeration of all of
        them.  Flush the locally logged error of the given type and return
        L{UnknownRemoteError}.
        """
        if err in Commit.errors:
            return err
        self.flushLoggedErrors(err)
        return FailsafeException


    def resultOf(self, it):
        result = resultOf(it)
        self.pump.flush()
        return result



class NetworkedConnectionPoolTests(NetworkedPoolHelper, ConnectionPoolTests):
    """
    Tests for L{ConnectionPoolConnection} and L{ConnectionPoolClient}
    interacting with each other.
    """

    def setParamstyle(self, paramstyle):
        """
        Change the paramstyle on both the pool and the client.
        """
        super(NetworkedConnectionPoolTests, self).setParamstyle(paramstyle)
        self.pump.client.paramstyle = paramstyle


    def setDialect(self, dialect):
        """
        Change the dialect on both the pool and the client.
        """
        super(NetworkedConnectionPoolTests, self).setDialect(dialect)
        self.pump.client.dialect = dialect


    def test_newTransaction(self):
        """
        L{ConnectionPoolClient.newTransaction} returns a provider of
        L{IAsyncTransaction}, and creates a new transaction on the server side.
        """
        txn = self.pump.client.newTransaction()
        verifyObject(IAsyncTransaction, txn)
        self.pump.flush()
        self.assertEquals(len(self.factory.connections), 1)



class HookableOperationTests(TestCase):
    """
    Tests for L{_HookableOperation}.
    """

    @inlineCallbacks
    def test_clearPreventsSubsequentAddHook(self):
        """
        After clear() or runHooks() are called, subsequent calls to addHook()
        are NO-OPs.
        """
        def hook():
            return succeed(None)

        hookOp = _HookableOperation()
        hookOp.addHook(hook)
        self.assertEquals(len(hookOp._hooks), 1)
        hookOp.clear()
        self.assertEquals(hookOp._hooks, None)

        hookOp = _HookableOperation()
        hookOp.addHook(hook)
        yield hookOp.runHooks()
        self.assertEquals(hookOp._hooks, None)
        hookOp.addHook(hook)
        self.assertEquals(hookOp._hooks, None)
