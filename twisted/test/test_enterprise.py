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
from twisted.trial import unittest

import os
import random

from twisted.trial.util import deferredResult
from twisted.enterprise.row import RowObject
from twisted.enterprise.reflector import *
from twisted.enterprise.xmlreflector import XMLReflector
from twisted.enterprise.sqlreflector import SQLReflector
from twisted.enterprise.adbapi import ConnectionPool
from twisted.enterprise import util

try: import gadfly
except: gadfly = None

try: import sqlite
except: sqlite = None

try: from pyPgSQL import PgSQL
except: PgSQL = None

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

def randomizeRow(row, nullsOK=1):
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
        setattr(row, name, value)
        values[name] = value
    return values

def rowMatches(row, values):
    for name, type in row.rowColumns:
        if getattr(row, name) != values[name]:
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
        values = randomizeRow(row, self.nullsOK)

        # save it
        deferredResult(self.reflector.insertRow(row))
        row = None # drop the reference so it is no longer cached

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
            values = randomizeRow(row, self.nullsOK)
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

        # test update FIXME: make some changes to row
        deferredResult(self.reflector.updateRow(parent))

        # test bulk
        for i in range(0, self.count):
            row = TestRow()
            row.assignKeyAttr("key_string", "bulk%d"%i)
            row.col2 = 4
            row.another_column = "another"
            row.Column4 = "444"
            row.column_5_ = 1
            deferredResult(self.reflector.insertRow(row))
            row = None

        d = self.reflector.loadObjectsFrom("testTable")
        d.addCallback(self.gotData)
        deferredResult(d)

        assert len(self.data) == self.count + 1, "query did not get rows"

        for row in self.data:
            deferredResult(self.reflector.updateRow(row))

        for row in self.data:
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
    """

    DB_NAME = "twisted_test"
    DB_USER = 'twisted_test'
    DB_PASS = 'twisted_test'

    reflectorClass = SQLReflector

    def createReflector(self):
        self.startDB()
        self.dbpool = self.makePool()
        deferredResult(self.dbpool.runOperation(main_table_schema))
        deferredResult(self.dbpool.runOperation(child_table_schema))
        return self.reflectorClass(self.dbpool, [TestRow, ChildRow])

    def destroyReflector(self):
        deferredResult(self.dbpool.runOperation('DROP TABLE testTable'))
        deferredResult(self.dbpool.runOperation('DROP TABLE childTable'))
        self.dbpool.close()
        self.stopDB()

    def startDB(self): pass
    def stopDB(self): pass


class SinglePool(ConnectionPool):
    """A pool for just one connection at a time.
    Remove this when ConnectionPool is fixed.
    """

    def __init__(self, connection):
        self.connection = connection

    def connect(self):
        return self.connection

    def close(self):
        self.connection.close()
        del self.connection


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
        return SinglePool(gadfly.gadfly(self.DB_NAME, self.DB_DIR))


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
        return SinglePool(sqlite.connect(database=self.database))


class PostgresTestCase(SQLReflectorTestCase, unittest.TestCase):
    """Test cases for the SQL reflector using Postgres.
    """

    def makePool(self):
        return ConnectionPool('pyPgSQL.PgSQL', database=self.DB_NAME,
                              user=self.DB_USER, password=self.DB_PASS)


class QuotingTestCase(unittest.TestCase):

    def testQuoting(self):
        for value, typ, expected in [
            (12, "integer", "12"),
            ("foo'd", "text", "'foo''d'"),
            ("\x00abc\\s\xFF", "bytea", "'\\\\000abc\\\\\\\\s\\377'"),
            ]:
            self.assertEquals(util.quote(value, typ), expected)


if gadfly is None: GadflyTestCase.skip = 1
if sqlite is None: SQLiteTestCase.skip = 1

if PgSQL is None: PostgresTestCase.skip = 1
else:
    try:
        conn = PgSQL.connect(database=SQLReflectorTestCase.DB_NAME,
                             user=PostgresTestCase.DB_USER,
                             password=PostgresTestCase.DB_PASS)
        conn.close()
    except:
        PostgresTestCase.skip = 1
