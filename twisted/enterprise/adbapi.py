# -*- test-case-name: twisted.test.test_adbapi -*-
# Copyright (c) 2001-2008 Twisted Matrix Laboratories.
# See LICENSE for details.


"""
An asynchronous mapping to U{DB-API 2.0<http://www.python.org/topics/database/DatabaseAPI-2.0.html>}.
"""

from twisted.internet import defer, threads
from twisted.python import reflect, log
from twisted.python.deprecate import deprecated
from twisted.python.versions import Version


class ConnectionLost(Exception):
    """This exception means that a db connection has been lost.
    Client code may try again."""
    pass
    
    
class Connection(object):
    """A wrapper for a DB-API connection instance.
    
    The wrapper passes almost everything to the wrapped connection and so has
    the same API. However, the Connection knows about its pool and also
    handle reconnecting should when the real connection dies.
    """
    
    def __init__(self, pool):
        self._pool = pool
        self._connection = None
        self.reconnect()
        
    def close(self):
        # The way adbapi works right now means that closing a connection is
        # a really bad thing  as it leaves a dead connection associated with
        # a thread in the thread pool.
        # Really, I think closing a pooled connection should return it to the
        # pool but that's handled by the runWithConnection method already so,
        # rather than upsetting anyone by raising an exception, let's ignore
        # the request
        pass
        
    def rollback(self):
        if not self._pool.reconnect:
            self._connection.rollback()
            return

        try:
            self._connection.rollback()
            curs = self._connection.cursor()
            curs.execute(self._pool.good_sql)
            curs.close()
            self._connection.commit()
            return
        except:
            pass

        self._pool.disconnect(self._connection)

        if self._pool.noisy:
            log.msg('Connection lost.')

        raise ConnectionLost()

    def reconnect(self):
        if self._connection is not None:
            self._pool.disconnect(self._connection)
        self._connection = self._pool.connect()
        
    def __getattr__(self, name):
        return getattr(self._connection, name)
        
        
class Transaction:
    """A lightweight wrapper for a DB-API 'cursor' object.

    Relays attribute access to the DB cursor. That is, you can call
    execute(), fetchall(), etc., and they will be called on the
    underlying DB-API cursor object. Attributes will also be
    retrieved from there.
    """
    _cursor = None

    def __init__(self, pool, connection):
        self._pool = pool
        self._connection = connection
        self.reopen()

    def close(self):
        _cursor = self._cursor
        self._cursor = None
        _cursor.close()

    def reopen(self):
        if self._cursor is not None:
            self.close()

        try:
            self._cursor = self._connection.cursor()
            return
        except:
            if not self._pool.reconnect:
                raise

        if self._pool.noisy:
            log.msg('Connection lost, reconnecting')

        self.reconnect()
        self._cursor = self._connection.cursor()

    def reconnect(self):
        self._connection.reconnect()
        self._cursor = None

    def __getattr__(self, name):
        return getattr(self._cursor, name)


class ConnectionPool:
    """I represent a pool of connections to a DB-API 2.0 compliant database.
    """

    CP_ARGS = "min max name noisy openfun reconnect good_sql".split()

    noisy = True # if true, generate informational log messages
    min = 3 # minimum number of connections in pool
    max = 5 # maximum number of connections in pool
    name = None # Name to assign to thread pool for debugging
    openfun = None # A function to call on new connections
    reconnect = False # reconnect when connections fail
    good_sql = 'select 1' # a query which should always succeed

    running = False # true when the pool is operating

    def __init__(self, dbapiName, *connargs, **connkw):
        """Create a new ConnectionPool.

        Any positional or keyword arguments other than those documented here
        are passed to the DB-API object when connecting. Use these arguments to
        pass database names, usernames, passwords, etc.

        @param dbapiName: an import string to use to obtain a DB-API compatible
                          module (e.g. 'pyPgSQL.PgSQL')

        @param cp_min: the minimum number of connections in pool (default 3)

        @param cp_max: the maximum number of connections in pool (default 5)

        @param cp_noisy: generate informational log messages during operation
                         (default False)

        @param cp_openfun: a callback invoked after every connect() on the
                           underlying DB-API object. The callback is passed a
                           new DB-API connection object.  This callback can
                           setup per-connection state such as charset,
                           timezone, etc.

        @param cp_reconnect: detect connections which have failed and reconnect
                             (default False). Failed connections may result in
                             ConnectionLost exceptions, which indicate the
                             query may need to be re-sent.

        @param cp_good_sql: an sql query which should always succeed and change
                            no state (default 'select 1')
        """

        self.dbapiName = dbapiName
        self.dbapi = reflect.namedModule(dbapiName)

        if getattr(self.dbapi, 'apilevel', None) != '2.0':
            log.msg('DB API module not DB API 2.0 compliant.')

        if getattr(self.dbapi, 'threadsafety', 0) < 1:
            log.msg('DB API module not sufficiently thread-safe.')

        self.connargs = connargs
        self.connkw = connkw

        for arg in self.CP_ARGS:
            cp_arg = 'cp_%s' % arg
            if connkw.has_key(cp_arg):
                setattr(self, arg, connkw[cp_arg])
                del connkw[cp_arg]

        self.min = min(self.min, self.max)
        self.max = max(self.min, self.max)

        self.connections = {}  # all connections, hashed on thread id

        # these are optional so import them here
        from twisted.python import threadpool
        import thread

        self.threadID = thread.get_ident
        self.threadpool = threadpool.ThreadPool(self.min, self.max)

        from twisted.internet import reactor
        self.startID = reactor.callWhenRunning(self._start)

    def _start(self):
        self.startID = None
        return self.start()

    def start(self):
        """Start the connection pool.

        If you are using the reactor normally, this function does *not*
        need to be called.
        """

        if not self.running:
            from twisted.internet import reactor
            self.threadpool.start()
            self.shutdownID = reactor.addSystemEventTrigger('during',
                                                            'shutdown',
                                                            self.finalClose)
            self.running = True
            
    def runWithConnection(self, func, *args, **kw):
        return self._deferToThread(self._runWithConnection,
                                   func, *args, **kw)

    def _runWithConnection(self, func, *args, **kw):
        conn = Connection(self)
        try:
            result = func(conn, *args, **kw)
            conn.commit()
            return result
        except:
            conn.rollback()
            raise
        
    def runInteraction(self, interaction, *args, **kw):
        """Interact with the database and return the result.

        The 'interaction' is a callable object which will be executed
        in a thread using a pooled connection. It will be passed an
        L{Transaction} object as an argument (whose interface is
        identical to that of the database cursor for your DB-API
        module of choice), and its results will be returned as a
        Deferred. If running the method raises an exception, the
        transaction will be rolled back. If the method returns a
        value, the transaction will be committed.

        NOTE that the function you pass is *not* run in the main
        thread: you may have to worry about thread-safety in the
        function you pass to this if it tries to use non-local
        objects.

        @param interaction: a callable object whose first argument is
            L{adbapi.Transaction}. *args,**kw will be passed as
            additional arguments.

        @return: a Deferred which will fire the return value of
            'interaction(Transaction(...))', or a Failure.
        """

        return self._deferToThread(self._runInteraction,
                                   interaction, *args, **kw)

    def runQuery(self, *args, **kw):
        """Execute an SQL query and return the result.

        A DB-API cursor will will be invoked with cursor.execute(*args, **kw).
        The exact nature of the arguments will depend on the specific flavor
        of DB-API being used, but the first argument in *args be an SQL
        statement. The result of a subsequent cursor.fetchall() will be
        fired to the Deferred which is returned. If either the 'execute' or
        'fetchall' methods raise an exception, the transaction will be rolled
        back and a Failure returned.

        The  *args and **kw arguments will be passed to the DB-API cursor's
        'execute' method.

        @return: a Deferred which will fire the return value of a DB-API
        cursor's 'fetchall' method, or a Failure.
        """

        return self.runInteraction(self._runQuery, *args, **kw)

    def runOperation(self, *args, **kw):
        """Execute an SQL query and return None.

        A DB-API cursor will will be invoked with cursor.execute(*args, **kw).
        The exact nature of the arguments will depend on the specific flavor
        of DB-API being used, but the first argument in *args will be an SQL
        statement. This method will not attempt to fetch any results from the
        query and is thus suitable for INSERT, DELETE, and other SQL statements
        which do not return values. If the 'execute' method raises an
        exception, the transaction will be rolled back and a Failure returned.

        The args and kw arguments will be passed to the DB-API cursor's
        'execute' method.

        return: a Deferred which will fire None or a Failure.
        """

        return self.runInteraction(self._runOperation, *args, **kw)

    def close(self):
        """Close all pool connections and shutdown the pool."""

        from twisted.internet import reactor
        if self.shutdownID:
            reactor.removeSystemEventTrigger(self.shutdownID)
            self.shutdownID = None
        if self.startID:
            reactor.removeSystemEventTrigger(self.startID)
            self.startID = None
        self.finalClose()

    def finalClose(self):
        """This should only be called by the shutdown trigger."""

        self.shutdownID = None
        self.threadpool.stop()
        self.running = False
        for conn in self.connections.values():
            self._close(conn)
        self.connections.clear()

    def connect(self):
        """Return a database connection when one becomes available.

        This method blocks and should be run in a thread from the internal
        threadpool. Don't call this method directly from non-threaded code.
        Using this method outside the external threadpool may exceed the
        maximum number of connections in the pool.

        @return: a database connection from the pool.
        """

        tid = self.threadID()
        conn = self.connections.get(tid)
        if conn is None:
            if self.noisy:
                log.msg('adbapi connecting: %s %s%s' % (self.dbapiName,
                                                        self.connargs or '',
                                                        self.connkw or ''))
            conn = self.dbapi.connect(*self.connargs, **self.connkw)
            if self.openfun != None:
                self.openfun(conn)
            self.connections[tid] = conn
        return conn

    def disconnect(self, conn):
        """Disconnect a database connection associated with this pool.

        Note: This function should only be used by the same thread which
        called connect(). As with connect(), this function is not used
        in normal non-threaded twisted code.
        """

        tid = self.threadID()
        if conn is not self.connections.get(tid):
            raise Exception("wrong connection for thread")
        if conn is not None:
            self._close(conn)
            del self.connections[tid]

    def _close(self, conn):
        if self.noisy:
            log.msg('adbapi closing: %s' % (self.dbapiName,))
        try:
            conn.close()
        except:
            pass

    def _runInteraction(self, interaction, *args, **kw):
        conn = Connection(self)
        trans = Transaction(self, conn)
        try:
            result = interaction(trans, *args, **kw)
            trans.close()
            conn.commit()
            return result
        except:
            conn.rollback()
            raise

    def _runQuery(self, trans, *args, **kw):
        trans.execute(*args, **kw)
        return trans.fetchall()

    def _runOperation(self, trans, *args, **kw):
        trans.execute(*args, **kw)

    def __getstate__(self):
        return {'dbapiName': self.dbapiName,
                'min': self.min,
                'max': self.max,
                'noisy': self.noisy,
                'reconnect': self.reconnect,
                'good_sql': self.good_sql,
                'connargs': self.connargs,
                'connkw': self.connkw}

    def __setstate__(self, state):
        self.__dict__ = state
        self.__init__(self.dbapiName, *self.connargs, **self.connkw)

    def _deferToThread(self, f, *args, **kwargs):
        """Internal function.

        Call f in one of the connection pool's threads.
        """

        d = defer.Deferred()
        self.threadpool.callInThread(threads._putResultInDeferred,
                                     d, f, args, kwargs)
        return d



# Common deprecation decorator used for all deprecations.
_unreleasedVersion = Version("Twisted", 2, 6, 0)
_unreleasedDeprecation = deprecated(_unreleasedVersion)



def _safe(text):
    """
    Something really stupid that replaces quotes with escaped quotes.
    """
    return text.replace("'", "''").replace("\\", "\\\\")



def safe(text):
    """
    Make a string safe to include in an SQL statement.
    """
    return _safe(text)

safe = _unreleasedDeprecation(safe)


__all__ = ['Transaction', 'ConnectionPool', 'safe']
