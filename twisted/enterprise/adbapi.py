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

from twisted.spread import pb
from twisted.internet import defer
from twisted.internet import threads
from twisted.python import reflect, log, failure


class Transaction:
    """
    I am a lightweight wrapper for a database 'cursor' object.  I relay
    attribute access to the DB cursor.
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


class ConnectionPool(pb.Referenceable):
    """I represent a pool of connections to a DB-API 2.0 compliant database.

    You can pass the noisy arg which determines whether informational
    log messages are generated during the pool's operation.
    """
    noisy = 1

    # XXX - make the min and max attributes (and cp_min and cp_max
    # kwargs to __init__) actually do something?
    min = 3
    max = 5

    def __init__(self, dbapiName, *connargs, **connkw):
        """See ConnectionPool.__doc__
        """
        self.dbapiName = dbapiName
        if self.noisy:
            log.msg("Connecting to database: %s %s %s" %
                    (dbapiName, connargs, connkw))
        self.dbapi = reflect.namedModule(dbapiName)

        if getattr(self.dbapi, 'apilevel', None) != '2.0':
            log.msg('DB API module not DB API 2.0 compliant.')

        if getattr(self.dbapi, 'threadsafety', 0) < 1:
            log.msg('DB API module not sufficiently thread-safe.')

        self.connargs = connargs
        self.connkw = connkw

        import thread
        self.threadID = thread.get_ident
        self.connections = {}

        if connkw.has_key('cp_min'):
            self.min = connkw['cp_min']
            del connkw['cp_min']

        if connkw.has_key('cp_max'):
            self.max = connkw['cp_max']
            del connkw['cp_max']

        if connkw.has_key('cp_noisy'):
            self.noisy = connkw['cp_noisy']
            del connkw['cp_noisy']

        from twisted.internet import reactor
        self.shutdownID = reactor.addSystemEventTrigger('during', 'shutdown',
                                                        self.finalClose)

    def runInteraction(self, interaction, *args, **kw):
        """Interact with the database and return the result.

        The 'interaction' is a callable object which will be executed in a
        pooled thread.  It will be passed an L{Transaction} object as an
        argument (whose interface is identical to that of the database cursor
        for your DB-API module of choice), and its results will be returned as
        a Deferred.  If running the method raises an exception, the transaction
        will be rolled back.  If the method returns a value, the transaction
        will be committed.

        @param interaction: a callable object whose first argument is
            L{adbapi.Transaction}.
        @param *args,**kw: additional arguments to be passed to 'interaction'

        @return: a Deferred which will fire the return value of
        'interaction(Transaction(...))', or a Failure.
        """

        d = defer.Deferred()
        apply(self.interaction, (interaction,d.callback,d.errback,)+args, kw)
        return d

    def __getstate__(self):
        return {'dbapiName': self.dbapiName,
                'noisy': self.noisy,
                'min': self.min,
                'max': self.max,
                'connargs': self.connargs,
                'connkw': self.connkw}

    def __setstate__(self, state):
        self.__dict__ = state
        apply(self.__init__, (self.dbapiName, )+self.connargs, self.connkw)

    def connect(self):
        """Should be run in thread, blocks.

        Don't call this method directly from non-threaded twisted code.
        """
        tid = self.threadID()
        conn = self.connections.get(tid)
        if not conn:
            conn = apply(self.dbapi.connect, self.connargs, self.connkw)
            self.connections[tid] = conn
            if self.noisy:
                log.msg('adbapi connecting: %s %s%s' %
                    ( self.dbapiName, self.connargs or '', self.connkw or ''))
        return conn

    def _runQuery(self, args, kw):
        conn = self.connect()
        curs = conn.cursor()
        try:
            apply(curs.execute, args, kw)
            result = curs.fetchall()
            curs.close()
            conn.commit()
            return result
        except:
            conn.rollback()
            raise

    def _runOperation(self, args, kw):
        conn = self.connect()
        curs = conn.cursor()

        try:
            apply(curs.execute, args, kw)
            result = None
            curs.close()
            conn.commit()
        except:
            # XXX - failures aren't working here
            conn.rollback()
            raise
        return result

    def query(self, callback, errback, *args, **kw):
        # this will be deprecated ASAP
        threads.deferToThread(self._runQuery, args, kw).addCallbacks(
            callback, errback)

    def operation(self, callback, errback, *args, **kw):
        # this will be deprecated ASAP
        threads.deferToThread(self._runOperation, args, kw).addCallbacks(
            callback, errback)

    def synchronousOperation(self, *args, **kw):
        self._runOperation(args, kw)

    def interaction(self, interaction, callback, errback, *args, **kw):
        # this will be deprecated ASAP
        apply(threads.deferToThread,
              (self._runInteraction, interaction) + args, kw).addCallbacks(
            callback, errback)

    def runOperation(self, *args, **kw):
        """Run a SQL statement and return a Deferred of result."""
        d = defer.Deferred()
        apply(self.operation, (d.callback,d.errback)+args, kw)
        return d

    def runQuery(self, *args, **kw):
        """Run a read-only query and return a Deferred."""
        d = defer.Deferred()
        apply(self.query, (d.callback, d.errback)+args, kw)
        return d

    def _runInteraction(self, interaction, *args, **kw):
        trans = Transaction(self, self.connect())
        try:
            result = apply(interaction, (trans,)+args, kw)
        except:
            log.msg('Exception in SQL interaction!  rolling back...')
            log.deferr()
            trans._connection.rollback()
            raise
        else:
            trans._cursor.close()
            trans._connection.commit()
            return result

    def close(self):
        from twisted.internet import reactor
        reactor.removeSystemEventTrigger(self.shutdownID)
        self.finalClose()

    def finalClose(self):
        for connection in self.connections.values():
            if self.noisy:
                log.msg('adbapi closing: %s %s%s' % (self.dbapiName,
                                                     self.connargs or '',
                                                     self.connkw or ''))
            connection.close()

class Augmentation:
    '''A class which augments a database connector with some functionality.

    Conventional usage of me is to write methods that look like

      >>>  def getSomeData(self, critereon):
      >>>      return self.runQuery("SELECT * FROM FOO WHERE BAR LIKE '%%%s%%'" % critereon).addCallback(self.processResult)

    '''

    def __init__(self, dbpool):
        self.dbpool = dbpool
        #self.createSchema()

    def __setstate__(self, state):
        self.__dict__ = state
        #self.createSchema()

    def operationDone(self, done):
        """Example callback for database operation success.

        Override this, and/or define your own callbacks.
        """
        log.msg("%s Operation Done: %s" % (reflect.qual(self.__class__), done))

    def operationError(self, error):
        """Example callback for database operation failure.

        Override this, and/or define your own callbacks.
        """
        log.msg("%s Operation Failed: %s" % (reflect.qual(self.__class__), error))
        log.err(error)

    schema = ''' Insert your SQL database schema here. '''

    def createSchema(self):
        return self.runOperation(self.schema).addCallbacks(self.schemaCreated, self.schemaNotCreated)

    def schemaCreated(self, result):
        log.msg("Successfully created schema for %s." % reflect.qual(self.__class__))

    def schemaNotCreated(self, error):
        log.msg("Schema already exists for %s." % reflect.qual(self.__class__))

    def runQuery(self, *args, **kw):
        d = defer.Deferred()
        apply(self.dbpool.query, (d.callback, d.errback)+args, kw)
        return d

    def runOperation(self, *args, **kw):
        d = defer.Deferred()
        apply(self.dbpool.operation, (d.callback,d.errback)+args, kw)
        return d

    def runInteraction(self, interaction, *args, **kw):
        d = defer.Deferred()
        apply(self.dbpool.interaction, (interaction,d.callback,d.errback,)+args, kw)
        return d


def safe(text):
    """Make a string safe to include in an SQL statement
    """
    return text.replace("'", "''").replace("\\", "\\\\")
