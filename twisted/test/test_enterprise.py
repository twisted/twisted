# Twisted, the Framework of Your Internet
# Copyright (C) 2001-2002 Matthew W. Lefkowitz
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
#

"""Tests for twisted.enterprise."""

from twisted.trial import unittest

import os
import stat
import random
import tempfile

from twisted.enterprise.row import RowObject
from twisted.enterprise.reflector import *
from twisted.enterprise.xmlreflector import XMLReflector
from twisted.enterprise.sqlreflector import SQLReflector
from twisted.enterprise.adbapi import ConnectionPool
from twisted.enterprise import util
from twisted.internet import defer
from twisted.trial.util import deferredResult, deferredError
from twisted.python import log

try: import gadfly
except: gadfly = None

try: import sqlite
except: sqlite = None

try: from pyPgSQL import PgSQL
except: PgSQL = None

try: import MySQLdb
except: MySQLdb = None

try: import psycopg
except: psycopg = None

try: import kinterbasdb
except: kinterbasdb = None

tableName = "testTable"
childTableName = "childTable"

class TestRow(RowObject):
    rowColumns = [("key_string",      "varchar"),
                  ("col2",            "int"),
                  ("another_column",  "varchar"),
                  ("Column4",         "varchar"),
                  ("column_5_",       "int")]
    rowKeyColumns = [("key_string", "varchar")]
    rowTableName  = tableName

class ChildRow(RowObject):
    rowColumns    = [("childId",  "int"),
                     ("foo",      "varchar"),
                     ("test_key", "varchar"),
                     ("stuff",    "varchar"),
                     ("gogogo",   "int"),
                     ("data",     "varchar")]
    rowKeyColumns = [("childId", "int")]
    rowTableName  = childTableName
    rowForeignKeys = [(tableName,
                       [("test_key","varchar")],
                       [("key_string","varchar")],
                       None, 1)]

main_table_schema = """
CREATE TABLE testTable (
  key_string     varchar(64),
  col2           integer,
  another_column varchar(64),
  Column4        varchar(64),
  column_5_      integer
)
"""

child_table_schema = """
CREATE TABLE childTable (
  childId        integer,
  foo            varchar(64),
  test_key       varchar(64),
  stuff          varchar(64),
  gogogo         integer,
  data           varchar(64)
)
"""

simple_table_schema = """
CREATE TABLE simple (
  x integer
)
"""

def randomizeRow(row, nullsOK=1, trailingSpacesOK=1):
    values = {}
    for name, type in row.rowColumns:
        if util.getKeyColumn(row, name):
            values[name] = getattr(row, name)
            continue
        elif nullsOK and random.randint(0, 9) == 0:
            value = None # null
        elif type == 'int':
            value = random.randint(-10000, 10000)
        else:
            if random.randint(0, 9) == 0:
                value = ''
            else:
                value = ''.join(map(lambda i:chr(random.randrange(32,127)),
                                    xrange(random.randint(1, 64))))
            if not trailingSpacesOK:
                value = value.rstrip()
        setattr(row, name, value)
        values[name] = value
    return values

def rowMatches(row, values):
    for name, type in row.rowColumns:
        if getattr(row, name) != values[name]:
            print ("Mismatch on column %s: |%s| (row) |%s| (values)" %
                   (name, getattr(row, name), values[name]))
            return
    return 1

class ReflectorTestCase:
    """Base class for testing reflectors.

    Subclass and implement createReflector for the style and db you
    want to test. This may involve creating a new database, starting a
    server, etc. If createReflector returns None, the test is skipped.
    This allows subclasses to test for the presence of the database
    libraries and silently skip the test if they are not present.
    Implement destroyReflector if your database needs to be shutdown
    afterwards.
    """

    count = 100 # a parameter used for running iterative tests
    nullsOK = 1 # we can put nulls into the db
    trailingSpacesOK = 1 # we can put strings with trailing spaces into the db

    def randomizeRow(self, row):
        return randomizeRow(row, self.nullsOK, self.trailingSpacesOK)

    def setUp(self):
        self.reflector = self.createReflector()

    def tearDown(self):
        self.destroyReflector()

    def destroyReflector(self):
        pass

    def testReflector(self):
        # create one row to work with
        row = TestRow()
        row.assignKeyAttr("key_string", "first")
        values = self.randomizeRow(row)

        # save it
        deferredResult(self.reflector.insertRow(row))

        # now load it back in
        whereClause = [("key_string", EQUAL, "first")]
        d = self.reflector.loadObjectsFrom(tableName, whereClause=whereClause)
        d.addCallback(self.gotData)
        deferredResult(d)

        # make sure it came back as what we saved
        self.failUnless(len(self.data) == 1, "no row")
        parent = self.data[0]
        self.failUnless(rowMatches(parent, values), "no match")

        # create some child rows
        child_values = {}
        for i in range(0, self.count):
            row = ChildRow()
            row.assignKeyAttr("childId", i)
            values = self.randomizeRow(row)
            values['test_key'] = row.test_key = "first"
            child_values[i] = values
            deferredResult(self.reflector.insertRow(row))
            row = None

        d = self.reflector.loadObjectsFrom(childTableName, parentRow=parent)
        d.addCallback(self.gotData)
        deferredResult(d)

        self.failUnless(len(self.data) == self.count, "no rows on query")
        self.failUnless(len(parent.childRows) == self.count,
                        "did not load child rows: %d" % len(parent.childRows))
        for child in parent.childRows:
            self.failUnless(rowMatches(child, child_values[child.childId]),
                            "child %d does not match" % child.childId)

        # loading these objects a second time should not re-add them
        # to the parentRow.
        d = self.reflector.loadObjectsFrom(childTableName, parentRow=parent)
        d.addCallback(self.gotData)
        deferredResult(d)

        self.failUnless(len(self.data) == self.count, "no rows on query")
        self.failUnless(len(parent.childRows) == self.count,
                        "child rows added twice!: %d" % len(parent.childRows))

        # now change the parent
        values = self.randomizeRow(parent)
        deferredResult(self.reflector.updateRow(parent))
        parent = None

        # now load it back in
        whereClause = [("key_string", EQUAL, "first")]
        d = self.reflector.loadObjectsFrom(tableName, whereClause=whereClause)
        d.addCallback(self.gotData)
        deferredResult(d)

        # make sure it came back as what we saved
        self.failUnless(len(self.data) == 1, "no row")
        parent = self.data[0]
        self.failUnless(rowMatches(parent, values), "no match")

        # save parent
        test_values = {}
        test_values[parent.key_string] = values
        parent = None

        # save some more test rows
        for i in range(0, self.count):
            row = TestRow()
            row.assignKeyAttr("key_string", "bulk%d"%i)
            test_values[row.key_string] = self.randomizeRow(row)
            deferredResult(self.reflector.insertRow(row))
            row = None

        # now load them all back in
        d = self.reflector.loadObjectsFrom("testTable")
        d.addCallback(self.gotData)
        deferredResult(d)

        # make sure they are the same
        self.failUnless(len(self.data) == self.count + 1,
                        "query did not get rows")
        for row in self.data:
            self.failUnless(rowMatches(row, test_values[row.key_string]),
                            "child %s does not match" % row.key_string)

        # now change them all
        for row in self.data:
            test_values[row.key_string] = self.randomizeRow(row)
            deferredResult(self.reflector.updateRow(row))
        self.data = None

        # load'em back
        d = self.reflector.loadObjectsFrom("testTable")
        d.addCallback(self.gotData)
        deferredResult(d)

        # make sure they are the same
        self.failUnless(len(self.data) == self.count + 1,
                        "query did not get rows")
        for row in self.data:
            self.failUnless(rowMatches(row, test_values[row.key_string]),
                            "child %s does not match" % row.key_string)

        # now delete them
        for row in self.data:
            deferredResult(self.reflector.deleteRow(row))
        self.data = None

        # load'em back
        d = self.reflector.loadObjectsFrom("testTable")
        d.addCallback(self.gotData)
        deferredResult(d)

        self.failUnless(len(self.data) == 0, "rows were not deleted")

        # create one row to work with
        row = TestRow()
        row.assignKeyAttr("key_string", "first")
        values = self.randomizeRow(row)

        # save it
        deferredResult(self.reflector.insertRow(row))

        # delete it
        deferredResult(self.reflector.deleteRow(row))

    def gotData(self, data):
        self.data = data


class XMLReflectorTestCase(ReflectorTestCase, unittest.TestCase):
    """Test cases for the XML reflector.
    """

    count = 10 # xmlreflector is slow
    DB = "./xmlDB"

    def createReflector(self):
        return XMLReflector(self.DB, [TestRow, ChildRow])


class SQLReflectorTestCase(ReflectorTestCase):
    """Test cases for the SQL reflector.

    To enable this test for databases which use a central, system database,
    you must create a database named DB_NAME with a user DB_USER and password
    DB_PASS with full access rights to the database DB_NAME.
    """

    DB_NAME = "twisted_test"
    DB_USER = 'twisted_test'
    DB_PASS = 'twisted_test'

    can_rollback = 1
    test_failures = 1

    reflectorClass = SQLReflector

    def createReflector(self):
        self.startDB()
        self.dbpool = self.makePool()
        self.dbpool.start()
        deferredResult(self.dbpool.runOperation(main_table_schema))
        deferredResult(self.dbpool.runOperation(child_table_schema))
        deferredResult(self.dbpool.runOperation(simple_table_schema))
        return self.reflectorClass(self.dbpool, [TestRow, ChildRow])

    def destroyReflector(self):
        deferredResult(self.dbpool.runOperation('DROP TABLE testTable'))
        deferredResult(self.dbpool.runOperation('DROP TABLE childTable'))
        deferredResult(self.dbpool.runOperation('DROP TABLE simple'))
        self.dbpool.close()
        self.stopDB()

    def testPool(self):
        if self.test_failures:
            # make sure failures are raised correctly
            deferredError(self.dbpool.runQuery("select * from NOTABLE"))
            deferredError(self.dbpool.runOperation("deletexxx from NOTABLE"))
            deferredError(self.dbpool.runInteraction(self.bad_interaction))
            log.flushErrors()

        # verify simple table is empty
        sql = "select count(1) from simple"
        row = deferredResult(self.dbpool.runQuery(sql))
        self.failUnless(int(row[0][0]) == 0, "Interaction not rolled back")

        # add some rows to simple table (runOperation)
        for i in range(self.count):
            sql = "insert into simple(x) values(%d)" % i
            deferredResult(self.dbpool.runOperation(sql))

        # make sure they were added (runQuery)
        sql = "select x from simple order by x";
        rows = deferredResult(self.dbpool.runQuery(sql))
        self.failUnless(len(rows) == self.count, "Wrong number of rows")
        for i in range(self.count):
            self.failUnless(len(rows[i]) == 1, "Wrong size row")
            self.failUnless(rows[i][0] == i, "Values not returned.")

        # runInteraction
        self.assertEquals(deferredResult(self.dbpool.runInteraction(self.interaction)),
                          "done")

        # give the pool a workout
        ds = []
        for i in range(self.count):
            sql = "select x from simple where x = %d" % i
            ds.append(self.dbpool.runQuery(sql))
        dlist = defer.DeferredList(ds, fireOnOneErrback=1)
        result = deferredResult(dlist)
        for i in range(self.count):
            self.failUnless(result[i][1][0][0] == i, "Value not returned")

        # now delete everything
        ds = []
        for i in range(self.count):
            sql = "delete from simple where x = %d" % i
            ds.append(self.dbpool.runOperation(sql))
        dlist = defer.DeferredList(ds, fireOnOneErrback=1)
        deferredResult(dlist)

        # verify simple table is empty
        sql = "select count(1) from simple"
        row = deferredResult(self.dbpool.runQuery(sql))
        self.failUnless(int(row[0][0]) == 0, "Interaction not rolled back")

    def interaction(self, transaction):
        transaction.execute("select x from simple order by x")
        for i in range(self.count):
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

    def startDB(self): pass
    def stopDB(self): pass


class NoSlashSQLReflector(SQLReflector):
    def escape_string(self, text):
        return text.replace("'", "''")


class GadflyTestCase(SQLReflectorTestCase, unittest.TestCase):
    """Test cases for the SQL reflector using Gadfly.
    """

    count = 10 # gadfly is slow
    nullsOK = 0
    DB_DIR = "./gadflyDB"
    reflectorClass = NoSlashSQLReflector
    can_rollback = 0

    def startDB(self):
        if not os.path.exists(self.DB_DIR): os.mkdir(self.DB_DIR)
        conn = gadfly.gadfly()
        conn.startup(self.DB_NAME, self.DB_DIR)

        # gadfly seems to want us to create something to get the db going
        cursor = conn.cursor()
        cursor.execute("create table x (x integer)")
        conn.commit()
        conn.close()

    def makePool(self):
        return ConnectionPool('gadfly', self.DB_NAME, self.DB_DIR, cp_max=1)


class SQLiteTestCase(SQLReflectorTestCase, unittest.TestCase):
    """Test cases for the SQL reflector using SQLite.
    """

    DB_DIR = "./sqliteDB"
    reflectorClass = NoSlashSQLReflector

    def startDB(self):
        if not os.path.exists(self.DB_DIR): os.mkdir(self.DB_DIR)
        self.database = os.path.join(self.DB_DIR, self.DB_NAME)
        if os.path.exists(self.database): os.unlink(self.database)

    def makePool(self):
        return ConnectionPool('sqlite', database=self.database, cp_max=1)


class PostgresTestCase(SQLReflectorTestCase, unittest.TestCase):
    """Test cases for the SQL reflector using Postgres.
    """

    def makePool(self):
        return ConnectionPool('pyPgSQL.PgSQL', database=self.DB_NAME,
                              user=self.DB_USER, password=self.DB_PASS,
                              cp_min=0)

class PsycopgTestCase(SQLReflectorTestCase, unittest.TestCase):
    """Test cases for the SQL reflector using psycopg for Postgres.
    """

    def makePool(self):
        return ConnectionPool('psycopg', database=self.DB_NAME,
                              user=self.DB_USER, password=self.DB_PASS,
                              cp_min=0)


class MySQLTestCase(SQLReflectorTestCase, unittest.TestCase):
    """Test cases for the SQL reflector using MySQL.
    """

    trailingSpacesOK = 0
    can_rollback = 0

    def makePool(self):
        return ConnectionPool('MySQLdb', db=self.DB_NAME,
                              user=self.DB_USER, passwd=self.DB_PASS)


class FirebirdTestCase(SQLReflectorTestCase, unittest.TestCase):
    """Test cases for the SQL reflector using Firebird/Interbase."""

    count = 2 # CHANGEME
    test_failures = 0 # failure testing causes problems
    reflectorClass = NoSlashSQLReflector
    DB_DIR = tempfile.mktemp()
    DB_NAME = os.path.join(DB_DIR, SQLReflectorTestCase.DB_NAME)

    def startDB(self):
        os.chmod(self.DB_DIR, stat.S_IRWXU + stat.S_IRWXG + stat.S_IRWXO)
        sql = 'create database "%s" user "%s" password "%s"'
        sql %= (self.DB_NAME, self.DB_USER, self.DB_PASS);
        conn = kinterbasdb.create_database(sql)
        conn.close()
        os.chmod(self.DB_NAME, stat.S_IRWXU + stat.S_IRWXG + stat.S_IRWXO)

    def makePool(self):
        return ConnectionPool('kinterbasdb', database=self.DB_NAME,
                              host='localhost', user=self.DB_USER,
                              password=self.DB_PASS)

    def stopDB(self):
        conn = kinterbasdb.connect(database=self.DB_NAME,
                                   host='localhost', user=self.DB_USER,
                                   password=self.DB_PASS)
        conn.drop_database()
        conn.close()

class QuotingTestCase(unittest.TestCase):

    def testQuoting(self):
        for value, typ, expected in [
            (12, "integer", "12"),
            ("foo'd", "text", "'foo''d'"),
            ("\x00abc\\s\xFF", "bytea", "'\\\\000abc\\\\\\\\s\\377'"),
            ]:
            self.assertEquals(util.quote(value, typ), expected)


if gadfly is None: GadflyTestCase.skip = "gadfly module not available"
elif not getattr(gadfly, 'connect', None): gadfly.connect = gadfly.gadfly

if sqlite is None: SQLiteTestCase.skip = "sqlite module not available"

if PgSQL is None: PostgresTestCase.skip = "pyPgSQL module not available"
else:
    try:
        conn = PgSQL.connect(database=PostgresTestCase.DB_NAME,
                             user=PostgresTestCase.DB_USER,
                             password=PostgresTestCase.DB_PASS)
        conn.close()
    except Exception, e:
        PostgresTestCase.skip = "Connection to PgSQL server failed: " + str(e)

if psycopg is None: PsycopgTestCase.skip = "psycopg module not available"
else:
    try:
        conn = psycopg.connect(database=PsycopgTestCase.DB_NAME,
                               user=PsycopgTestCase.DB_USER,
                               password=PsycopgTestCase.DB_PASS)
        conn.close()
    except Exception, e:
        PsycopgTestCase.skip = "Connection to PostgreSQL using psycopg failed: " + str(e)

if MySQLdb is None: MySQLTestCase.skip = "MySQLdb module not available"
else:
    try:
        conn = MySQLdb.connect(db=MySQLTestCase.DB_NAME,
                               user=MySQLTestCase.DB_USER,
                               passwd=MySQLTestCase.DB_PASS)
        conn.close()
    except Exception, e:
        MySQLTestCase.skip = "Connection to MySQL server failed: " + str(e)

if kinterbasdb is None:
    FirebirdTestCase.skip = "kinterbasdb module not available"
else:
    try:
        testcase = FirebirdTestCase()
        testcase.startDB()
        testcase.stopDB()
    except Exception, e:
        FirebirdTestCase.skip = "Connection to Firebase server failed: " + str(e)
