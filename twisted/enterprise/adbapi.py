
"""An asynchronous mapping to DB-API.

This is designed to integrate with twisted.internet.threadtask.
"""
import traceback
    
from twisted.spread import pb
from twisted.internet import task, threadtask
from twisted.python import reflect, log, defer, failure

class EntityObject:
    """Default class for database objects. Knows how to save itself back to the db.
    Should use a class derived from this class for each database table. Objects of these
    classes are constructed by the object loader.
    """
    columns = []     # list of column names and types for the table I came from
    keyColumns = []  # list of key columns to identify instances in the db
    tableName = ""
    updateSQL = ""
    
    def updateMe(self):
        """update my contents to the database.
        """
        args = []
        
        # build update attributes
        for column, type, typeid in self.columns:
            found = 0
            # be sure not to update key columns            
            for keyColumn, type in self.keyColumns:
                if column == keyColumn:
                    found = 1
            if found:
                continue
            args.append(self.__dict__[column])
            
        # build where clause
        for keyColumn, type in self.keyColumns:
            args.append( self.__dict__[keyColumn])

        sql = self.updateSQL % tuple(args)
        return self.augmentation.runOperation(sql)


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
        
    def loadObjectsFrom(self, tableName, keyColumns, entityClass = EntityObject, whereClause = "1 = 1"):
        """Create a set of python objects of <entityClass> from the contents of a table
        populated with appropriate data members. The constructor for <entityClass> must take
        no args. Example to use this:

        class EmployeeEntity:
            pass
            
        def gotEmployees(employees):
            for emp in employees:
                emp.manager = "fred smith"
                emp.updateMe()

        manager.loadObjectsFrom("employee",
                                ["employee_name", "varchar"],
                                EmployeeEntity).addCallback(getEmployees)

        NOTE: this functionality is experimental. be careful.
        """
        return self.runInteraction(self._objectLoader, tableName, keyColumns, entityClass, whereClause)

    def _objectLoader(self, transaction, tableName, keyColumns, entityClass, whereClause):
        """worker method to load objects from a table.
        NOTE: works with Postgresql for now...
        NOTE: 26 - 29 are system column types that you shouldn't use...
        """

        sql = """SELECT pg_attribute.attname, pg_type.typname, pg_attribute.atttypid
        FROM pg_class, pg_attribute, pg_type
        WHERE pg_class.oid = pg_attribute.attrelid
        AND pg_attribute.atttypid = pg_type.oid
        AND pg_class.relname = '%s'
        AND pg_attribute.atttypid not in (26,27,28,29)""" % tableName

        # get the columns for the table
        transaction.execute(sql)
        columns = transaction.fetchall()

        # get the data from the table
        sql = """SELECT * FROM %s WHERE %s""" % (tableName, whereClause)
        transaction.execute(sql)
        rows = transaction.fetchall()

        # populate entityClass data
        self.buildSQL(entityClass, tableName, columns, keyColumns)

        # construct the objects
        results = []        
        for row in rows:
            resultObject = apply(entityClass)
            for i in range(0, len(columns)):
                #print columns[i], row[i]
                resultObject.__dict__[columns[i][0]] = row[i]
            results.append(resultObject)

        #print "RESULTS", results
        return results

    def buildSQL(self, entityClass, tableName, columns, keyColumns):
        """build the SQL to update objects of <entityClass> to the database. This 
        populates the class attributes used when doing updates.
        """

        if entityClass.tableName and entityClass.tableName != tableName:
            raise ("ERROR: class %s has already had SQL generated for table %s." % (repr(entityClass), tableName) )

        entityClass.tableName = tableName
        entityClass.columns = columns
        entityClass.keyColumns = keyColumns
        entityClass.augmentation = self

        sql = "UPDATE %s SET" % tableName

        # build update attributes
        first = 1        
        for column, type, typeid in columns:
            found = 0
            # be sure not to update key columns
            for keyColumn, ktype in keyColumns:
                print "column", column, keyColumn
                if column == keyColumn:
                    found = 1
            if found:
                continue
            if not first:
                sql = sql + ", "
            sql = sql + "  %s = %s" % (column, quote("%s", type))
            first = 0

        # build where clause
        first = 1
        sql = sql + "  WHERE "
        for keyColumn, type in keyColumns:
            if not first:
                sql = sql + " AND "
            sql = sql + "   %s = %s " % (keyColumn, quote("%s", type) )
            first = 0

        print "Generated SQL:", sql
        entityClass.updateSQL = sql
        return 1



### Utility functions


NOQUOTE = 1
USEQUOTE = 2

dbTypeMap = {
    "bool": NOQUOTE,    
    "int2": NOQUOTE,
    "int4": NOQUOTE,
    "float8": NOQUOTE,
    "char": USEQUOTE,
    "varchar": USEQUOTE,
    "text": USEQUOTE,
    "timestamp": USEQUOTE
    }


def safe(text):
    """Make a string safe to include in an SQL statement
    """
    return text.replace("'", "''")

def quote(value, typeCode):
    """Add quotes for text types and no quotes for integer types.
    NOTE: uses Postgresql type codes..
    """
    q = dbTypeMap.get(typeCode, None)
    if not q:
        raise ("Type %s not known" % typeCode)
    if q == NOQUOTE:
        return value
    elif q == USEQUOTE:
        return "'%s'" % safe(value)

