
"""An asynchronous mapping to DB-API.

This is designed to integrate with twisted.internet.threadtask.
"""

from twisted.python import threadable
from twisted.spread import pb
from twisted.internet import task, threadtask

import traceback

class Transaction:
    def __init__(self, pool, connection):
        self._connection = connection
        self._cursor = connection.cursor()
        self.cursor = connection.cursor
        self.execute = cursor.execute
        self.fetchone = cursor.fetchone
        self.executemany = cursor.executemany
        self.fetchmany = cursor.fetchmany
        self.fetchall = cursor.fetchall

class ConnectionPool(pb.Referenceable):
    """I represent a pool of connections to a DB-API 2.0 compliant database.
    """
    def __init__(self, dbapi, *connargs, **connkw):
        """See ConnectionPool.__doc__
        """
        self.dbapi = dbapi
        assert dbapi.apilevel == '2.0', 'DB API module not DB API 2.0 compliant.'
        assert dbapi.threadsafety > 0, 'DB API module not sufficiently thread-safe.'
        self.connargs = connargs
        self.connkw = connkw
        import thread
        self.threadID = thread.get_ident
        self.connections = {}

    def connect(self):
        print 'connecting'
        tid = self.threadID()
        conn = self.connections.get(tid)
        if not conn:
            conn = apply(self.dbapi.connect, self.connargs, self.connkw)
            self.connections[tid] = conn
            print 'connected'
        else:
            print 'already'
        return conn

    def _runQuery(self, qstr, eater, chunkSize):
        print 'running query'
        conn = self.connect()
        curs = conn.cursor()
        try:
            curs.execute(qstr)
            print 'ran it!'
            if eater is not None:
                task.schedule(eater, curs.fetchmany(chunkSize))
                result = None
            else:
                result = curs.fetchall()
        except:
            print 'oops!'
            conn.rollback()
            traceback.print_exc()
            raise
        return result

    def query(self, qstr, callback, errback, eater=None, chunkSize=1):
        threadtask.dispatch(callback, errback, self._runQuery, qstr, eater, chunkSize)

    def interact(self, interaction, callback, errback):
        """Interact with the database.

        Arguments:

          * interaction: a callable object which takes 1 argument; a transaction.

        The callable object presented here will be executed in an arbitrary
        thread.  'callback' will be made in the main thread upon success and
        'errback' will be called upon failure.  If 'callback' is called, that
        means that the transaction was committed; if 'errback', it was rolled
        back.  This does not apply in databases which do not support
        transactions.
        """
        threadtask.dispatch(callback, errback, self._runInteraction, interaction)

    def _runInteraction(self, interaction):
        if not trans:
            self.transactions[tid] = trans = Transaction(self, self.connect())
        try:
            interaction(trans)
        except:
            print 'Exception in SQL query!  rolling back...'
            trans._connection.rollback()
            raise
        else:
            trans._connection.commit()

