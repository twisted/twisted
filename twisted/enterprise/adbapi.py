# -*- test-case-name: twisted.test.test_enterprise -*-
# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

"""
An asynchronous mapping to U{DB-API 2.0<http://www.python.org/topics/database/DatabaseAPI-2.0.html>}.
"""

import warnings

from twisted.internet import defer
from twisted.internet import threads
from twisted.python import reflect, log, failure


class Transaction:
    """A lightweight wrapper for a DB-API 'cursor' object.

    Relays attribute access to the DB cursor. That is, you can call
    execute(), fetchall(), etc., and they will be called on the
    underlying DB-API cursor object. Attributes will also be
    retrieved from there.
    """
    _cursor = None

    def __init__(self, pool, connection):
        self._connection = connection
        self.reopen()

    def reopen(self):
        if self._cursor is not None:
            self._cursor.close()
        self._cursor = self._connection.cursor()

    def __getattr__(self, name):
        return getattr(self._cursor, name)


class ConnectionPool:
    """I represent a pool of connections to a DB-API 2.0 compliant database.

    You can pass cp_min, cp_max or both to set the minimum and maximum
    number of connections that will be opened by the pool. You can pass
    the noisy arg which determines whether informational log messages are
    generated during the pool's operation.
    """

    noisy = 1   # if true, generate informational log messages
    min = 3     # minimum number of connections in pool
    max = 5     # maximum number of connections in pool
    running = 0 # true when the pool is operating

    def __init__(self, dbapiName, *connargs, **connkw):
        self.dbapiName = dbapiName
        self.dbapi = reflect.namedModule(dbapiName)

        if getattr(self.dbapi, 'apilevel', None) != '2.0':
            log.msg('DB API module not DB API 2.0 compliant.')

        if getattr(self.dbapi, 'threadsafety', 0) < 1:
            log.msg('DB API module not sufficiently thread-safe.')

        self.connargs = connargs
        self.connkw = connkw

        if connkw.has_key('cp_min'):
            self.min = connkw['cp_min']
            del connkw['cp_min']

        if connkw.has_key('cp_max'):
            self.max = connkw['cp_max']
            del connkw['cp_max']

        if connkw.has_key('cp_noisy'):
            self.noisy = connkw['cp_noisy']
            del connkw['cp_noisy']

        self.min = min(self.min, self.max)
        self.max = max(self.min, self.max)

        self.connections = {}  # all connections, hashed on thread id

        # these are optional so import them here
        from twisted.python import threadpool
        import thread

        self.threadID = thread.get_ident
        self.threadpool = threadpool.ThreadPool(self.min, self.max)

        from twisted.internet import reactor
        self.startID = reactor.callWhenRunning(self.start)

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
            self.running = 1

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

        return self._deferToThread(self._runQuery, *args, **kw)

    def runOperation(self, *args, **kw):
        """Execute an SQL query and return None.

        A DB-API cursor will will be invoked with cursor.execute(*args, **kw).
        The exact nature of the arguments will depend on the specific flavor
        of DB-API being used, but the first argument in *args will be an SQL
        statement. This method will not attempt to fetch any results from the
        query and is thus suitable for INSERT, DELETE, and other SQL statements
        which do not return values. If the 'execute' method raises an exception,
        the transaction will be rolled back and a Failure returned.

        The args and kw arguments will be passed to the DB-API cursor's
        'execute' method.

        return: a Deferred which will fire None or a Failure.
        """
        return self._deferToThread(self._runOperation, *args, **kw)

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
        self.threadpool.stop()
        self.running = 0
        for conn in self.connections.values():
            if self.noisy:
                log.msg('adbapi closing: %s %s%s' % (self.dbapiName,
                                                     self.connargs or '',
                                                     self.connkw or ''))
            conn.close()
        self.connections.clear()

    def connect(self):
        """Return a database connection when one becomes available.

        This method blocks and should be run in a thread from the internal threadpool.
        Don't call this method directly from non-threaded twisted code.

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
            self.connections[tid] = conn
        return conn

    def _runInteraction(self, interaction, *args, **kw):
        trans = Transaction(self, self.connect())
        try:
            result = interaction(trans, *args, **kw)
            trans.close()
            trans._connection.commit()
            return result
        except:
            log.msg('Exception in SQL interaction. Rolling back.')
            log.deferr()
            trans._connection.rollback()
            raise

    def _runQuery(self, *args, **kw):
        conn = self.connect()
        curs = conn.cursor()
        try:
            curs.execute(*args, **kw)
            result = curs.fetchall()
            curs.close()
            conn.commit()
            return result
        except:
            log.msg('Exception in SQL query. Rolling back.')
            log.deferr()
            conn.rollback()
            raise

    def _runOperation(self, *args, **kw):
        conn = self.connect()
        curs = conn.cursor()
        try:
            curs.execute(*args, **kw)
            curs.close()
            conn.commit()
        except:
            log.msg('Exception in SQL operation. Rolling back.')
            log.deferr()
            conn.rollback()
            raise

    def __getstate__(self):
        return {'dbapiName': self.dbapiName,
                'noisy': self.noisy,
                'min': self.min,
                'max': self.max,
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

    def query(self, callback, errback, *args, **kw):
        warnings.warn("This is deprecated. Use runQuery.", DeprecationWarning)
        self._deferToThread(self._runQuery, *args, **kw).addCallbacks(
            callback, errback)

    def operation(self, callback, errback, *args, **kw):
        warnings.warn("This is deprecated. Use runOperation", DeprecationWarning)
        self._deferToThread(self._runOperation, *args, **kw).addCallbacks(
            callback, errback)

    def synchronousOperation(self, *args, **kw):
        warnings.warn("This is deprecated. Use DB-API directly.", DeprecationWarning)
        self._runOperation(*args, **kw)

    def interaction(self, interaction, callback, errback, *args, **kw):
        warnings.warn("This is deprecated. Use runInteraction", DeprecationWarning)
        self._deferToThread(self._runInteraction, interaction,
                            *args, **kw).addCallbacks(callback, errback)


class Augmentation:
    '''This class is now deprecated. Just use the ConnectionPool directly.

    Conventional usage of me is to write methods that look like

      >>>  def getSomeData(self, critereon):
      >>>      return self.runQuery("SELECT * FROM FOO WHERE BAR LIKE '%%%s%%'" % critereon).addCallback(self.processResult)

    '''

    def __init__(self, dbpool):
        warnings.warn("This is deprecated. Use ConnectionPool.", DeprecationWarning)
        self.dbpool = dbpool

    def __setstate__(self, state):
        self.__dict__ = state

    def operationDone(self, done):
        """Example callback for database operation success.

        Override this, and/or define your own callbacks.
        """
        warnings.warn("This is deprecated. Roll your own.", DeprecationWarning)
        log.msg("%s Operation Done: %s" % (reflect.qual(self.__class__), done))

    def operationError(self, error):
        """Example callback for database operation failure.

        Override this, and/or define your own callbacks.
        """
        warnings.warn("This is deprecated. Roll your own.", DeprecationWarning)
        log.msg("%s Operation Failed: %s" % (reflect.qual(self.__class__), error))
        log.err(error)

    schema = ''' Insert your SQL database schema here. '''

    def createSchema(self):
        warnings.warn("This is deprecated. Roll your own.", DeprecationWarning)
        return self.runOperation(self.schema).addCallbacks(self.schemaCreated, self.schemaNotCreated)

    def schemaCreated(self, result):
        warnings.warn("This is deprecated. Roll your own.", DeprecationWarning)
        log.msg("Successfully created schema for %s." % reflect.qual(self.__class__))

    def schemaNotCreated(self, error):
        warnings.warn("This is deprecated. Roll your own.", DeprecationWarning)
        log.msg("Schema already exists for %s." % reflect.qual(self.__class__))

    def runQuery(self, *args, **kw):
        warnings.warn("This is deprecated. Use the ConnectionPool.",
                      DeprecationWarning)
        d = defer.Deferred()
        self.dbpool.query(d.callback, d.errback, *args, **kw)
        return d

    def runOperation(self, *args, **kw):
        warnings.warn("This is deprecated. Use the ConnectionPool.",
                      DeprecationWarning)
        d = defer.Deferred()
        self.dbpool.operation(d.callback, d.errback, *args, **kw)
        return d

    def runInteraction(self, interaction, *args, **kw):
        warnings.warn("This is deprecated. Use the ConnectionPool.",
                      DeprecationWarning)
        d = defer.Deferred()
        self.dbpool.interaction(interaction, d.callback, d.errback,
                                *args, **kw)
        return d


def safe(text):
    """Make a string safe to include in an SQL statement
    """
    return text.replace("'", "''").replace("\\", "\\\\")
