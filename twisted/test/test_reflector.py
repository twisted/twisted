# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for twisted.enterprise reflectors.
"""

import random

from twisted.internet import reactor, interfaces, defer
from twisted.enterprise.row import RowObject
from twisted.enterprise.reflector import EQUAL
from twisted.enterprise.sqlreflector import SQLReflector
from twisted.enterprise import util
from twisted.test.test_adbapi import makeSQLTests
from twisted.trial.util import suppress as suppressWarning
from twisted.trial import unittest


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


rowObjectSuppression = suppressWarning(
    message="twisted.enterprise.row is deprecated since Twisted 8.0",
    category=DeprecationWarning)


reflectorSuppression = suppressWarning(
    message="twisted.enterprise.reflector is deprecated since Twisted 8.0",
    category=DeprecationWarning)


class ReflectorTestBase:
    """
    Base class for testing reflectors.

    @ivar reflector: The reflector created during setup.
    """

    if interfaces.IReactorThreads(reactor, None) is None:
        skip = "No thread support, no reflector tests"

    count = 100 # a parameter used for running iterative tests

    def randomizeRow(self, row):
        return randomizeRow(row, self.nulls_ok, self.trailing_spaces_ok)

    def extraSetUp(self):
        """
        Create and store a reference to a SQL reflector for use by the tests.
        """
        d = self.createReflector()
        d.addCallback(self._cbSetUp)
        return d

    def _cbSetUp(self, reflector):
        self.reflector = reflector

    def tearDown(self):
        return self.destroyReflector()

    def destroyReflector(self):
        pass

    def test_reflector(self):
        """
        Full featured tests of reflector.
        """
        # create one row to work with
        row = TestRow()
        row.assignKeyAttr("key_string", "first")
        values = self.randomizeRow(row)

        # save it
        d = self.reflector.insertRow(row)

        def _loadBack(_):
            # now load it back in
            whereClause = [("key_string", EQUAL, "first")]
            d = self.reflector.loadObjectsFrom(tableName,
                                               whereClause=whereClause)
            return d.addCallback(self.gotData)

        def _getParent(_):
            # make sure it came back as what we saved
            self.failUnless(len(self.data) == 1, "no row")
            parent = self.data[0]
            self.failUnless(rowMatches(parent, values), "no match")
            return parent

        d.addCallback(_loadBack)
        d.addCallback(_getParent)
        d.addCallback(self._cbTestReflector)
        return d
    test_reflector.suppress = [rowObjectSuppression, reflectorSuppression]

    def _cbTestReflector(self, parent):
        # create some child rows
        test_values = {}
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
        #del inserts
        d = defer.gatherResults(inserts)
        values = [None]

        def _loadObjects(_):
            d = self.reflector.loadObjectsFrom(childTableName, parentRow=parent)
            return d.addCallback(self.gotData)

        def _checkLoadObjects(_):
            self.failUnless(len(self.data) == self.num_iterations,
                            "no rows on query")
            self.failUnless(len(parent.childRows) == self.num_iterations,
                            "did not load child rows: %d" % len(parent.childRows))
            for child in parent.childRows:
                self.failUnless(rowMatches(child, child_values[child.childId]),
                                "child %d does not match" % child.childId)

        def _checkLoadObjects2(_):
            self.failUnless(len(self.data) == self.num_iterations,
                            "no rows on query")
            self.failUnless(len(parent.childRows) == self.num_iterations,
                            "child rows added twice!: %d" % len(parent.childRows))

        def _changeParent(_):
            # now change the parent
            values[0] = self.randomizeRow(parent)
            return self.reflector.updateRow(parent)

        def _loadBack(_):
            # now load it back in
            whereClause = [("key_string", EQUAL, "first")]
            d = self.reflector.loadObjectsFrom(tableName, whereClause=whereClause)
            return d.addCallback(self.gotData)

        def _checkLoadBack(_):
            # make sure it came back as what we saved
            self.failUnless(len(self.data) == 1, "no row")
            parent = self.data[0]
            self.failUnless(rowMatches(parent, values[0]), "no match")
            # save parent
            test_values[parent.key_string] = values[0]
            parent = None

        def _saveMoreTestRows(_):
            # save some more test rows
            ds = []
            for i in range(0, self.num_iterations):
                row = TestRow()
                row.assignKeyAttr("key_string", "bulk%d"%i)
                test_values[row.key_string] = self.randomizeRow(row)
                ds.append(self.reflector.insertRow(row))
            return defer.gatherResults(ds)

        def _loadRowsBack(_):
            # now load them all back in
            d = self.reflector.loadObjectsFrom("testTable")
            return d.addCallback(self.gotData)

        def _checkRowsBack(_):
            # make sure they are the same
            self.failUnless(len(self.data) == self.num_iterations + 1,
                            "query did not get rows")
            for row in self.data:
                self.failUnless(rowMatches(row, test_values[row.key_string]),
                                "child %s does not match" % row.key_string)

        def _changeRows(_):
            # now change them all
            ds = []
            for row in self.data:
                test_values[row.key_string] = self.randomizeRow(row)
                ds.append(self.reflector.updateRow(row))
            d = defer.gatherResults(ds)
            return d.addCallback(_cbChangeRows)

        def _cbChangeRows(_):
            self.data = None

        def _deleteRows(_):
            # now delete them
            ds = []
            for row in self.data:
                ds.append(self.reflector.deleteRow(row))
            d = defer.gatherResults(ds)
            return d.addCallback(_cbChangeRows)

        def _checkRowsDeleted(_):
            self.failUnless(len(self.data) == 0, "rows were not deleted")

        d.addCallback(_loadObjects)
        d.addCallback(_checkLoadObjects)
        d.addCallback(_loadObjects)
        d.addCallback(_checkLoadObjects2)
        d.addCallback(_changeParent)
        d.addCallback(_loadBack)
        d.addCallback(_checkLoadBack)
        d.addCallback(_saveMoreTestRows)
        d.addCallback(_loadRowsBack)
        d.addCallback(_checkRowsBack)
        d.addCallback(_changeRows)
        d.addCallback(_loadRowsBack)
        d.addCallback(_checkRowsBack)
        d.addCallback(_deleteRows)
        d.addCallback(_loadRowsBack)
        d.addCallback(_checkRowsDeleted)
        return d


    def test_saveAndDelete(self):
        """
        Create a row and then try to delete it.
        """
        # create one row to work with
        row = TestRow()
        row.assignKeyAttr("key_string", "first")
        values = self.randomizeRow(row)
        # save it
        d = self.reflector.insertRow(row)
        def _deleteRow(_):
            # delete it
            return self.reflector.deleteRow(row)
        d.addCallback(_deleteRow)
        return d
    test_saveAndDelete.suppress = [rowObjectSuppression, reflectorSuppression]


    def gotData(self, data):
        self.data = data


ReflectorTestBase.timeout = 30.0


class SQLReflectorTestBase(ReflectorTestBase):
    """
    Base class for the SQL reflector.
    """

    def createReflector(self):
        self.startDB()
        self.dbpool = self.makePool()
        self.dbpool.start()

        if self.can_clear:
            d = self.dbpool.runOperation('DROP TABLE testTable')
            d.addCallback(lambda _:
                          self.dbpool.runOperation('DROP TABLE childTable'))
            d.addErrback(lambda _: None)
        else:
            d = defer.succeed(None)

        d.addCallback(lambda _: self.dbpool.runOperation(main_table_schema))
        d.addCallback(lambda _: self.dbpool.runOperation(child_table_schema))
        reflectorClass = self.escape_slashes and SQLReflector \
                         or NoSlashSQLReflector
        d.addCallback(lambda _:
                      reflectorClass(self.dbpool, [TestRow, ChildRow]))
        return d

    def destroyReflector(self):
        d = self.dbpool.runOperation('DROP TABLE testTable')
        d.addCallback(lambda _:
                      self.dbpool.runOperation('DROP TABLE childTable'))
        def close(_):
            self.dbpool.close()
            self.stopDB()
        d.addCallback(close)
        return d


class DeprecationTestCase(unittest.TestCase):
    """
    Test various deprecations of twisted.enterprise.
    """

    def test_rowDeprecation(self):
        """
        Test deprecation of L{RowObject}.
        """
        def wrapper():
            return TestRow()
        self.assertWarns(DeprecationWarning,
            "twisted.enterprise.row is deprecated since Twisted 8.0",
            __file__,
            wrapper)

    def test_reflectorDeprecation(self):
        """
        Test deprecation of L{SQLReflector}.
        """
        def wrapper():
            return SQLReflector(None, ())
        from twisted.enterprise import sqlreflector
        self.assertWarns(DeprecationWarning,
            "twisted.enterprise.reflector is deprecated since Twisted 8.0",
            sqlreflector.__file__,
            wrapper)


# GadflyReflectorTestCase SQLiteReflectorTestCase PyPgSQLReflectorTestCase
# PsycopgReflectorTestCase MySQLReflectorTestCase FirebirdReflectorTestCase
makeSQLTests(SQLReflectorTestBase, 'ReflectorTestCase', globals())


class NoSlashSQLReflector(SQLReflector):
    """
    An sql reflector that only escapes single quotes.
    """

    def escape_string(self, text):
        return text.replace("'", "''")

