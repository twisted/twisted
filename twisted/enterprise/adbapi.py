"""An asynchronous mapping to DB-API.

This is designed to integrate with twisted.internet.threadtask.
"""
import traceback

from twisted.spread import pb
from twisted.internet import task, threadtask
from twisted.python import reflect, log, defer, failure

# sibling imports
import row

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
            conn.rollback()
            raise
        return result

    def query(self, callback, errback, *args, **kw):
        threadtask.dispatch(callback, errback, self._runQuery, args, kw)

    def operation(self, callback, errback, *args, **kw):
        threadtask.dispatch(callback, errback, self._runOperation, args, kw)

    def interaction(self, interaction, callback, errback, *args, **kw):
        """Interact with the database.

        Arguments:

          * interaction: a callable object whose first argument is an adbapi.Transaction.

          * *args and **kw: additional arguments to be passed to 'interaction'

        The callable object presented here will be executed in a pooled thread.
        'callback' will be made in the main thread upon success and 'errback'
        will be called upon failure.  If 'callback' is called, that means that
        the transaction was committed; if 'errback', it was rolled back.  This
        does not apply in databases which do not support transactions.
        """
        apply(threadtask.dispatch, (callback, errback, self._runInteraction, interaction) + args, kw)

    def _runInteraction(self, interaction, *args, **kw):
        trans = Transaction(self, self.connect())
        try:
            result = apply(interaction, (trans,)+args, kw)
        except:
            print 'Exception in SQL interaction!  rolling back...'
            failure.Failure().printTraceback()
            trans._connection.rollback()
            raise
        else:
            trans._cursor.close()
            trans._connection.commit()
            return result

    def close(self):
        print "Closing connections:"
        for connection in self.connections.values():
            print "closing: ", connection
            connection.close()

class Augmentation:
    '''A class which augments a database connector with some functionality.

    Conventional usage of me is to write methods that look like

      |  def getSomeData(self, critereon):
      |      return self.runQuery("SELECT * FROM FOO WHERE BAR LIKE '%%%s%%'" % critereon).addCallback(self.processResult)

    '''

    def __init__(self, dbpool):
        self.dbpool = dbpool
        #self.createSchema().arm()

    def __setstate__(self, state):
        self.__dict__ = state
        #self.createSchema().arm()

    def operationDone(self, done):
        """Default callback for database operation success.
        """
        log.msg("%s Operation Done: %s" % (str(self.__class__), done))

    def operationError(self, error):
        """Default callback for database operation failure.
        """
        log.msg("%s Operation Failed: %s" % (str(self.__class__), error))
        log.err(error)

    schema = ''' Insert your SQL database schema here. '''

    def createSchema(self):
        return self.runOperation(self.schema, self.schemaCreated, self.schemaNotCreated)

    def schemaCreated(self, result):
        log.msg("Successfully created schema for %s." % str(self.__class__))

    def schemaNotCreated(self, error):
        log.msg("Schema already exists for %s." % str(self.__class__))

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

    def loadObjectsFrom(self, tableName, keyColumns, rowClass = row.RowObject, whereClause = "1 = 1"):
        """Create a set of python objects of <rowClass> from the contents of a table
        populated with appropriate data members. The constructor for <rowClass> must take
        no args. Example to use this:

        class EmployeeRow(row.rowClass):
            pass
            
        def gotEmployees(employees):
            for emp in employees:
                emp.manager = "fred smith"
                emp.updateRow()

        manager.loadObjectsFrom("employee",
                                ["employee_name", "varchar"],
                                "employee_name like 'm%%'",
                                EmployeeRow).addCallback(gotEmployees)

        NOTE: this functionality is experimental. be careful.
        """
        return self.runInteraction(self._objectLoader, tableName, keyColumns, rowClass, whereClause)

    def _objectLoader(self, transaction, tableName, keyColumns, rowClass, whereClause):
        """worker method to load objects from a table.
        """
        if not rowClass.populated:
            row._populateRowClass(transaction, self, rowClass, tableName, keyColumns)

        # get the data from the table
        sql = """SELECT * FROM %s WHERE %s""" % (tableName, whereClause)
        transaction.execute(sql)
        rows = transaction.fetchall()

        # construct the objects
        results = []        
        for r in rows:

            # find the key values
            keys = {}
            i = 0
            for name, type, typeid in rowClass.columns:
                if row.getKeyColumn(rowClass, name):
                    keys[name] = r[i]
                i = i + 1
            
            resultObject = apply(rowClass, (), keys)
            for i in range(0, len(rowClass.columns)):
                if not row.getKeyColumn(rowClass, rowClass.columns[i][0] ):
                    setattr(resultObject, rowClass.columns[i][0], r[i] )
            resultObject.setSync()
            results.append(resultObject)

        #print "RESULTS", results
        return results


safe = row.safe
