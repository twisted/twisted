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
from twisted.internet import task, main, defer
from twisted.internet import threads
from twisted.python import reflect, log, failure


class Transaction:

    def __init__(self, pool, connection):
        self._connection = connection
        cursor = self._cursor = connection.cursor()
        self.execute = cursor.execute
        self.fetchone = cursor.fetchone
        self.executemany = cursor.executemany
        self.fetchmany = cursor.fetchmany
        self.fetchall = cursor.fetchall


class ConnectionPool(pb.Referenceable):
    """I represent a pool of connections to a DB-API 2.0 compliant database.

    You can pass keywords args cp_min and cp_max that will specify the size
    of the thread pool used to serve database requests (possibly this is
    deprecated - it does not work at the moment in any case).
    """
    
    def __init__(self, dbapiName, *connargs, **connkw):
        """See ConnectionPool.__doc__
        """
        self.dbapiName = dbapiName
        log.msg("Connecting to database: %s %s %s" % (dbapiName, connargs, connkw))
        self.dbapi = reflect.namedModule(dbapiName)
        assert self.dbapi.apilevel == '2.0', 'DB API module not DB API 2.0 compliant.'
        assert self.dbapi.threadsafety > 0, 'DB API module not sufficiently thread-safe.'
        self.connargs = connargs
        self.connkw = connkw
        import thread
        self.threadID = thread.get_ident
        self.connections = {}
        if connkw.has_key('cp_min'):
            min = connkw['cp_min']
            del connkw['cp_min']
        else:
            min = 3
        if connkw.has_key('cp_max'):
            max = connkw['cp_max']
            del connkw['cp_max']
        else:
            max = 5
        main.callDuringShutdown(self.close)

    def __getstate__(self):
        return {'dbapiName': self.dbapiName,
                'connargs': self.connargs,
                'connkw': self.connkw}

    def __setstate__(self, state):
        self.__dict__ = state
        apply(self.__init__, (self.dbapiName, )+self.connargs, self.connkw)

    def connect(self):
        tid = self.threadID()
        conn = self.connections.get(tid)
        if not conn:
            conn = apply(self.dbapi.connect, self.connargs, self.connkw)
            self.connections[tid] = conn
            log.msg('adbapi connecting: %s %s%s' %
                    ( self.dbapiName, self.connargs or '', self.connkw or ''))
        return conn

    def _runQuery(self, args, kw):
        conn = self.connect()
        curs = conn.cursor()
        apply(curs.execute, args, kw)
        result = curs.fetchall()
        curs.close()
        return result

    def _runOperation(self, args, kw):
        """This is used for non-query operations that don't want "fetch*" to be called
        """
        
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
        threads.deferToThread(self._runQuery, args, kw).addCallbacks(
            callback, errback)

    def operation(self, callback, errback, *args, **kw):
        threads.deferToThread(self._runOperation, args, kw).addCallbacks(
            callback, errback)

    def synchronousOperation(self, *args, **kw):
        self._runOperation(args, kw)

    def interaction(self, interaction, callback, errback, *args, **kw):
        """Interact with the database.

        The callable object presented here will be executed in a pooled thread.
        'callback' will be made in the main thread upon success and 'errback'
        will be called upon failure.  If 'callback' is called, that means that
        the transaction was committed; if 'errback', it was rolled back.  This
        does not apply in databases which do not support transactions.

        @param interaction: a callable object whose first argument is
            L{adbapi.Transaction}.
        @param *args,**kw: additional arguments to be passed to 'interaction'
        """
        apply(threads.deferToThread,
              (self._runInteraction, interaction) + args, kw).addCallbacks(
            callback, errback)

    def runOperation(self, *args, **kw):
        d = defer.Deferred()
        apply(self.operation, (d.callback,d.errback)+args, kw)
        return d

    def runInteraction(self, interaction, *args, **kw):
        d = defer.Deferred()
        apply(self.interaction, (interaction,d.callback,d.errback,)+args, kw)
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
        for connection in self.connections.values():
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
        """Default callback for database operation success.
        """
        log.msg("%s Operation Done: %s" % (reflect.qual(self.__class__), done))

    def operationError(self, error):
        """Default callback for database operation failure.
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
