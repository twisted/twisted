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

from twisted.trial.util import deferredResult
from twisted.enterprise.row import RowObject
from twisted.enterprise.xmlreflector import XMLReflector
from twisted.enterprise.sqlreflector import SQLReflector
from twisted.enterprise.adbapi import ConnectionPool
from twisted.enterprise import util

try: import gadfly
except: pass

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

    def setUp(self):
        self.reflector = self.createReflector()

    def tearDown(self):
        if self.reflector: self.destroyReflector()

    def destroyReflector(self):
        pass

    def testReflector(self):
        if not self.reflector: return

        # create one row to work with
        newRow = TestRow()
        newRow.assignKeyAttr("key_string", "first")
        newRow.col2 = 1
        newRow.another_column = "another"
        newRow.Column4 = "foo"
        newRow.column_5_ = 444
        self.data = None

        deferredResult(self.reflector.insertRow(newRow))

        # create some child rows
        for i in range(0, 10):
            row = ChildRow()
            row.assignKeyAttr("childId", i)
            row.foo = "foo foo "
            row.test_key = "first"
            row.stuff = "d"
            row.gogogo = 101
            row.data = "some data"
            deferredResult(self.reflector.insertRow(row))
            row = None

        d = self.reflector.loadObjectsFrom(childTableName,
                                           parentRow=newRow)
        d.addCallback(self.gotData)
        deferredResult(d)

        self.failUnless(len(self.data) > 0, "no rows on query")
        self.failUnless(len(newRow.childRows) == 10,
                        "did not load child rows: %d" % len(newRow.childRows))

        # loading these objects a second time should not re-add them
        # to the parentRow.
        d = self.reflector.loadObjectsFrom(childTableName,
                                           parentRow=newRow)
        d.addCallback(self.gotData)
        deferredResult(d)

        self.failUnless(len(self.data) > 0, "no rows on query")
        self.failUnless(len(newRow.childRows) == 10,
                        "child rows added twice!: %d" % len(newRow.childRows))

        # test update FIXME: make some changes to row
        deferredResult(self.reflector.updateRow(newRow))

        # test bulk
        num = 10
        for i in range(0, num):
            newRow = TestRow()
            newRow.assignKeyAttr("key_string", "bulk%d"%i)
            newRow.col2 = 4
            newRow.another_column = "another"
            newRow.Column4 = "444"
            newRow.column_5_ = 1
            deferredResult(self.reflector.insertRow(newRow))
            newRow = None

        d = self.reflector.loadObjectsFrom("testTable")
        d.addCallback(self.gotData)
        deferredResult(d)

        assert len(self.data) == num + 1, "query did not get rows"

        for row in self.data:
            deferredResult(self.reflector.updateRow(row))

        for row in self.data:
            deferredResult(self.reflector.deleteRow(row))

    def gotData(self, data):
        self.data = data


class XMLReflectorTestCase(ReflectorTestCase, unittest.TestCase):
    """Test cases for the XML reflector.
    """

    DB = "./xmlDB"

    def createReflector(self):
        return XMLReflector(self.DB, [TestRow, ChildRow])


class SQLReflectorTestCase(ReflectorTestCase):
    """Test cases for the SQL reflector.
    """

    def createReflector(self):
        if not self.installed(): return None
        self.startDB()
        self.dbpool = self.makePool()
        deferredResult(self.dbpool.runOperation(main_table_schema))
        deferredResult(self.dbpool.runOperation(child_table_schema))
        return SQLReflector(self.dbpool, [TestRow, ChildRow])

    def destroyReflector(self):
        self.dbpool.close()
        self.stopDB()

    def stopDB(self):
        pass


class GadflyPool(ConnectionPool):
    """A pool for gadfly -- just one connection at a time, please!
    Remove this when ConnectionPool is fixed.
    """

    def __init__(self, dbname, dbdir):
        self.connection = gadfly.gadfly(dbname, dbdir)

    def connect(self):
        return self.connection

    def close(self):
        self.connection.close()
        del self.connection


class GadflyReflectorTestCase(SQLReflectorTestCase, unittest.TestCase):
    """Test cases for the SQL reflector using Gadfly.
    """

    DB_NAME = "gadfly"
    DB_DIR = "./gadflyDB"

    def installed(self):
        try: gadfly
        except: return 0
        return 1

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
        return GadflyPool(self.DB_NAME, self.DB_DIR)


class QuotingTestCase(unittest.TestCase):

    def testQuoting(self):
        for value, typ, expected in [
            (12, "integer", "12"),
            ("foo'd", "text", "'foo''d'"),
            ("\x00abc\\s\xFF", "bytea", "'\\\\000abc\\\\\\\\s\\377'"),
            ]:
            self.assertEquals(util.quote(value, typ), expected)
