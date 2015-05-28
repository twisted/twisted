# -*- test-case-name: twext.enterprise.test.test_fixtures -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Fixtures for testing code that uses ADBAPI2.
"""

import sqlite3
from Queue import Empty
from itertools import count

from zope.interface import implementer
from zope.interface.verify import verifyClass

from twisted.internet.interfaces import IReactorThreads
from twisted.python.threadpool import ThreadPool

from twisted.internet.task import Clock

from twext.enterprise.adbapi2 import ConnectionPool
from twext.enterprise.ienterprise import SQLITE_DIALECT
from twext.enterprise.ienterprise import POSTGRES_DIALECT
from twext.enterprise.adbapi2 import DEFAULT_PARAM_STYLE
from twext.internet.threadutils import ThreadHolder



def buildConnectionPool(testCase, schemaText="", dialect=SQLITE_DIALECT):
    """
    Build a L{ConnectionPool} for testing purposes, with the given C{testCase}.

    @param testCase: the test case to attach the resulting L{ConnectionPool}
        to.
    @type testCase: L{twisted.trial.unittest.TestCase}

    @param schemaText: The text of the schema with which to initialize the
        database.
    @type schemaText: L{str}

    @return: a L{ConnectionPool} service whose C{startService} method has
        already been invoked.
    @rtype: L{ConnectionPool}
    """
    sqlitename = testCase.mktemp()
    seqs = {}

    def connectionFactory(label=testCase.id()):
        conn = sqlite3.connect(sqlitename, isolation_level=None)

        def nextval(seq):
            result = seqs[seq] = seqs.get(seq, 0) + 1
            return result

        conn.create_function("nextval", 1, nextval)
        return conn

    con = connectionFactory()
    con.executescript(schemaText)
    con.commit()
    pool = ConnectionPool(connectionFactory, paramstyle="numeric",
                          dialect=SQLITE_DIALECT)
    pool.startService()
    testCase.addCleanup(pool.stopService)
    return pool



def resultOf(deferred, propagate=False):
    """
    Add a callback and errback which will capture the result of a L{Deferred}
    in a list, and return that list.  If C{propagate} is True, pass through the
    results.
    """
    results = []

    if propagate:
        def cb(r):
            results.append(r)
            return r
    else:
        cb = results.append

    deferred.addBoth(cb)
    return results



class FakeThreadHolder(ThreadHolder):
    """
    Run things to submitted this ThreadHolder on the main thread, so that
    execution is easier to control.
    """

    def __init__(self, test):
        super(FakeThreadHolder, self).__init__(self)
        self.test = test
        self.started = False
        self.stopped = False
        self._workerIsRunning = False


    def start(self):
        self.started = True
        return super(FakeThreadHolder, self).start()


    def stop(self):
        result = super(FakeThreadHolder, self).stop()
        self.stopped = True
        return result


    @property
    def _get_q(self):
        return self._q_


    @_get_q.setter
    def _q(self, newq):
        if newq is not None:
            oget = newq.get
            newq.get = lambda: oget(timeout=0)
            oput = newq.put

            def putit(x):
                p = oput(x)
                if not self.test.paused:
                    self.flush()
                return p

            newq.put = putit

        self._q_ = newq


    def callFromThread(self, f, *a, **k):
        result = f(*a, **k)
        return result


    def callInThread(self, f, *a, **k):
        """
        This should be called only once, to start the worker function that
        dedicates a thread to this L{ThreadHolder}.
        """
        self._workerIsRunning = True


    def flush(self):
        """
        Fire all deferreds previously returned from submit.
        """
        try:
            while self._workerIsRunning and self._qpull():
                pass
            else:
                self._workerIsRunning = False
        except Empty:
            pass



@implementer(IReactorThreads)
class ClockWithThreads(Clock):
    """
    A testing reactor that supplies L{IReactorTime} and L{IReactorThreads}.
    """

    def __init__(self):
        super(ClockWithThreads, self).__init__()
        self._pool = ThreadPool()


    def getThreadPool(self):
        """
        Get the threadpool.
        """
        return self._pool


    def suggestThreadPoolSize(self, size):
        """
        Approximate the behavior of a "real" reactor.
        """
        self._pool.adjustPoolsize(maxthreads=size)


    def callInThread(self, thunk, *a, **kw):
        """
        No implementation.
        """

    def callFromThread(self, thunk, *a, **kw):
        """
        No implementation.
        """

verifyClass(IReactorThreads, ClockWithThreads)



class ConnectionPoolHelper(object):
    """
    Connection pool setting-up facilities for tests that need a
    L{ConnectionPool}.
    """

    dialect = POSTGRES_DIALECT
    paramstyle = DEFAULT_PARAM_STYLE

    def setUp(self, test=None, connect=None):
        """
        Support inheritance by L{TestCase} classes.
        """
        if test is None:
            test = self
        if connect is None:
            self.factory = ConnectionFactory()
            connect = self.factory.connect
        self.connect = connect
        self.paused = False
        self.holders = []
        self.pool = ConnectionPool(
            connect,
            maxConnections=2,
            dialect=self.dialect,
            paramstyle=self.paramstyle
        )
        self.pool._createHolder = self.makeAHolder
        self.clock = self.pool.reactor = ClockWithThreads()
        self.pool.startService()
        test.addCleanup(self.flushHolders)


    def flushHolders(self):
        """
        Flush all pending C{submit}s since C{pauseHolders} was called.  This
        makes sure the service is stopped and the fake ThreadHolders are all
        executing their queues so failed tests can exit cleanly.
        """
        self.paused = False
        for holder in self.holders:
            holder.flush()


    def pauseHolders(self):
        """
        Pause all L{FakeThreadHolder}s, causing C{submit} to return an unfired
        L{Deferred}.
        """
        self.paused = True


    def makeAHolder(self):
        """
        Make a ThreadHolder-alike.
        """
        fth = FakeThreadHolder(self)
        self.holders.append(fth)
        return fth


    def resultOf(self, it):
        return resultOf(it)


    def createTransaction(self):
        return self.pool.connection()


    def translateError(self, err):
        return err



class SteppablePoolHelper(ConnectionPoolHelper):
    """
    A version of L{ConnectionPoolHelper} that can set up a connection pool
    capable of firing all its L{Deferred}s on demand, synchronously, by using
    SQLite.
    """
    dialect = SQLITE_DIALECT
    paramstyle = sqlite3.paramstyle

    def __init__(self, schema):
        self.schema = schema


    def setUp(self, test):
        connect = synchronousConnectionFactory(test)
        con = connect()
        cur = con.cursor()
        cur.executescript(self.schema)
        con.commit()
        super(SteppablePoolHelper, self).setUp(test, connect)


    def rows(self, sql):
        """
        Get some rows from the database to compare in a test.
        """
        con = self.connect()
        cur = con.cursor()
        cur.execute(sql)
        result = cur.fetchall()
        con.commit()
        return result



def synchronousConnectionFactory(test):
    tmpdb = test.mktemp()

    def connect():
        return sqlite3.connect(tmpdb, isolation_level=None)

    return connect



class Child(object):
    """
    An object with a L{Parent}, in its list of C{children}.
    """
    def __init__(self, parent):
        self.closed = False
        self.parent = parent
        self.parent.children.append(self)


    def close(self):
        if self.parent._closeFailQueue:
            raise self.parent._closeFailQueue.pop(0)
        self.closed = True



class Parent(object):
    """
    An object with a list of L{Child}ren.
    """

    def __init__(self):
        self.children = []
        self._closeFailQueue = []


    def childCloseWillFail(self, exception):
        """
        Closing children of this object will result in the given exception.

        @see: L{ConnectionFactory}
        """
        self._closeFailQueue.append(exception)



class FakeConnection(Parent, Child):
    """
    Fake Stand-in for DB-API 2.0 connection.

    @ivar executions: the number of statements which have been executed.

    """

    executions = 0

    def __init__(self, factory):
        """
        Initialize list of cursors
        """
        Parent.__init__(self)
        Child.__init__(self, factory)
        self.id = factory.idcounter.next()
        self._executeFailQueue = []
        self._commitCount = 0
        self._rollbackCount = 0


    def executeWillFail(self, thunk):
        """
        The next call to L{FakeCursor.execute} will fail with an exception
        returned from the given callable.
        """
        self._executeFailQueue.append(thunk)


    @property
    def cursors(self):
        "Alias to make tests more readable."
        return self.children


    def cursor(self):
        return FakeCursor(self)


    def commit(self):
        self._commitCount += 1
        if self.parent.commitFail:
            self.parent.commitFail = False
            raise CommitFail()


    def rollback(self):
        self._rollbackCount += 1
        if self.parent.rollbackFail:
            self.parent.rollbackFail = False
            raise RollbackFail()



class RollbackFail(Exception):
    """
    Sample rollback-failure exception.
    """



class CommitFail(Exception):
    """
    Sample Commit-failure exception.
    """



class FakeCursor(Child):
    """
    Fake stand-in for a DB-API 2.0 cursor.
    """
    def __init__(self, connection):
        Child.__init__(self, connection)
        self.rowcount = 0
        # not entirely correct, but all we care about is its truth value.
        self.description = False
        self.variables = []
        self.allExecutions = []


    @property
    def connection(self):
        "Alias to make tests more readable."
        return self.parent


    def execute(self, sql, args=()):
        if self.connection.closed:
            raise FakeConnectionError
        self.connection.executions += 1
        if self.connection._executeFailQueue:
            raise self.connection._executeFailQueue.pop(0)()
        self.allExecutions.append((sql, args))
        self.sql = sql
        factory = self.connection.parent
        self.description = factory.hasResults
        if factory.hasResults and factory.shouldUpdateRowcount:
            self.rowcount = 1
        else:
            self.rowcount = 0
        return


    def var(self, type, *args):
        """
        Return a database variable in the style of the cx_Oracle bindings.
        """
        v = FakeVariable(self, type, args)
        self.variables.append(v)
        return v


    def fetchall(self):
        """
        Just echo the SQL that was executed in the last query.
        """
        if self.connection.parent.hasResults:
            return [[self.connection.id, self.sql]]
        if self.description:
            return []
        return None



class FakeVariable(object):
    def __init__(self, cursor, type, args):
        self.cursor = cursor
        self.type = type
        self.args = args


    def getvalue(self):
        vv = self.cursor.connection.parent.varvals
        if vv:
            return vv.pop(0)
        return self.cursor.variables.index(self) + 300


    def __reduce__(self):
        raise RuntimeError("Not pickleable (since oracle vars aren't)")



class ConnectionFactory(Parent):
    """
    A factory for L{FakeConnection} objects.

    @ivar shouldUpdateRowcount: Should C{execute} on cursors produced by
        connections produced by this factory update their C{rowcount} or just
        their C{description} attribute?

    @ivar hasResults: should cursors produced by connections by this factory
        have any results returned by C{fetchall()}?
    """

    rollbackFail = False
    commitFail = False

    def __init__(self, shouldUpdateRowcount=True, hasResults=True):
        Parent.__init__(self)
        self.idcounter = count(1)
        self._connectResultQueue = []
        self.defaultConnect()
        self.varvals = []
        self.shouldUpdateRowcount = shouldUpdateRowcount
        self.hasResults = hasResults


    @property
    def connections(self):
        "Alias to make tests more readable."
        return self.children


    def connect(self):
        """
        Implement the C{ConnectionFactory} callable expected by
        L{ConnectionPool}.
        """
        if self._connectResultQueue:
            thunk = self._connectResultQueue.pop(0)
        else:
            thunk = self._default
        return thunk()


    def willConnect(self):
        """
        Used by tests to queue a successful result for connect().
        """
        def thunk():
            return FakeConnection(self)
        self._connectResultQueue.append(thunk)


    def willConnectTo(self):
        """
        Queue a successful result for connect() and immediately add it as a
        child to this L{ConnectionFactory}.

        @return: a connection object
        @rtype: L{FakeConnection}
        """
        aConnection = FakeConnection(self)

        def thunk():
            return aConnection

        self._connectResultQueue.append(thunk)
        return aConnection


    def willFail(self):
        """
        Used by tests to queue a successful result for connect().
        """
        def thunk():
            raise FakeConnectionError()
        self._connectResultQueue.append(thunk)


    def defaultConnect(self):
        """
        By default, connection attempts will succeed.
        """
        self.willConnect()
        self._default = self._connectResultQueue.pop()


    def defaultFail(self):
        """
        By default, connection attempts will fail.
        """
        self.willFail()
        self._default = self._connectResultQueue.pop()



class FakeConnectionError(Exception):
    """
    Synthetic error that might occur during connection.
    """
