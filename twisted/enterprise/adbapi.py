
"""An asynchronous mapping to DB-API.

This is designed to integrate with twisted.internet.threadtask.
"""

from twisted.spread import pb
from twisted.internet import task, threadtask
from twisted.python import reflect, log, defer

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
    def __init__(self, dbapiName, *connargs, **connkw):
        """See ConnectionPool.__doc__
        """
        self.dbapiName = dbapiName
        print "Connecting to database: %s %s %s" % (dbapiName, connargs, connkw)
        self.dbapi = reflect.namedModule(dbapiName)
        assert self.dbapi.apilevel == '2.0', 'DB API module not DB API 2.0 compliant.'
        assert self.dbapi.threadsafety > 0, 'DB API module not sufficiently thread-safe.'
        self.connargs = connargs
        self.connkw = connkw
        import thread
        self.threadID = thread.get_ident
        self.connections = {}

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
            print 'connecting using', self.dbapiName, self.connargs, self.connkw
            conn = apply(self.dbapi.connect, self.connargs, self.connkw)
            self.connections[tid] = conn
            print 'connected'
        return conn

    def _runQuery(self, qstr, eater, chunkSize):
        conn = self.connect()
        curs = conn.cursor()
        try:
            curs.execute(qstr)
            if eater is not None:
                task.schedule(eater, curs.fetchmany(chunkSize))
                result = None
            else:
                result = curs.fetchall()
                curs.close()
        except:
            print 'ERROR: runQuery traceback'
            # NOTE: dont rollback queries...
            # conn.rollback()
            traceback.print_exc()
            raise
        return result


    def _runOperation(self, qstr):
        """This is used for non-query operations that don't want "fetch*" to be called
        """
        # print 'running operation'
        conn = self.connect()
        curs = conn.cursor()
        try:
            curs.execute(qstr)
            result = None
            curs.close()
            conn.commit()
        except:
            conn.rollback()
            # traceback.print_exc()
            raise
        return result

    def query(self, qstr, callback, errback, eater=None, chunkSize=1):
        threadtask.dispatch(callback, errback, self._runQuery, qstr, eater, chunkSize)

    def operation(self, qstr, callback, errback, eater=None, chunkSize=1):
        threadtask.dispatch(callback, errback, self._runOperation, qstr)

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

            
class Augmentation:
    '''A class which augments a database connector with some functionality.

    Conventional usage of me is to write methods that look like

      |  def getSomeData(self, critereon, callbackIn, errbackIn):
      |      return self.runQuery("SELECT * FROM FOO WHERE BAR LIKE '%%%s%%'" % critereon, callbackIn, errbackIn)
    
    '''

    def __init__(self, dbpool):
        self.dbpool = dbpool
        self.createSchema().arm()

    def __setstate__(self, state):
        self.__dict__ = state
        self.createSchema().arm()

    def operationDone(self, done):
        """Default callback for database operation success.
        """
        log.msg("%s Operation Done: %s" % (str(self.__class__), done))

    def operationError(self, error):
        """Default callback for database operation failure.
        """
        # error.print_traceback()
        log.msg("%s Operation Failed: %s" % (str(self.__class__), error))

    schema = ''' Insert your SQL database schema here. '''

    def createSchema(self):
        return self.runOperation(self.schema, self.schemaCreated, self.schemaNotCreated)

    def schemaCreated(self, result):
        log.msg("Successfully created schema for %s." % str(self.__class__))

    def schemaNotCreated(self, error):
        log.msg("Schema already exists for %s." % str(self.__class__))

    def runQuery(self, querySQL, callback, errback):
        d = defer.Deferred()
        d.addCallbacks(callback, errback)
        self.dbpool.query(querySQL, d.callback, d.errback)
        return d

    def runOperation(self, updateSQL, callback=None, errback=None):
        d = defer.Deferred()
        d.addCallbacks(callback or self.operationDone,
                       errback or self.operationError)
        self.dbpool.operation(updateSQL, d.callback, d.errback)
        return d

