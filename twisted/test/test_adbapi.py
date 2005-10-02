# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""Tests for twisted.enterprise.adbapi."""

from twisted.trial import unittest

import os, stat, tempfile

from twisted.enterprise.adbapi import ConnectionPool, ConnectionLost
from twisted.internet import reactor, defer, interfaces
from twisted.python import log

simple_table_schema = """
CREATE TABLE simple (
  x integer
)
"""

class ADBAPITestBase:
    """Test the asynchronous DB-API code."""

    openfun_called = {}

    if interfaces.IReactorThreads(reactor, None) is None:
        skip = "ADB-API requires threads, no way to test without them"

    def wait(self, d, timeout=10.0):
        return unittest.wait(d, timeout=timeout)

    def setUp(self):
        self.startDB()
        self.dbpool = self.makePool(cp_openfun=self.openfun)
        self.dbpool.start()

    def tearDown(self):
        self.wait(self.dbpool.runOperation('DROP TABLE simple'))
        self.dbpool.close()
        self.stopDB()

    def openfun(self, conn):
        self.openfun_called[conn] = True

    def checkOpenfunCalled(self, conn=None):
        if not conn:
            self.failUnless(self.openfun_called)
        else:
            self.failUnless(self.openfun_called.has_key(conn))

    def testPool(self):
        self.wait(self.dbpool.runOperation(simple_table_schema))

        if self.test_failures:
            # make sure failures are raised correctly
            try:
                self.wait(self.dbpool.runQuery("select * from NOTABLE"))
                self.fail('no exception')
            except:
                pass

            try:
                self.wait(self.dbpool.runOperation("deletexxx from NOTABLE"))
                self.fail('no exception')
            except:
                pass

            try:
                self.wait(self.dbpool.runInteraction(self.bad_interaction))
                self.fail('no exception')
            except:
                pass
                
            try:
                self.wait(self.dbpool.runWithConnection(self.bad_withConnection))
                self.fail('no exception')
            except:
                pass
            log.flushErrors()

        # verify simple table is empty
        sql = "select count(1) from simple"
        row = self.wait(self.dbpool.runQuery(sql))
        self.failUnless(int(row[0][0]) == 0, "Interaction not rolled back")

        self.checkOpenfunCalled()

        inserts = []
        # add some rows to simple table (runOperation)
        for i in range(self.num_iterations):
            sql = "insert into simple(x) values(%d)" % i
            inserts.append(self.dbpool.runOperation(sql))
        self.wait(defer.gatherResults(inserts), timeout=self.num_iterations)
        del inserts

        # make sure they were added (runQuery)
        sql = "select x from simple order by x";
        rows = self.wait(self.dbpool.runQuery(sql))
        self.failUnless(len(rows) == self.num_iterations,
                        "Wrong number of rows")
        for i in range(self.num_iterations):
            self.failUnless(len(rows[i]) == 1, "Wrong size row")
            self.failUnless(rows[i][0] == i, "Values not returned.")

        # runInteraction
        res = self.wait(self.dbpool.runInteraction(self.interaction))
        self.assertEquals(res, "done")

        # withConnection
        res = self.wait(self.dbpool.runWithConnection(self.withConnection))
        self.assertEquals(res, "done")

        # Test a withConnection cannot be closed
        res = self.wait(self.dbpool.runWithConnection(self.close_withConnection))

        # give the pool a workout
        ds = []
        for i in range(self.num_iterations):
            sql = "select x from simple where x = %d" % i
            ds.append(self.dbpool.runQuery(sql))
        dlist = defer.DeferredList(ds, fireOnOneErrback=True)
        result = self.wait(dlist, timeout=self.num_iterations / 5.0)
        for i in range(self.num_iterations):
            self.failUnless(result[i][1][0][0] == i, "Value not returned")

        # now delete everything
        ds = []
        for i in range(self.num_iterations):
            sql = "delete from simple where x = %d" % i
            ds.append(self.dbpool.runOperation(sql))
        dlist = defer.DeferredList(ds, fireOnOneErrback=True)
        self.wait(dlist, timeout=self.num_iterations / 5.0)

        # verify simple table is empty
        sql = "select count(1) from simple"
        row = self.wait(self.dbpool.runQuery(sql))
        self.failUnless(int(row[0][0]) == 0,
                        "Didn't successfully delete table contents")

        self.checkConnect()
    
    def checkConnect(self):
        """Check the connect/disconnect synchronous calls."""
        conn = self.dbpool.connect()
        self.checkOpenfunCalled(conn)
        curs = conn.cursor()
        curs.execute("insert into simple(x) values(1)")
        curs.execute("select x from simple")
        res = curs.fetchall()
        self.failUnlessEqual(len(res), 1)
        self.failUnlessEqual(len(res[0]), 1)
        self.failUnlessEqual(res[0][0], 1)
        curs.execute("delete from simple")
        curs.execute("select x from simple")
        self.failUnlessEqual(len(curs.fetchall()), 0)
        curs.close()
        self.dbpool.disconnect(conn)

    def interaction(self, transaction):
        transaction.execute("select x from simple order by x")
        for i in range(self.num_iterations):
            row = transaction.fetchone()
            self.failUnless(len(row) == 1, "Wrong size row")
            self.failUnless(row[0] == i, "Value not returned.")
        # should test this, but gadfly throws an exception instead
        #self.failUnless(transaction.fetchone() is None, "Too many rows")
        return "done"

    def bad_interaction(self, transaction):
        if self.can_rollback:
            transaction.execute("insert into simple(x) values(0)")

        transaction.execute("select * from NOTABLE")

    def withConnection(self, conn):
        curs = conn.cursor()
        try:
            curs.execute("select x from simple order by x")
            for i in range(self.num_iterations):
                row = curs.fetchone()
                self.failUnless(len(row) == 1, "Wrong size row")
                self.failUnless(row[0] == i, "Value not returned.")
            # should test this, but gadfly throws an exception instead
            #self.failUnless(transaction.fetchone() is None, "Too many rows")
        finally:
            curs.close()
        return "done"
        
    def close_withConnection(self, conn):
        conn.close()
        
    def bad_withConnection(self, conn):
        curs = conn.cursor()
        try:
            curs.execute("select * from NOTABLE")
        finally:
            curs.close()
        

ADBAPITestBase.timeout = 30.0

class ReconnectTestBase:
    """Test the asynchronous DB-API code with reconnect."""

    if interfaces.IReactorThreads(reactor, None) is None:
        skip = "ADB-API requires threads, no way to test without them"

    def wait(self, d, timeout=10.0):
        return unittest.wait(d, timeout=timeout)

    def setUp(self):
        if self.good_sql is None:
            raise unittest.SkipTest('no good sql for reconnect test')
        self.startDB()
        self.dbpool = self.makePool(cp_max=1, cp_reconnect=True,
                                    cp_good_sql=self.good_sql)
        self.dbpool.start()
        self.wait(self.dbpool.runOperation(simple_table_schema))

    def tearDown(self):
        self.wait(self.dbpool.runOperation('DROP TABLE simple'))
        self.dbpool.close()
        self.stopDB()

    def testPool(self):
        sql = "select count(1) from simple"
        row = self.wait(self.dbpool.runQuery(sql))
        self.failUnless(int(row[0][0]) == 0, "Table not empty")

        # reach in and close the connection manually
        self.dbpool.connections.values()[0].close()

        if not self.early_reconnect:
            try:
                self.wait(self.dbpool.runQuery(sql))
                self.fail('no exception')
            except ConnectionLost:
                pass
            except:
                self.fail('not connection lost')

        row = self.wait(self.dbpool.runQuery(sql))
        self.failUnless(int(row[0][0]) == 0, "Table not empty")

        sql = "select * from NOTABLE" # bad sql
        try:
            self.wait(self.dbpool.runQuery(sql))
            self.fail('no exception')
        except ConnectionLost:
            self.fail('connection lost exception')
        except:
            pass

class DBTestConnector:
    """A class which knows how to test for the presence of
    and establish a connection to a relational database.

    To enable test cases  which use a central, system database,
    you must create a database named DB_NAME with a user DB_USER
    and password DB_PASS with full access rights to database DB_NAME.
    """

    TEST_PREFIX = None # used for creating new test cases

    DB_NAME = "twisted_test"
    DB_USER = 'twisted_test'
    DB_PASS = 'twisted_test'

    DB_DIR = None # directory for database storage

    nulls_ok = True # nulls supported
    trailing_spaces_ok = True # trailing spaces in strings preserved
    can_rollback = True # rollback supported
    test_failures = True # test bad sql?
    escape_slashes = True # escape \ in sql?
    good_sql = ConnectionPool.good_sql
    early_reconnect = True # cursor() will fail on closed connection
    can_clear = True # can try to clear out tables when starting
    needs_dbdir = False # if a temporary directory is needed for the db

    num_iterations = 50 # number of iterations for test loops
                        # (lower this for slow db's)

    def setUpClass(self):
        if self.needs_dbdir:
            self.DB_DIR = tempfile.mktemp()
            os.mkdir(self.DB_DIR)

        if not self.can_connect():
            raise unittest.SkipTest, '%s: Cannot access db' % self.TEST_PREFIX

    def can_connect(self):
        """Return true if this database is present on the system
        and can be used in a test."""
        raise NotImplementedError()

    def startDB(self):
        """Take any steps needed to bring database up."""
        pass

    def stopDB(self):
        """Bring database down, if needed."""
        pass

    def makePool(self, **newkw):
        """Create a connection pool with additional keyword arguments."""
        args, kw = self.getPoolArgs()
        kw = kw.copy()
        kw.update(newkw)
        return ConnectionPool(*args, **kw)

    def getPoolArgs(self):
        """Return a tuple (args, kw) of list and keyword arguments
        that need to be passed to ConnectionPool to create a connection
        to this database."""
        raise NotImplementedError()

class GadflyConnector(DBTestConnector):
    TEST_PREFIX = 'Gadfly'

    nulls_ok = False
    can_rollback = False
    escape_slashes = False
    good_sql = 'select * from simple where 1=0'
    needs_dbdir = True

    num_iterations = 1 # slow

    def can_connect(self):
        try: import gadfly
        except: return False
        if not getattr(gadfly, 'connect', None):
            gadfly.connect = gadfly.gadfly
        return True

    def startDB(self):
        import gadfly
        conn = gadfly.gadfly()
        conn.startup(self.DB_NAME, self.DB_DIR)

        # gadfly seems to want us to create something to get the db going
        cursor = conn.cursor()
        cursor.execute("create table x (x integer)")
        conn.commit()
        conn.close()

    def getPoolArgs(self):
        args = ('gadfly', self.DB_NAME, self.DB_DIR)
        kw = {'cp_max': 1}
        return args, kw

class SQLiteConnector(DBTestConnector):
    TEST_PREFIX = 'SQLite'

    escape_slashes = False
    needs_dbdir = True

    num_iterations = 1 # slow

    def can_connect(self):
        try: import sqlite
        except: return False
        return True

    def startDB(self):
        self.database = os.path.join(self.DB_DIR, self.DB_NAME)
        if os.path.exists(self.database):
            os.unlink(self.database)

    def getPoolArgs(self):
        args = ('sqlite',)
        kw = {'database': self.database, 'cp_max': 1}
        return args, kw

class PyPgSQLConnector(DBTestConnector):
    TEST_PREFIX = "PyPgSQL"

    def can_connect(self):
        try: from pyPgSQL import PgSQL
        except: return False
        try:
            conn = PgSQL.connect(database=self.DB_NAME, user=self.DB_USER,
                                 password=self.DB_PASS)
            conn.close()
            return True
        except:
            return False

    def getPoolArgs(self):
        args = ('pyPgSQL.PgSQL',)
        kw = {'database': self.DB_NAME, 'user': self.DB_USER,
              'password': self.DB_PASS, 'cp_min': 0}
        return args, kw

class PsycopgConnector(DBTestConnector):
    TEST_PREFIX = 'Psycopg'

    def can_connect(self):
        try: import psycopg
        except: return False
        try:
            conn = psycopg.connect(database=self.DB_NAME, user=self.DB_USER,
                                   password=self.DB_PASS)
            conn.close()
            return True
        except:
            return False

    def getPoolArgs(self):
        args = ('psycopg',)
        kw = {'database': self.DB_NAME, 'user': self.DB_USER,
              'password': self.DB_PASS, 'cp_min': 0}
        return args, kw

class MySQLConnector(DBTestConnector):
    TEST_PREFIX = 'MySQL'

    trailing_spaces_ok = False
    can_rollback = False
    early_reconnect = False

    def can_connect(self):
        try: import MySQLdb
        except: return False
        try:
            conn = MySQLdb.connect(db=self.DB_NAME, user=self.DB_USER,
                                   passwd=self.DB_PASS)
            conn.close()
            return True
        except:
            return False

    def getPoolArgs(self):
        args = ('MySQLdb',)
        kw = {'db': self.DB_NAME, 'user': self.DB_USER, 'passwd': self.DB_PASS}
        return args, kw

class FirebirdConnector(DBTestConnector):
    TEST_PREFIX = 'Firebird'

    test_failures = False # failure testing causes problems
    escape_slashes = False
    good_sql = None # firebird doesn't handle failed sql well
    can_clear = False # firebird is not so good
    needs_dbdir = True

    num_iterations = 5 # slow

    def can_connect(self):
        try: import kinterbasdb
        except: return False
        try:
            self.startDB()
            self.stopDB()
            return True
        except:
            return False

    def startDB(self):
        import kinterbasdb
        self.DB_NAME = os.path.join(self.DB_DIR, DBTestConnector.DB_NAME)
        os.chmod(self.DB_DIR, stat.S_IRWXU + stat.S_IRWXG + stat.S_IRWXO)
        sql = 'create database "%s" user "%s" password "%s"'
        sql %= (self.DB_NAME, self.DB_USER, self.DB_PASS);
        conn = kinterbasdb.create_database(sql)
        conn.close()

    def getPoolArgs(self):
        args = ('kinterbasdb',)
        kw = {'database': self.DB_NAME, 'host': '127.0.0.1',
              'user': self.DB_USER, 'password': self.DB_PASS}
        return args, kw

    def stopDB(self):
        import kinterbasdb
        conn = kinterbasdb.connect(database=self.DB_NAME,
                                   host='127.0.0.1', user=self.DB_USER,
                                   password=self.DB_PASS)
        conn.drop_database()

def makeSQLTests(base, suffix, globals):
    """Make a test case for every db connector which can connect.

    @param base: Base class for test case. Additional base classes
                 will be a DBConnector subclass and unittest.TestCase
    @param suffix: A suffix used to create test case names. Prefixes
                   are defined in the DBConnector subclasses.
    """
    connectors = [GadflyConnector, SQLiteConnector, PyPgSQLConnector,
                  PsycopgConnector, MySQLConnector, FirebirdConnector]
    for connclass in connectors:
        name = connclass.TEST_PREFIX + suffix
        import new
        klass = new.classobj(name, (connclass, base, unittest.TestCase), {})
        globals[name] = klass

# GadflyADBAPITestCase SQLiteADBAPITestCase PyPgSQLADBAPITestCase
# PsycopgADBAPITestCase MySQLADBAPITestCase FirebirdADBAPITestCase
makeSQLTests(ADBAPITestBase, 'ADBAPITestCase', globals())

# GadflyReconnectTestCase SQLiteReconnectTestCase PyPgSQLReconnectTestCase
# PsycopgReconnectTestCase MySQLReconnectTestCase FirebirdReconnectTestCase
makeSQLTests(ReconnectTestBase, 'ReconnectTestCase', globals())
