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
"""An asynchronous mapping to DB-API.

This is designed to integrate with twisted.internet.threadtask.
"""
import traceback

from twisted.spread import pb
from twisted.internet import task, main
from twisted.internet.threadtask import ThreadDispatcher
from twisted.python import reflect, log, defer, failure

# sibling imports
import row


def defaultFactoryMethod(rowClass, data, kw):
    """Default factory method used by loadObjects to create rowObject instances.
    """
    newObject = rowClass()
    newObject.__dict__.update(kw)
    return newObject

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
        self.dispatcher = ThreadDispatcher(3, 5)
        main.callDuringShutdown(self.dispatcher.stop)

    def __getstate__(self):
        return {'dbapiName': self.dbapiName,
                'connargs': self.connargs,
                'connkw': self.connkw}

    def __setstate__(self, state):
        self.__dict__ = state
        apply(self.__init__, (self.dbapiName, )+self.connargs, self.connkw)
        main.callDuringShutdown(self.dispatcher.stop)

    def connect(self):
        tid = self.threadID()
        conn = self.connections.get(tid)
        if not conn:
            conn = apply(self.dbapi.connect, self.connargs, self.connkw)
            self.connections[tid] = conn
            log.msg('Database Connected %s %s %s' %( self.dbapiName, self.connargs, self.connkw ))
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
        self.dispatcher.runInThread(callback, errback, self._runQuery, args, kw)

    def operation(self, callback, errback, *args, **kw):
        self.dispatcher.runInThread(callback, errback, self._runOperation, args, kw)

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
        apply(self.dispatcher.runInThread, (callback, errback, self._runInteraction, interaction) + args, kw)

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

    def loadObjectsFrom(self, tableName, keyColumns, data, rowClass, whereClause = "1 = 1", factoryMethod = defaultFactoryMethod):
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
                                userData,
                                employeeFactory,
                                EmployeeRow,
                                "employee_name like 'm%%'"
                                ).addCallback(gotEmployees)

        NOTE: this functionality is experimental. be careful.
        """
        return self.runInteraction(self._objectLoader, tableName, keyColumns, data, rowClass, whereClause, factoryMethod)

    def _objectLoader(self, transaction, tableName, keyColumns, data, rowClass, whereClause, factoryMethod):
        """worker method to load objects from a table.
        """
        # get the data from the table
        sql = """SELECT """
        first = 1
        for column, typeid, type in rowClass.dbColumns:
            if first:
                first = 0
            else:
                sql = sql + ","
            sql = sql + " %s" % column
        sql = sql + " FROM %s WHERE %s""" % (tableName, whereClause)
        transaction.execute(sql)
        rows = transaction.fetchall()
        # construct the objects
        results = []
        for r in rows:
            kw = row.makeKW(rowClass, r)
            resultObject = apply(factoryMethod, (rowClass, data, kw) )
            results.append(resultObject)

        #print "RESULTS", results
        return results




safe = row.safe
