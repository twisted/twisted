# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""Tests for twisted.enterprise reflectors."""

from twisted.trial import unittest

import os, random

from twisted.internet import reactor, interfaces, defer
from twisted.enterprise.row import RowObject
from twisted.enterprise.reflector import *
from twisted.enterprise.sqlreflector import SQLReflector
from twisted.enterprise import util
from twisted.test.test_adbapi import makeSQLTests

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

def randomizeRow(row, nulls_ok=True, trailing_spaces_ok=True):
    values = {}
    for name, type in row.rowColumns:
        if util.getKeyColumn(row, name):
            values[name] = getattr(row, name)
            continue
        elif nulls_ok and random.randint(0, 9) == 0:
            value = None # null
        elif type == 'int':
            value = random.randint(-10000, 10000)
        else:
            if random.randint(0, 9) == 0:
                value = ''
            else:
                value = ''.join(map(lambda i:chr(random.randrange(32,127)),
                                    xrange(random.randint(1, 64))))
            if not trailing_spaces_ok:
                value = value.rstrip()
        setattr(row, name, value)
        values[name] = value
    return values

def rowMatches(row, values):
    for name, type in row.rowColumns:
        if getattr(row, name) != values[name]:
            print ("Mismatch on column %s: |%s| (row) |%s| (values)" %
                   (name, getattr(row, name), values[name]))
            return False
    return True

class ReflectorTestBase:
    """Base class for testing reflectors."""

    if interfaces.IReactorThreads(reactor, None) is None:
        skip = "No thread support, no reflector tests"

    count = 100 # a parameter used for running iterative tests

    def wait(self, d, timeout=10.0):
        return unittest.wait(d, timeout=timeout)

    def randomizeRow(self, row):
        return randomizeRow(row, self.nulls_ok, self.trailing_spaces_ok)

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
        self.wait(self.reflector.insertRow(row))

        # now load it back in
        whereClause = [("key_string", EQUAL, "first")]
        d = self.reflector.loadObjectsFrom(tableName, whereClause=whereClause)
        d.addCallback(self.gotData)
        self.wait(d)

        # make sure it came back as what we saved
        self.failUnless(len(self.data) == 1, "no row")
        parent = self.data[0]
        self.failUnless(rowMatches(parent, values), "no match")

        # create some child rows
        inserts = []
        child_values = {}
        for i in range(0, self.num_iterations):
            row = ChildRow()
            row.assignKeyAttr("childId", i)
            values = self.randomizeRow(row)
            values['test_key'] = row.test_key = "first"
            child_values[i] = values
            inserts.append(self.reflector.insertRow(row))
            row = None
        self.wait(defer.gatherResults(inserts), timeout=self.num_iterations)
        del inserts

        d = self.reflector.loadObjectsFrom(childTableName, parentRow=parent)
        d.addCallback(self.gotData)
        self.wait(d)

        self.failUnless(len(self.data) == self.num_iterations,
                        "no rows on query")
        self.failUnless(len(parent.childRows) == self.num_iterations,
                        "did not load child rows: %d" % len(parent.childRows))
        for child in parent.childRows:
            self.failUnless(rowMatches(child, child_values[child.childId]),
                            "child %d does not match" % child.childId)

        # loading these objects a second time should not re-add them
        # to the parentRow.
        d = self.reflector.loadObjectsFrom(childTableName, parentRow=parent)
        d.addCallback(self.gotData)
        self.wait(d)

        self.failUnless(len(self.data) == self.num_iterations,
                        "no rows on query")
        self.failUnless(len(parent.childRows) == self.num_iterations,
                        "child rows added twice!: %d" % len(parent.childRows))

        # now change the parent
        values = self.randomizeRow(parent)
        self.wait(self.reflector.updateRow(parent))
        parent = None

        # now load it back in
        whereClause = [("key_string", EQUAL, "first")]
        d = self.reflector.loadObjectsFrom(tableName, whereClause=whereClause)
        d.addCallback(self.gotData)
        self.wait(d)

        # make sure it came back as what we saved
        self.failUnless(len(self.data) == 1, "no row")
        parent = self.data[0]
        self.failUnless(rowMatches(parent, values), "no match")

        # save parent
        test_values = {}
        test_values[parent.key_string] = values
        parent = None

        # save some more test rows
        for i in range(0, self.num_iterations):
            row = TestRow()
            row.assignKeyAttr("key_string", "bulk%d"%i)
            test_values[row.key_string] = self.randomizeRow(row)
            self.wait(self.reflector.insertRow(row))
            row = None

        # now load them all back in
        d = self.reflector.loadObjectsFrom("testTable")
        d.addCallback(self.gotData)
        self.wait(d, 100.0)

        # make sure they are the same
        self.failUnless(len(self.data) == self.num_iterations + 1,
                        "query did not get rows")
        for row in self.data:
            self.failUnless(rowMatches(row, test_values[row.key_string]),
                            "child %s does not match" % row.key_string)

        # now change them all
        for row in self.data:
            test_values[row.key_string] = self.randomizeRow(row)
            self.wait(self.reflector.updateRow(row))
        self.data = None

        # load'em back
        d = self.reflector.loadObjectsFrom("testTable")
        d.addCallback(self.gotData)
        self.wait(d)

        # make sure they are the same
        self.failUnless(len(self.data) == self.num_iterations + 1,
                        "query did not get rows")
        for row in self.data:
            self.failUnless(rowMatches(row, test_values[row.key_string]),
                            "child %s does not match" % row.key_string)

        # now delete them
        for row in self.data:
            self.wait(self.reflector.deleteRow(row))
        self.data = None

        # load'em back
        d = self.reflector.loadObjectsFrom("testTable")
        d.addCallback(self.gotData)
        self.wait(d)

        self.failUnless(len(self.data) == 0, "rows were not deleted")

        # create one row to work with
        row = TestRow()
        row.assignKeyAttr("key_string", "first")
        values = self.randomizeRow(row)

        # save it
        self.wait(self.reflector.insertRow(row))

        # delete it
        self.wait(self.reflector.deleteRow(row))

    def gotData(self, data):
        self.data = data

ReflectorTestBase.timeout = 30.0

class SQLReflectorTestBase(ReflectorTestBase):
    """Base class for the SQL reflector."""

    def createReflector(self):
        self.startDB()
        self.dbpool = self.makePool()
        self.dbpool.start()

        if self.can_clear:
            try:
                self.wait(self.dbpool.runOperation('DROP TABLE testTable'))
            except:
                pass

            try:
                self.wait(self.dbpool.runOperation('DROP TABLE childTable'))
            except:
                pass

        self.wait(self.dbpool.runOperation(main_table_schema))
        self.wait(self.dbpool.runOperation(child_table_schema))
        reflectorClass = self.escape_slashes and SQLReflector \
                         or NoSlashSQLReflector
        return reflectorClass(self.dbpool, [TestRow, ChildRow])

    def destroyReflector(self):
        self.wait(self.dbpool.runOperation('DROP TABLE testTable'))
        self.wait(self.dbpool.runOperation('DROP TABLE childTable'))
        self.dbpool.close()
        self.stopDB()

# GadflyReflectorTestCase SQLiteReflectorTestCase PyPgSQLReflectorTestCase
# PsycopgReflectorTestCase MySQLReflectorTestCase FirebirdReflectorTestCase
makeSQLTests(SQLReflectorTestBase, 'ReflectorTestCase', globals())

class NoSlashSQLReflector(SQLReflector):
    """An sql reflector that only escapes single quotes."""

    def escape_string(self, text):
        return text.replace("'", "''")
