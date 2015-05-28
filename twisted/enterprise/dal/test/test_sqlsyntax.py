# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twext.enterprise.dal.syntax}
"""

from twisted.internet.defer import succeed
from twisted.trial.unittest import TestCase, SkipTest

from twext.enterprise.dal import syntax
try:
    from twext.enterprise.dal.parseschema import addSQLToSchema
except ImportError as e:
    def addSQLToSchema(*args, **kwargs):
        raise SkipTest("addSQLToSchema is not available: {0}".format(e))
from twext.enterprise.dal.syntax import (
    Select, Insert, Update, Delete, Lock, SQLFragment,
    TableMismatch, Parameter, Max, Min, Len, NotEnoughValues,
    Savepoint, RollbackToSavepoint, ReleaseSavepoint, SavepointAction,
    Union, Intersect, Except, SetExpression, DALError,
    ResultAliasSyntax, Count, QueryGenerator, ALL_COLUMNS,
    DatabaseLock, DatabaseUnlock, Not, Coalesce)
from twext.enterprise.dal.syntax import FixedPlaceholder, NumericPlaceholder
from twext.enterprise.dal.syntax import Function
from twext.enterprise.dal.syntax import SchemaSyntax
from twext.enterprise.dal.test.test_parseschema import SchemaTestHelper
from twext.enterprise.ienterprise import (
    POSTGRES_DIALECT, ORACLE_DIALECT, SQLITE_DIALECT
)
from twext.enterprise.test.test_adbapi2 import ConnectionPoolHelper
from twext.enterprise.test.test_adbapi2 import NetworkedPoolHelper
from twext.enterprise.test.test_adbapi2 import resultOf, AssertResultHelper
from twext.enterprise.dal.syntax import Tuple
from twext.enterprise.dal.syntax import Constant



class _FakeTransaction(object):
    """
    An L{IAsyncTransaction} that provides the relevant metadata for SQL
    generation.
    """

    def __init__(self, paramstyle):
        self.paramstyle = "qmark"



class FakeCXOracleModule(object):
    NUMBER = "the NUMBER type"
    STRING = "a string type (for varchars)"
    NCLOB = "the NCLOB type. (for text)"
    TIMESTAMP = "for timestamps!"



class CatchSQL(object):
    """
    L{IAsyncTransaction} emulator that records the SQL executed on it.
    """
    counter = 0

    def __init__(self, dialect=SQLITE_DIALECT, paramstyle="numeric"):
        self.execed = []
        self.pendingResults = []
        self.dialect = SQLITE_DIALECT
        self.paramstyle = "numeric"


    def nextResult(self, result):
        """
        Make it so that the next result from L{execSQL} will be the argument.
        """
        self.pendingResults.append(result)


    def execSQL(self, sql, args, rozrc):
        """
        Implement L{IAsyncTransaction} by recording C{sql} and C{args} in
        C{self.execed}, and return a L{Deferred} firing either an integer or a
        value pre-supplied by L{CatchSQL.nextResult}.
        """
        self.execed.append([sql, args])
        self.counter += 1
        if self.pendingResults:
            result = self.pendingResults.pop(0)
        else:
            result = self.counter
        return succeed(result)



class NullTestingOracleTxn(object):
    """
    Fake transaction for testing oracle NULL behavior.
    """

    dialect = ORACLE_DIALECT
    paramstyle = "numeric"

    def execSQL(self, text, params, exc):
        return succeed([[None, None]])



EXAMPLE_SCHEMA = """
create sequence A_SEQ;
create table FOO (BAR integer, BAZ varchar(255));
create table BOZ (QUX integer, QUUX integer);
create table OTHER (BAR integer,
                    FOO_BAR integer not null);
create table TEXTUAL (MYTEXT varchar(255));
create table LEVELS (ACCESS integer,
                     USERNAME varchar(255));
create table NULLCHECK (ASTRING varchar(255) not null,
                        ANUMBER integer);
"""



class ExampleSchemaHelper(SchemaTestHelper):
    """
    setUp implementor.
    """

    def setUp(self):
        self.schema = SchemaSyntax(self.schemaFromString(EXAMPLE_SCHEMA))



class GenerationTests(ExampleSchemaHelper, TestCase, AssertResultHelper):
    """
    Tests for syntactic helpers to generate SQL queries.
    """

    def test_simplestSelect(self):
        """
        L{Select} generates a C{select} statement, by default, asking for all
        rows in a table.
        """
        self.assertEquals(
            Select(From=self.schema.FOO).toSQL(),
            SQLFragment("select * from FOO", [])
        )


    def test_tableSyntaxFromSchemaSyntaxCompare(self):
        """
        One L{TableSyntax} is equivalent to another wrapping the same table;
        one wrapping a different table is different.
        """
        self.assertEquals(self.schema.FOO, self.schema.FOO)
        self.assertNotEquals(self.schema.FOO, self.schema.BOZ)


    def test_simpleWhereClause(self):
        """
        L{Select} generates a C{select} statement with a C{where} clause
        containing an expression.
        """
        self.assertEquals(
            Select(
                From=self.schema.FOO,
                Where=self.schema.FOO.BAR == 1
            ).toSQL(),
            SQLFragment("select * from FOO where BAR = ?", [1])
        )


    def test_alternateMetadata(self):
        """
        L{Select} generates a C{select} statement with the specified
        placeholder syntax when explicitly given L{ConnectionMetadata} which
        specifies a placeholder.
        """
        self.assertEquals(
            Select(
                From=self.schema.FOO,
                Where=self.schema.FOO.BAR == 1
            ).toSQL(QueryGenerator(POSTGRES_DIALECT, FixedPlaceholder("$$"))),
            SQLFragment("select * from FOO where BAR = $$", [1])
        )


    def test_columnComparison(self):
        """
        L{Select} generates a C{select} statement which compares columns.
        """
        self.assertEquals(
            Select(
                From=self.schema.FOO,
                Where=self.schema.FOO.BAR == self.schema.FOO.BAZ
            ).toSQL(),
            SQLFragment("select * from FOO where BAR = BAZ", [])
        )


    def test_comparisonTestErrorPrevention(self):
        """
        The comparison object between SQL expressions raises an exception when
        compared for a truth value, so that code will not accidentally operate
        on SQL objects and get a truth value.

        (Note that this has a caveat, in test_columnsAsDictKeys and
        test_columnEqualityTruth.)
        """
        def sampleComparison():
            if self.schema.FOO.BAR > self.schema.FOO.BAZ:
                return "comparison should not succeed"
        self.assertRaises(DALError, sampleComparison)


    def test_compareWithNULL(self):
        """
        Comparing a column with None results in the generation of an C{is null}
        or C{is not null} SQL statement.
        """
        self.assertEquals(
            Select(
                From=self.schema.FOO,
                Where=self.schema.FOO.BAR == None
            ).toSQL(),
            SQLFragment("select * from FOO where BAR is null", [])
        )
        self.assertEquals(
            Select(
                From=self.schema.FOO,
                Where=self.schema.FOO.BAR != None
            ).toSQL(),
            SQLFragment("select * from FOO where BAR is not null", [])
        )


    def test_compareWithEmptyStringOracleSpecialCase(self):
        """
        Oracle considers the empty string to be a C{NULL} value, so comparisons
        with the empty string should be C{is NULL} comparisons.
        """
        # Sanity check: let's make sure that the non-oracle case looks normal.
        self.assertEquals(
            Select(
                From=self.schema.FOO,
                Where=self.schema.FOO.BAR == ""
            ).toSQL(),
            SQLFragment("select * from FOO where BAR = ?", [""])
        )
        self.assertEquals(
            Select(
                From=self.schema.FOO,
                Where=self.schema.FOO.BAR != ""
            ).toSQL(),
            SQLFragment("select * from FOO where BAR != ?", [""])
        )
        self.assertEquals(
            Select(
                From=self.schema.FOO,
                Where=self.schema.FOO.BAR == ""
            ).toSQL(QueryGenerator(ORACLE_DIALECT, NumericPlaceholder())),
            SQLFragment("select * from FOO where BAR is null", [])
        )
        self.assertEquals(
            Select(
                From=self.schema.FOO,
                Where=self.schema.FOO.BAR != ""
            ).toSQL(QueryGenerator(ORACLE_DIALECT, NumericPlaceholder())),
            SQLFragment("select * from FOO where BAR is not null", [])
        )


    def test_compoundWhere(self):
        """
        L{Select.And} and L{Select.Or} will return compound columns.
        """
        self.assertEquals(
            Select(
                From=self.schema.FOO,
                Where=(self.schema.FOO.BAR < 2).Or(self.schema.FOO.BAR > 5)
            ).toSQL(),
            SQLFragment("select * from FOO where BAR < ? or BAR > ?", [2, 5])
        )


    def test_orderBy(self):
        """
        L{Select}'s L{OrderBy} parameter generates an C{order by} clause for a
        C{select} statement.
        """
        self.assertEquals(
            Select(
                From=self.schema.FOO,
                OrderBy=self.schema.FOO.BAR
            ).toSQL(),
            SQLFragment("select * from FOO order by BAR")
        )


    def test_orderByOrder(self):
        """
        L{Select}'s L{Ascending} parameter specifies an ascending/descending
        order for query results with an OrderBy clause.
        """
        self.assertEquals(
            Select(
                From=self.schema.FOO,
                OrderBy=self.schema.FOO.BAR,
                Ascending=False
            ).toSQL(),
            SQLFragment("select * from FOO order by BAR desc")
        )

        self.assertEquals(
            Select(
                From=self.schema.FOO,
                OrderBy=self.schema.FOO.BAR,
                Ascending=True
            ).toSQL(),
            SQLFragment("select * from FOO order by BAR asc")
        )

        self.assertEquals(
            Select(
                From=self.schema.FOO,
                OrderBy=[self.schema.FOO.BAR, self.schema.FOO.BAZ],
                Ascending=True
            ).toSQL(),
            SQLFragment("select * from FOO order by BAR, BAZ asc")
        )


    def test_orderByParens(self):
        """
        L{Select}'s L{OrderBy} paraneter, if specified as a L{Tuple}, generates
        an SQL expression I{without} parentheses, since the standard format
        does not allow an arbitrary sort expression but rather a list of
        columns.
        """
        self.assertEquals(
            Select(
                From=self.schema.FOO,
                OrderBy=Tuple([self.schema.FOO.BAR, self.schema.FOO.BAZ])
            ).toSQL(),
            SQLFragment("select * from FOO order by BAR, BAZ")
        )


    def test_forUpdate(self):
        """
        L{Select}'s L{ForUpdate} parameter generates a C{for update} clause at
        the end of the query.
        """
        self.assertEquals(
            Select(From=self.schema.FOO, ForUpdate=True).toSQL(),
            SQLFragment("select * from FOO for update")
        )


    def test_groupBy(self):
        """
        L{Select}'s L{GroupBy} parameter generates a C{group by} clause for a
        C{select} statement.
        """
        self.assertEquals(
            Select(
                From=self.schema.FOO,
                GroupBy=self.schema.FOO.BAR
            ).toSQL(),
            SQLFragment("select * from FOO group by BAR")
        )


    def test_groupByMulti(self):
        """
        L{Select}'s L{GroupBy} parameter can accept multiple columns in a list.
        """
        self.assertEquals(
            Select(
                From=self.schema.FOO,
                GroupBy=[self.schema.FOO.BAR, self.schema.FOO.BAZ]
            ).toSQL(),
            SQLFragment("select * from FOO group by BAR, BAZ")
        )


    def test_joinClause(self):
        """
        A table's C{.join()} method returns a join statement in a C{SELECT}.
        """
        self.assertEquals(
            Select(
                From=self.schema.FOO.join(
                    self.schema.BOZ,
                    self.schema.FOO.BAR == self.schema.BOZ.QUX
                )
            ).toSQL(),
            SQLFragment("select * from FOO join BOZ on BAR = QUX", [])
        )


    def test_commaJoin(self):
        """
        A join with no clause specified will generate a cross join. This variant
        uses a "," between table names rather than "cross join".
        """
        self.assertEquals(
            Select(From=self.schema.FOO.join(self.schema.BOZ, type=",")).toSQL(),
            SQLFragment("select * from FOO, BOZ")
        )


    def test_crossJoin(self):
        """
        A join with no clause specified will generate a cross join.  (This is
        AN explicit synonym for an implicit join: i.e. C{select * from FOO,
        BAR}.)
        """
        self.assertEquals(
            Select(From=self.schema.FOO.join(self.schema.BOZ)).toSQL(),
            SQLFragment("select * from FOO cross join BOZ")
        )


    def test_joinJoin(self):
        """
        L{Join.join} will result in a multi-table join.
        """
        self.assertEquals(
            Select(
                [self.schema.FOO.BAR, self.schema.BOZ.QUX],
                From=self.schema.FOO
                .join(self.schema.BOZ)
                .join(self.schema.OTHER)
            ).toSQL(),
            SQLFragment(
                "select FOO.BAR, QUX from FOO cross join BOZ cross join OTHER"
            )
        )


    def test_multiJoin(self):
        """
        L{Join.join} has the same signature as L{TableSyntax.join} and supports
        the same C{on} and C{type} arguments.
        """

        self.assertEquals(
            Select(
                [self.schema.FOO.BAR],
                From=self.schema.FOO.join(
                    self.schema.BOZ
                ).join(
                    self.schema.OTHER,
                    self.schema.OTHER.BAR == self.schema.FOO.BAR,
                    "left outer"
                )
            ).toSQL(),
            SQLFragment(
                "select FOO.BAR from FOO cross join BOZ left outer join OTHER "
                "on OTHER.BAR = FOO.BAR"
            )
        )


    def test_tableAliasing(self):
        """
        Tables may be given aliases, in order to facilitate self-joins.
        """
        sfoo = self.schema.FOO
        sfoo2 = sfoo.alias()
        self.assertEqual(
            Select(From=self.schema.FOO.join(sfoo2)).toSQL(),
            SQLFragment("select * from FOO cross join FOO alias1")
        )


    def test_columnsOfAliasedTable(self):
        """
        The columns of aliased tables will always be prefixed with their alias
        in the generated SQL.
        """
        sfoo = self.schema.FOO
        sfoo2 = sfoo.alias()
        self.assertEquals(
            Select([sfoo2.BAR], From=sfoo2).toSQL(),
            SQLFragment("select alias1.BAR from FOO alias1")
        )


    def test_multipleTableAliases(self):
        """
        When multiple aliases are used for the same table, they will be unique
        within the query.
        """
        foo = self.schema.FOO
        fooPrime = foo.alias()
        fooPrimePrime = foo.alias()
        self.assertEquals(
            Select(
                [fooPrime.BAR, fooPrimePrime.BAR],
                From=fooPrime.join(fooPrimePrime)
            ).toSQL(),
            SQLFragment(
                "select alias1.BAR, alias2.BAR "
                "from FOO alias1 cross join FOO alias2"
            )
        )


    def test_columnSelection(self):
        """
        If a column is specified by the argument to L{Select}, those will be
        output by the SQL statement rather than the all-columns wildcard.
        """
        self.assertEquals(
            Select([self.schema.FOO.BAR], From=self.schema.FOO).toSQL(),
            SQLFragment("select BAR from FOO")
        )


    def test_tableIteration(self):
        """
        Iterating a L{TableSyntax} iterates its columns, in the order that they
        are defined.
        """
        self.assertEquals(
            list(self.schema.FOO),
            [self.schema.FOO.BAR, self.schema.FOO.BAZ]
        )


    def test_noColumn(self):
        """
        Accessing an attribute that is not a defined column on a L{TableSyntax}
        raises an L{AttributeError}.
        """
        self.assertRaises(AttributeError, lambda: self.schema.FOO.NOT_A_COLUMN)


    def test_columnAliases(self):
        """
        When attributes are set on a L{TableSyntax}, they will be remembered as
        column aliases, and their alias names may be retrieved via the
        L{TableSyntax.columnAliases} method.
        """
        self.assertEquals(self.schema.FOO.columnAliases(), {})
        self.schema.FOO.ALIAS = self.schema.FOO.BAR

        # you comparing ColumnSyntax object results in a ColumnComparison,
        # which you can't test for truth.
        fixedForEquality = dict([
            (k, v.model) for k, v in self.schema.FOO.columnAliases().items()
        ])

        self.assertEquals(
            fixedForEquality,
            {"ALIAS": self.schema.FOO.BAR.model}
        )
        self.assertIdentical(
            self.schema.FOO.ALIAS.model,
            self.schema.FOO.BAR.model
        )


    def test_multiColumnSelection(self):
        """
        If multiple columns are specified by the argument to L{Select}, those
        will be output by the SQL statement rather than the all-columns
        wildcard.
        """
        self.assertEquals(
            Select(
                [self.schema.FOO.BAZ, self.schema.FOO.BAR],
                From=self.schema.FOO
            ).toSQL(),
            SQLFragment("select BAZ, BAR from FOO")
        )


    def test_joinColumnSelection(self):
        """
        If multiple columns are specified by the argument to L{Select} that
        uses a L{TableSyntax.join}, those will be output by the SQL statement.
        """
        self.assertEquals(
            Select(
                [self.schema.FOO.BAZ, self.schema.BOZ.QUX],
                From=self.schema.FOO.join(
                    self.schema.BOZ,
                    self.schema.FOO.BAR == self.schema.BOZ.QUX
                )
            ).toSQL(),
            SQLFragment("select BAZ, QUX from FOO join BOZ on BAR = QUX")
        )


    def test_tableMismatch(self):
        """
        When a column in the C{columns} argument does not match the table from
        the C{From} argument, L{Select} raises a L{TableMismatch}.
        """
        self.assertRaises(
            TableMismatch,
            Select, [self.schema.BOZ.QUX], From=self.schema.FOO
        )


    def test_qualifyNames(self):
        """
        When two columns in the C{from} clause requested from different tables
        have the same name, the emitted SQL should explicitly disambiguate
        them.
        """
        self.assertEquals(
            Select(
                [self.schema.FOO.BAR, self.schema.OTHER.BAR],
                From=self.schema.FOO.join(
                    self.schema.OTHER,
                    self.schema.OTHER.FOO_BAR == self.schema.FOO.BAR
                )
            ).toSQL(),
            SQLFragment(
                "select FOO.BAR, OTHER.BAR from FOO "
                "join OTHER on FOO_BAR = FOO.BAR"
            )
        )


    def test_bindParameters(self):
        """
        L{SQLFragment.bind} returns a copy of that L{SQLFragment} with the
        L{Parameter} objects in its parameter list replaced with the keyword
        arguments to C{bind}.
        """
        self.assertEquals(
            Select(
                From=self.schema.FOO,
                Where=(self.schema.FOO.BAR > Parameter("testing"))
                .And(self.schema.FOO.BAZ < 7)
            ).toSQL().bind(testing=173),
            SQLFragment(
                "select * from FOO where BAR > ? and BAZ < ?", [173, 7]
            )
        )


    def test_rightHandSideExpression(self):
        """
        Arbitrary expressions may be used as the right-hand side of a
        comparison operation.
        """
        self.assertEquals(
            Select(
                From=self.schema.FOO,
                Where=self.schema.FOO.BAR > (self.schema.FOO.BAZ + 3)
            ).toSQL(),
            SQLFragment("select * from FOO where BAR > (BAZ + ?)", [3])
        )


    def test_setSelects(self):
        """
        L{SetExpression} produces set operation on selects.
        """
        # Simple UNION
        self.assertEquals(
            Select(
                From=self.schema.FOO,
                Where=(self.schema.FOO.BAR == 1),
                SetExpression=Union(
                    Select(
                        From=self.schema.FOO,
                        Where=(self.schema.FOO.BAR == 2),
                    ),
                ),
            ).toSQL(QueryGenerator(POSTGRES_DIALECT, FixedPlaceholder("?"))),
            SQLFragment(
                "(select * from FOO where BAR = ?) "
                "UNION (select * from FOO where BAR = ?)", [1, 2]
            )
        )

        # Simple INTERSECT ALL
        self.assertEquals(
            Select(
                From=self.schema.FOO,
                Where=(self.schema.FOO.BAR == 1),
                SetExpression=Intersect(
                    Select(
                        From=self.schema.FOO,
                        Where=(self.schema.FOO.BAR == 2),
                    ),
                    optype=SetExpression.OPTYPE_ALL
                ),
            ).toSQL(QueryGenerator(POSTGRES_DIALECT, FixedPlaceholder("?"))),
            SQLFragment(
                "(select * from FOO where BAR = ?) "
                "INTERSECT ALL (select * from FOO where BAR = ?)", [1, 2]
            )
        )

        # Multiple EXCEPTs, not nested, Postgres dialect
        self.assertEquals(
            Select(
                From=self.schema.FOO,
                SetExpression=Except(
                    (
                        Select(
                            From=self.schema.FOO,
                            Where=(self.schema.FOO.BAR == 2),
                        ),
                        Select(
                            From=self.schema.FOO,
                            Where=(self.schema.FOO.BAR == 3),
                        ),
                    ),
                    optype=SetExpression.OPTYPE_DISTINCT,
                ),
            ).toSQL(QueryGenerator(POSTGRES_DIALECT, FixedPlaceholder("?"))),
            SQLFragment(
                "(select * from FOO) "
                "EXCEPT DISTINCT (select * from FOO where BAR = ?) "
                "EXCEPT DISTINCT (select * from FOO where BAR = ?)", [2, 3]
            )
        )

        # Nested EXCEPTs, Oracle dialect
        self.assertEquals(
            Select(
                From=self.schema.FOO,
                SetExpression=Except(
                    Select(
                        From=self.schema.FOO,
                        Where=(self.schema.FOO.BAR == 2),
                        SetExpression=Except(
                            Select(
                                From=self.schema.FOO,
                                Where=(self.schema.FOO.BAR == 3),
                            ),
                        ),
                    ),
                ),
            ).toSQL(QueryGenerator(ORACLE_DIALECT, FixedPlaceholder("?"))),
            SQLFragment(
                "(select * from FOO) MINUS ((select * from FOO where BAR = ?) "
                "MINUS (select * from FOO where BAR = ?))", [2, 3]
            )
        )

        # UNION with order by
        self.assertEquals(
            Select(
                From=self.schema.FOO,
                Where=(self.schema.FOO.BAR == 1),
                SetExpression=Union(
                    Select(
                        From=self.schema.FOO,
                        Where=(self.schema.FOO.BAR == 2),
                    ),
                ),
                OrderBy=self.schema.FOO.BAR,
            ).toSQL(QueryGenerator(POSTGRES_DIALECT, FixedPlaceholder("?"))),
            SQLFragment(
                "(select * from FOO where BAR = ?) "
                "UNION (select * from FOO where BAR = ?) order by BAR", [1, 2]
            )
        )


    def test_simpleSubSelects(self):
        """
        L{Max}C{(column)} produces an object in the C{columns} clause that
        renders the C{max} aggregate in SQL.
        """
        self.assertEquals(
            Select(
                [Max(self.schema.BOZ.QUX)],
                From=(Select([self.schema.BOZ.QUX], From=self.schema.BOZ))
            ).toSQL(),
            SQLFragment("select max(QUX) from (select QUX from BOZ) genid_1")
        )

        self.assertEquals(
            Select(
                [Count(self.schema.BOZ.QUX)],
                From=(Select([self.schema.BOZ.QUX], From=self.schema.BOZ))
            ).toSQL(),
            SQLFragment("select count(QUX) from (select QUX from BOZ) genid_1")
        )

        self.assertEquals(
            Select(
                [Max(self.schema.BOZ.QUX)],
                From=(Select(
                    [self.schema.BOZ.QUX],
                    From=self.schema.BOZ,
                    As="alias_BAR"
                )),
            ).toSQL(),
            SQLFragment("select max(QUX) from (select QUX from BOZ) alias_BAR")
        )


    def test_setSubSelects(self):
        """
        L{SetExpression} in a C{From} sub-select.
        """
        # Simple UNION
        self.assertEquals(
            Select(
                [Max(self.schema.FOO.BAR)],
                From=Select(
                    [self.schema.FOO.BAR],
                    From=self.schema.FOO,
                    Where=(self.schema.FOO.BAR == 1),
                    SetExpression=Union(
                        Select(
                            [self.schema.FOO.BAR],
                            From=self.schema.FOO,
                            Where=(self.schema.FOO.BAR == 2),
                        ),
                    ),
                )
            ).toSQL(),
            SQLFragment(
                "select max(BAR) from ((select BAR from FOO where BAR = ?) "
                "UNION (select BAR from FOO where BAR = ?)) genid_1", [1, 2]
            )
        )


    def test_selectColumnAliases(self):
        """
        L{Select} works with aliased columns.
        """
        self.assertEquals(
            Select(
                [ResultAliasSyntax(self.schema.BOZ.QUX, "BOZ_QUX")],
                From=self.schema.BOZ
            ).toSQL(),
            SQLFragment("select QUX BOZ_QUX from BOZ")
        )

        self.assertEquals(
            Select(
                [ResultAliasSyntax(Max(self.schema.BOZ.QUX))],
                From=self.schema.BOZ
            ).toSQL(),
            SQLFragment("select max(QUX) genid_1 from BOZ")
        )

        alias = ResultAliasSyntax(Max(self.schema.BOZ.QUX))
        self.assertEquals(
            Select(
                [alias.columnReference()],
                From=Select([alias], From=self.schema.BOZ)
            ).toSQL(),
            SQLFragment(
                "select genid_1 from "
                "(select max(QUX) genid_1 from BOZ) genid_2"
            )
        )

        alias = ResultAliasSyntax(Len(self.schema.BOZ.QUX))
        self.assertEquals(
            Select(
                [alias.columnReference()],
                From=Select([alias], From=self.schema.BOZ)
            ).toSQL(),
            SQLFragment(
                "select genid_1 from "
                "(select character_length(QUX) genid_1 from BOZ) genid_2"
            )
        )


    def test_inSubSelect(self):
        """
        L{ColumnSyntax.In} returns a sub-expression using the SQL C{in} syntax
        with a sub-select.
        """
        wherein = self.schema.FOO.BAR.In(
            Select([self.schema.BOZ.QUX], From=self.schema.BOZ)
        )
        self.assertEquals(
            Select(From=self.schema.FOO, Where=wherein).toSQL(),
            SQLFragment(
                "select * from FOO where BAR in (select QUX from BOZ)"
            )
        )


    def test_inParameter(self):
        """
        L{ColumnSyntax.In} returns a sub-expression using the SQL C{in} syntax
        with parameter list.
        """
        # One item with IN only
        items = set(("A",))
        self.assertEquals(
            Select(
                From=self.schema.FOO,
                Where=self.schema.FOO.BAR.In(
                    Parameter("names", len(items))
                )
            ).toSQL().bind(names=items),
            SQLFragment("select * from FOO where BAR in (?)", ["A"])
        )

        # Two items with IN only
        items = set(("A", "B"))
        test = Select(
            From=self.schema.FOO,
            Where=self.schema.FOO.BAR.In(
                Parameter("names", len(items))
            )
        ).toSQL().bind(names=items)
        test.parameters.sort()
        self.assertEquals(
            test,
            SQLFragment(
                "select * from FOO where BAR in (?, ?)", ["A", "B"]
            )
        )

        # Two items with preceding AND
        test = Select(
            From=self.schema.FOO,
            Where=(
                (
                    self.schema.FOO.BAZ == Parameter("P1")
                ).And(
                    self.schema.FOO.BAR.In(Parameter("names", len(items)))
                )
            )
        ).toSQL().bind(P1="P1", names=items)
        test.parameters = [test.parameters[0], ] + sorted(test.parameters[1:])
        self.assertEquals(
            test,
            SQLFragment(
                "select * from FOO where BAZ = ? and BAR in (?, ?)",
                ["P1", "A", "B"]
            ),
        )

        # Two items with following AND
        test = Select(
            From=self.schema.FOO,
            Where=(
                (
                    self.schema.FOO.BAR.In(Parameter("names", len(items)))
                ).And(
                    self.schema.FOO.BAZ == Parameter("P2")
                )
            )
        ).toSQL().bind(P2="P2", names=items)
        test.parameters = sorted(test.parameters[:-1]) + [test.parameters[-1], ]
        self.assertEquals(
            test,
            SQLFragment(
                "select * from FOO where BAR in (?, ?) and BAZ = ?",
                ["A", "B", "P2"]
            ),
        )

        # Two items with preceding OR and following AND
        test = Select(
            From=self.schema.FOO,
            Where=((
                self.schema.FOO.BAZ == Parameter("P1")
            ).Or(
                self.schema.FOO.BAR.In(Parameter("names", len(items))).And(
                    self.schema.FOO.BAZ == Parameter("P2")
                )
            ))
        ).toSQL().bind(P1="P1", P2="P2", names=items)
        test.parameters = [test.parameters[0], ] + sorted(test.parameters[1:-1]) + [test.parameters[-1], ]
        self.assertEquals(
            test,
            SQLFragment(
                "select * from FOO where BAZ = ? or BAR in (?, ?) and BAZ = ?",
                ["P1", "A", "B", "P2"]
            ),
        )

        # Check various error situations

        # No count not allowed
        self.assertRaises(DALError, self.schema.FOO.BAR.In, Parameter("names"))

        # count=0 not allowed
        self.assertRaises(DALError, Parameter, "names", 0)

        # Mismatched count and len(items)
        self.assertRaises(
            DALError,
            Select(
                From=self.schema.FOO,
                Where=self.schema.FOO.BAR.In(Parameter("names", len(items)))
            ).toSQL().bind,
            names=["a", "b", "c"]
        )


    def test_inIterable(self):
        """
        L{ColumnSyntax.In} returns a sub-expression using the SQL C{in} syntax
        with parameter list.
        """
        # One item with IN only
        items = set(("A",))
        for items in (set(items), list(items), tuple(items),):
            self.assertEquals(
                Select(
                    From=self.schema.FOO,
                    Where=self.schema.FOO.BAR.In(items),
                ).toSQL().bind(),
                SQLFragment("select * from FOO where BAR in (?)", ["A"])
            )

        # Two items with IN only
        items = ("A", "B")
        for items in (set(items), list(items), tuple(items),):
            test = Select(
                From=self.schema.FOO,
                Where=self.schema.FOO.BAR.In(items),
            ).toSQL().bind(names=items)
            test.parameters.sort()
            self.assertEquals(
                test,
                SQLFragment(
                    "select * from FOO where BAR in (?, ?)", ["A", "B"]
                )
            )

            # Two items with preceding AND
            test = Select(
                From=self.schema.FOO,
                Where=(
                    (
                        self.schema.FOO.BAZ == Parameter("P1")
                    ).And(
                        self.schema.FOO.BAR.In(items)
                    )
                )
            ).toSQL().bind(P1="P1")
            test.parameters = [test.parameters[0], ] + sorted(test.parameters[1:])
            self.assertEquals(
                test,
                SQLFragment(
                    "select * from FOO where BAZ = ? and BAR in (?, ?)",
                    ["P1", "A", "B"]
                ),
            )

            # Two items with following AND
            test = Select(
                From=self.schema.FOO,
                Where=(
                    (
                        self.schema.FOO.BAR.In(items)
                    ).And(
                        self.schema.FOO.BAZ == Parameter("P2")
                    )
                )
            ).toSQL().bind(P2="P2")
            test.parameters = sorted(test.parameters[:-1]) + [test.parameters[-1], ]
            self.assertEquals(
                test,
                SQLFragment(
                    "select * from FOO where BAR in (?, ?) and BAZ = ?",
                    ["A", "B", "P2"]
                ),
            )

            # Two items with preceding OR and following AND
            test = Select(
                From=self.schema.FOO,
                Where=((
                    self.schema.FOO.BAZ == Parameter("P1")
                ).Or(
                    self.schema.FOO.BAR.In(items).And(
                        self.schema.FOO.BAZ == Parameter("P2")
                    )
                ))
            ).toSQL().bind(P1="P1", P2="P2")
            test.parameters = [test.parameters[0], ] + sorted(test.parameters[1:-1]) + [test.parameters[-1], ]
            self.assertEquals(
                test,
                SQLFragment(
                    "select * from FOO where BAZ = ? or BAR in (?, ?) and BAZ = ?",
                    ["P1", "A", "B", "P2"]
                ),
            )


    def test_max(self):
        """
        L{Max}C{(column)} produces an object in the C{columns} clause that
        renders the C{max} aggregate in SQL.
        """
        self.assertEquals(
            Select([Max(self.schema.BOZ.QUX)], From=self.schema.BOZ).toSQL(),
            SQLFragment("select max(QUX) from BOZ")
        )


    def test_min(self):
        """
        L{Min}C{(column)} produces an object in the C{columns} clause that
        renders the C{min} aggregate in SQL.
        """
        self.assertEquals(
            Select([Min(self.schema.BOZ.QUX)], From=self.schema.BOZ).toSQL(),
            SQLFragment("select min(QUX) from BOZ")
        )


    def test_coalesce(self):
        """
        L{Coalesce}C{(column)} produces an object in the C{columns} clause that
        renders the C{coalesce} conditional in SQL.
        """
        self.assertEquals(
            Select(
                [self.schema.BOZ.QUX],
                From=self.schema.BOZ,
                Where=Coalesce(self.schema.BOZ.QUX, self.schema.BOZ.QUUX) == 1
            ).toSQL(),
            SQLFragment("select QUX from BOZ where coalesce(QUX, QUUX) = ?", [1])
        )


    def test_countAllCoumns(self):
        """
        L{Count}C{(ALL_COLUMNS)} produces an object in the C{columns} clause
        that renders the C{count} in SQL.
        """
        self.assertEquals(
            Select([Count(ALL_COLUMNS)], From=self.schema.BOZ).toSQL(),
            SQLFragment("select count(*) from BOZ")
        )


    def test_aggregateComparison(self):
        """
        L{Max}C{(column) > constant} produces an object in the C{columns}
        clause that renders a comparison to the C{max} aggregate in SQL.
        """
        self.assertEquals(
            Select(
                [Max(self.schema.BOZ.QUX) + 12],
                From=self.schema.BOZ
            ).toSQL(),
            SQLFragment("select max(QUX) + ? from BOZ", [12])
        )


    def test_multiColumnExpression(self):
        """
        Multiple columns may be provided in an expression in the C{columns}
        portion of a C{Select()} statement.  All arithmetic operators are
        supported.
        """
        self.assertEquals(
            Select(
                [((self.schema.FOO.BAR + self.schema.FOO.BAZ) / 3) * 7],
                From=self.schema.FOO
            ).toSQL(),
            SQLFragment("select ((BAR + BAZ) / ?) * ? from FOO", [3, 7])
        )


    def test_len(self):
        """
        Test for the L{Len} function for determining character length of a
        column.  (Note that this should be updated to use different techniques
        as necessary in different databases.)
        """
        self.assertEquals(
            Select(
                [Len(self.schema.TEXTUAL.MYTEXT)],
                From=self.schema.TEXTUAL
            ).toSQL(),
            SQLFragment("select character_length(MYTEXT) from TEXTUAL")
        )


    def test_startswith(self):
        """
        Test for the string starts with comparison.
        (Note that this should be updated to use different techniques
        as necessary in different databases.)
        """
        self.assertEquals(
            Select(
                [self.schema.TEXTUAL.MYTEXT],
                From=self.schema.TEXTUAL,
                Where=self.schema.TEXTUAL.MYTEXT.StartsWith("test"),
            ).toSQL(),
            SQLFragment(
                "select MYTEXT from TEXTUAL where MYTEXT like (? || ?)",
                ["test", "%"]
            )
        )


    def test_endswith(self):
        """
        Test for the string starts with comparison.
        (Note that this should be updated to use different techniques
        as necessary in different databases.)
        """
        self.assertEquals(
            Select(
                [self.schema.TEXTUAL.MYTEXT],
                From=self.schema.TEXTUAL,
                Where=self.schema.TEXTUAL.MYTEXT.EndsWith("test"),
            ).toSQL(),
            SQLFragment(
                "select MYTEXT from TEXTUAL where MYTEXT like (? || ?)",
                ["%", "test"]
            )
        )


    def test_contains(self):
        """
        Test for the string starts with comparison.
        (Note that this should be updated to use different techniques
        as necessary in different databases.)
        """
        self.assertEquals(
            Select(
                [self.schema.TEXTUAL.MYTEXT],
                From=self.schema.TEXTUAL,
                Where=self.schema.TEXTUAL.MYTEXT.Contains("test"),
            ).toSQL(),
            SQLFragment(
                "select MYTEXT from TEXTUAL where MYTEXT like (? || (? || ?))",
                ["%", "test", "%"]
            )
        )


    def test_not(self):
        """
        Test for the string starts with comparison.
        (Note that this should be updated to use different techniques
        as necessary in different databases.)
        """
        self.assertEquals(
            Select([
                self.schema.TEXTUAL.MYTEXT],
                From=self.schema.TEXTUAL,
                Where=Not(self.schema.TEXTUAL.MYTEXT.StartsWith("test")),
            ).toSQL(),
            SQLFragment(
                "select MYTEXT from TEXTUAL where not MYTEXT like (? || ?)",
                ["test", "%"]
            )
        )

        self.assertEquals(
            Select([
                self.schema.TEXTUAL.MYTEXT],
                From=self.schema.TEXTUAL,
                Where=Not(self.schema.TEXTUAL.MYTEXT == "test"),
            ).toSQL(),
            SQLFragment(
                "select MYTEXT from TEXTUAL where not MYTEXT = ?",
                ["test"]
            )
        )

        self.assertEquals(
            Select([
                self.schema.TEXTUAL.MYTEXT],
                From=self.schema.TEXTUAL,
                Where=Not((self.schema.TEXTUAL.MYTEXT == "test1").And(self.schema.TEXTUAL.MYTEXT != "test2")),
            ).toSQL(),
            SQLFragment(
                "select MYTEXT from TEXTUAL where not (MYTEXT = ? and MYTEXT != ?)",
                ["test1", "test2"]
            )
        )

        self.assertEquals(
            Select([
                self.schema.TEXTUAL.MYTEXT],
                From=self.schema.TEXTUAL,
                Where=Not((self.schema.TEXTUAL.MYTEXT == "test1")).And(self.schema.TEXTUAL.MYTEXT != "test2"),
            ).toSQL(),
            SQLFragment(
                "select MYTEXT from TEXTUAL where not MYTEXT = ? and MYTEXT != ?",
                ["test1", "test2"]
            )
        )

        self.assertEquals(
            Select([
                self.schema.TEXTUAL.MYTEXT],
                From=self.schema.TEXTUAL,
                Where=Not(self.schema.TEXTUAL.MYTEXT.StartsWith("foo").And(self.schema.TEXTUAL.MYTEXT.NotEndsWith("bar"))),
            ).toSQL(),
            SQLFragment(
                "select MYTEXT from TEXTUAL where not (MYTEXT like (? || ?) and MYTEXT not like (? || ?))",
                ["foo", "%", "%", "bar"]
            )
        )


    def test_insert(self):
        """
        L{Insert.toSQL} generates an C{insert} statement with all the relevant
        columns.
        """
        self.assertEquals(
            Insert(
                {self.schema.FOO.BAR: 23, self.schema.FOO.BAZ: 9}
            ).toSQL(),
            SQLFragment("insert into FOO (BAR, BAZ) values (?, ?)", [23, 9])
        )


    def test_insertNotEnough(self):
        """
        L{Insert}'s constructor will raise L{NotEnoughValues} if columns have
        not been specified.
        """
        notEnough = self.assertRaises(
            NotEnoughValues, Insert, {self.schema.OTHER.BAR: 9}
        )
        self.assertEquals(str(notEnough), "Columns [FOO_BAR] required.")


    def test_insertReturning(self):
        """
        L{Insert}'s C{Return} argument will insert an SQL C{returning} clause.
        """
        self.assertEquals(
            Insert(
                {self.schema.FOO.BAR: 23, self.schema.FOO.BAZ: 9},
                Return=self.schema.FOO.BAR
            ).toSQL(),
            SQLFragment(
                "insert into FOO (BAR, BAZ) values (?, ?) returning BAR",
                [23, 9]
            )
        )


    def test_insertMultiReturn(self):
        """
        L{Insert}'s C{Return} argument can also be a C{tuple}, which will
        insert an SQL C{returning} clause with multiple columns.
        """
        self.assertEquals(
            Insert(
                {self.schema.FOO.BAR: 23, self.schema.FOO.BAZ: 9},
                Return=(self.schema.FOO.BAR, self.schema.FOO.BAZ)
            ).toSQL(),
            SQLFragment(
                "insert into FOO (BAR, BAZ) values (?, ?) returning BAR, BAZ",
                [23, 9]
            )
        )


    def test_insertMultiReturnOracle(self):
        """
        In Oracle's SQL dialect, the C{returning} clause requires an C{into}
        clause indicating where to put the results, as they can't be simply
        relayed to the cursor.  Further, additional bound variables are
        required to capture the output parameters.
        """
        self.assertEquals(
            Insert(
                {self.schema.FOO.BAR: 40, self.schema.FOO.BAZ: 50},
                Return=(self.schema.FOO.BAR, self.schema.FOO.BAZ)
            ).toSQL(QueryGenerator(ORACLE_DIALECT, NumericPlaceholder())),
            SQLFragment(
                "insert into FOO (BAR, BAZ) values (:1, :2) "
                "returning BAR, BAZ into :3, :4",
                [40, 50, Parameter("oracle_out_0"), Parameter("oracle_out_1")]
            )
        )


    def test_insertMultiReturnSQLite(self):
        """
        In SQLite's SQL dialect, there is no C{returning} clause, but given
        that SQLite serializes all SQL transactions, you can rely upon
        C{select} after a write operation to reliably give you exactly what was
        just modified.  Therefore, although C{toSQL} won't include any
        indication of the return value, the C{on} method will execute a
        C{select} statement following the insert to retrieve the value.
        """
        insertStatement = Insert(
            {self.schema.FOO.BAR: 39, self.schema.FOO.BAZ: 82},
            Return=(self.schema.FOO.BAR, self.schema.FOO.BAZ)
        )
        qg = lambda: QueryGenerator(SQLITE_DIALECT, NumericPlaceholder())
        self.assertEquals(
            insertStatement.toSQL(qg()),
            SQLFragment("insert into FOO (BAR, BAZ) values (:1, :2)", [39, 82])
        )
        result = []
        csql = CatchSQL()
        insertStatement.on(csql).addCallback(result.append)
        self.assertEqual(result, [2])
        self.assertEqual(
            csql.execed,
            [
                [
                    "insert into FOO (BAR, BAZ) values (:1, :2)",
                    [39, 82]
                ],
                [
                    "select BAR, BAZ from FOO "
                    "where rowid = last_insert_rowid()",
                    []
                ],
            ]
        )


    def test_insertNoReturnSQLite(self):
        """
        Insert a row I{without} a C{Return=} parameter should also work as
        normal in sqlite.
        """
        statement = Insert(
            {self.schema.FOO.BAR: 12, self.schema.FOO.BAZ: 48}
        )
        csql = CatchSQL()
        statement.on(csql)
        self.assertEqual(
            csql.execed,
            [["insert into FOO (BAR, BAZ) values (:1, :2)", [12, 48]]]
        )


    def test_updateReturningSQLite(self):
        """
        Since SQLite does not support the SQL C{returning} syntax extension, in
        order to preserve the rows that will be modified during an UPDATE
        statement, we must first find the rows that will be affected, then
        update them, then return the rows that were affected.  Since we might
        be changing even part of the primary key, we use the internal C{rowid}
        column to uniquely and reliably identify rows in the sqlite database
        that have been modified.
        """
        csql = CatchSQL()
        stmt = Update(
            {self.schema.FOO.BAR: 4321},
            Where=self.schema.FOO.BAZ == 1234,
            Return=self.schema.FOO.BAR
        )
        csql.nextResult([["sample row id"]])
        result = resultOf(stmt.on(csql))

        # Three statements were executed; make sure that the result returned
        # was the result of executing the 3rd (and final) one.
        self.assertResultList(result, 3)

        # Check that they were the right statements.
        self.assertEqual(len(csql.execed), 3)
        self.assertEqual(
            csql.execed[0],
            ["select rowid from FOO where BAZ = :1", [1234]]
        )
        self.assertEqual(
            csql.execed[1],
            ["update FOO set BAR = :1 where BAZ = :2", [4321, 1234]]
        )
        self.assertEqual(
            csql.execed[2],
            ["select BAR from FOO where rowid = :1", ["sample row id"]]
        )


    def test_updateReturningMultipleValuesSQLite(self):
        """
        When SQLite updates multiple values, it must embed the row ID of each
        subsequent value into its second C{where} clause, as there is no way to
        pass a list of values to a single statement..
        """
        csql = CatchSQL()
        stmt = Update(
            {self.schema.FOO.BAR: 4321},
            Where=self.schema.FOO.BAZ == 1234,
            Return=self.schema.FOO.BAR
        )
        csql.nextResult([["one row id"], ["and another"], ["and one more"]])
        result = resultOf(stmt.on(csql))

        # Three statements were executed; make sure that the result returned
        # was the result of executing the 3rd (and final) one.
        self.assertResultList(result, 3)

        # Check that they were the right statements.
        self.assertEqual(len(csql.execed), 3)
        self.assertEqual(
            csql.execed[0],
            ["select rowid from FOO where BAZ = :1", [1234]]
        )
        self.assertEqual(
            csql.execed[1],
            ["update FOO set BAR = :1 where BAZ = :2", [4321, 1234]]
        )
        self.assertEqual(
            csql.execed[2],
            [
                "select BAR from FOO "
                "where rowid = :1 or rowid = :2 or rowid = :3",
                ["one row id", "and another", "and one more"]
            ]
        )


    def test_deleteReturningSQLite(self):
        """
        When SQLite deletes a value, ...
        """
        csql = CatchSQL()
        stmt = Delete(
            From=self.schema.FOO,
            Where=self.schema.FOO.BAZ == 1234,
            Return=self.schema.FOO.BAR
        )
        result = resultOf(stmt.on(csql))
        self.assertResultList(result, 1)
        self.assertEqual(len(csql.execed), 2)
        self.assertEqual(
            csql.execed[0],
            ["select BAR from FOO where BAZ = :1", [1234]]
        )
        self.assertEqual(
            csql.execed[1],
            ["delete from FOO where BAZ = :1", [1234]]
        )


    def test_insertMismatch(self):
        """
        L{Insert} raises L{TableMismatch} if the columns specified aren't all
        from the same table.
        """
        self.assertRaises(
            TableMismatch,
            Insert, {
                self.schema.FOO.BAR: 23,
                self.schema.FOO.BAZ: 9,
                self.schema.TEXTUAL.MYTEXT: "hello"
            }
        )


    def test_quotingOnKeywordConflict(self):
        """
        "access" is a keyword, so although our schema parser will leniently
        accept it, it must be quoted in any outgoing SQL.  (This is only done
        in the Oracle dialect, because it isn't necessary in postgres, and
        idiosyncratic case-folding rules make it challenging to do it in both.)
        """
        self.assertEquals(
            Insert(
                {
                    self.schema.LEVELS.ACCESS: 1,
                    self.schema.LEVELS.USERNAME: "hi"
                }
            ).toSQL(QueryGenerator(ORACLE_DIALECT, FixedPlaceholder("?"))),
            SQLFragment(
                """insert into LEVELS ("ACCESS", USERNAME) values (?, ?)""",
                [1, "hi"]
            )
        )
        self.assertEquals(
            Insert(
                {
                    self.schema.LEVELS.ACCESS: 1,
                    self.schema.LEVELS.USERNAME: "hi"
                }
            ).toSQL(QueryGenerator(POSTGRES_DIALECT, FixedPlaceholder("?"))),
            SQLFragment(
                "insert into LEVELS (ACCESS, USERNAME) values (?, ?)",
                [1, "hi"]
            )
        )


    def test_updateReturning(self):
        """
        L{update}'s C{Return} argument will update an SQL C{returning} clause.
        """
        self.assertEquals(
            Update(
                {self.schema.FOO.BAR: 23},
                self.schema.FOO.BAZ == 43,
                Return=self.schema.FOO.BAR
            ).toSQL(),
            SQLFragment(
                "update FOO set BAR = ? where BAZ = ? returning BAR",
                [23, 43]
            )
        )


    def test_updateMismatch(self):
        """
        L{Update} raises L{TableMismatch} if the columns specified aren't all
        from the same table.
        """
        self.assertRaises(
            TableMismatch,
            Update, {
                self.schema.FOO.BAR: 23,
                self.schema.FOO.BAZ: 9,
                self.schema.TEXTUAL.MYTEXT: "hello"
            },
            Where=self.schema.FOO.BAZ == 9
        )


    def test_updateFunction(self):
        """
        L{Update} values may be L{FunctionInvocation}s, to update to computed
        values in the database.
        """
        sqlfunc = Function("hello")
        self.assertEquals(
            Update(
                {self.schema.FOO.BAR: 23, self.schema.FOO.BAZ: sqlfunc()},
                Where=self.schema.FOO.BAZ == 9
            ).toSQL(),
            SQLFragment(
                "update FOO set BAR = ?, BAZ = hello() where BAZ = ?", [23, 9]
            )
        )


    def test_insertFunction(self):
        """
        L{Update} values may be L{FunctionInvocation}s, to update to computed
        values in the database.
        """
        sqlfunc = Function("hello")
        self.assertEquals(
            Insert(
                {self.schema.FOO.BAR: 23, self.schema.FOO.BAZ: sqlfunc()},
            ).toSQL(),
            SQLFragment("insert into FOO (BAR, BAZ) values (?, hello())", [23])
        )


    def test_deleteReturning(self):
        """
        L{Delete}'s C{Return} argument will delete an SQL C{returning} clause.
        """
        self.assertEquals(
            Delete(
                self.schema.FOO,
                Where=self.schema.FOO.BAR == 7,
                Return=self.schema.FOO.BAZ
            ).toSQL(),
            SQLFragment("delete from FOO where BAR = ? returning BAZ", [7])
        )


    def test_update(self):
        """
        L{Update.toSQL} generates an C{update} statement.
        """
        self.assertEquals(
            Update(
                {self.schema.FOO.BAR: 4321},
                self.schema.FOO.BAZ == 1234
            ).toSQL(),
            SQLFragment("update FOO set BAR = ? where BAZ = ?", [4321, 1234])
        )


    def test_delete(self):
        """
        L{Delete} generates an SQL C{delete} statement.
        """
        self.assertEquals(
            Delete(self.schema.FOO, Where=self.schema.FOO.BAR == 12).toSQL(),
            SQLFragment("delete from FOO where BAR = ?", [12])
        )

        self.assertEquals(
            Delete(self.schema.FOO, Where=None).toSQL(),
            SQLFragment("delete from FOO")
        )


    def test_lock(self):
        """
        L{Lock.exclusive} generates a C{lock table} statement, locking the
        table in the specified mode.
        """
        self.assertEquals(
            Lock.exclusive(self.schema.FOO).toSQL(),
            SQLFragment("lock table FOO in exclusive mode")
        )


    def test_databaseLock(self):
        """
        L{DatabaseLock} generates a C{pg_advisory_lock} statement
        """
        self.assertEquals(
            DatabaseLock().toSQL(),
            SQLFragment("select pg_advisory_lock(1)")
        )


    def test_databaseUnlock(self):
        """
        L{DatabaseUnlock} generates a C{pg_advisory_unlock} statement
        """
        self.assertEquals(
            DatabaseUnlock().toSQL(),
            SQLFragment("select pg_advisory_unlock(1)")
        )


    def test_savepoint(self):
        """
        L{Savepoint} generates a C{savepoint} statement.
        """
        self.assertEquals(
            Savepoint("test").toSQL(),
            SQLFragment("savepoint test")
        )


    def test_rollbacktosavepoint(self):
        """
        L{RollbackToSavepoint} generates a C{rollback to savepoint} statement.
        """
        self.assertEquals(
            RollbackToSavepoint("test").toSQL(),
            SQLFragment("rollback to savepoint test")
        )


    def test_releasesavepoint(self):
        """
        L{ReleaseSavepoint} generates a C{release savepoint} statement.
        """
        self.assertEquals(
            ReleaseSavepoint("test").toSQL(),
            SQLFragment("release savepoint test")
        )


    def test_savepointaction(self):
        """
        L{SavepointAction} generates a C{savepoint} statement.
        """
        self.assertEquals(SavepointAction("test")._name, "test")


    def test_limit(self):
        """
        A L{Select} object with a C{Limit} keyword parameter will generate
        a SQL statement with a C{limit} clause.
        """
        self.assertEquals(
            Select(
                [self.schema.FOO.BAR],
                From=self.schema.FOO,
                Limit=123
            ).toSQL(),
            SQLFragment("select BAR from FOO limit ?", [123])
        )


    def test_limitOracle(self):
        """
        A L{Select} object with a C{Limit} keyword parameter will generate a
        SQL statement using a ROWNUM subquery for Oracle.

        See U{this "ask tom" article from 2006 for more
        information
        <http://www.oracle.com/technetwork/issue-archive/2006/06-sep/o56asktom-086197.html>}.
        """
        self.assertEquals(
            Select(
                [self.schema.FOO.BAR],
                From=self.schema.FOO,
                Limit=123
            ).toSQL(QueryGenerator(ORACLE_DIALECT, FixedPlaceholder("?"))),
            SQLFragment(
                "select * from (select BAR from FOO) "
                "where ROWNUM <= ?", [123]
            )
        )


    def test_having(self):
        """
        A L{Select} object with a C{Having} keyword parameter will generate
        a SQL statement with a C{having} expression.
        """
        self.assertEquals(
            Select(
                [self.schema.FOO.BAR],
                From=self.schema.FOO,
                Having=Max(self.schema.FOO.BAZ) < 7
            ).toSQL(),
            SQLFragment("select BAR from FOO having max(BAZ) < ?", [7])
        )


    def test_distinct(self):
        """
        A L{Select} object with a C{Disinct} keyword parameter with a value of
        C{True} will generate a SQL statement with a C{distinct} keyword
        preceding its list of columns.
        """
        self.assertEquals(
            Select(
                [self.schema.FOO.BAR],
                From=self.schema.FOO,
                Distinct=True
            ).toSQL(),
            SQLFragment("select distinct BAR from FOO")
        )


    def test_nextSequenceValue(self):
        """
        When a sequence is used as a value in an expression, it renders as the
        call to C{nextval} that will produce its next value.
        """
        self.assertEquals(
            Insert({self.schema.BOZ.QUX: self.schema.A_SEQ}).toSQL(),
            SQLFragment("insert into BOZ (QUX) values (nextval('A_SEQ'))", [])
        )


    def test_nextSequenceValueOracle(self):
        """
        When a sequence is used as a value in an expression in the Oracle
        dialect, it renders as the C{nextval} attribute of the appropriate
        sequence.
        """
        self.assertEquals(
            Insert(
                {self.schema.BOZ.QUX: self.schema.A_SEQ}
            ).toSQL(QueryGenerator(ORACLE_DIALECT, FixedPlaceholder("?"))),
            SQLFragment("insert into BOZ (QUX) values (A_SEQ.nextval)", [])
        )


    def test_nextSequenceDefaultImplicitExplicitOracle(self):
        """
        In Oracle's dialect, sequence defaults can't be implemented without
        using triggers, so instead we just explicitly always include the
        sequence default value.
        """
        addSQLToSchema(
            schema=self.schema.model,
            schemaData=(
                "create table DFLTR (a varchar(255), "
                "b integer default nextval('A_SEQ'));"
            )
        )
        self.assertEquals(
            Insert({self.schema.DFLTR.a: "hello"}).toSQL(
                QueryGenerator(ORACLE_DIALECT, FixedPlaceholder("?"))
            ),
            SQLFragment("insert into DFLTR (a, b) values "
                        "(?, A_SEQ.nextval)", ["hello"]),
        )
        # Should be the same if it's explicitly specified.
        self.assertEquals(
            Insert(
                {
                    self.schema.DFLTR.a: "hello",
                    self.schema.DFLTR.b: self.schema.A_SEQ
                }
            ).toSQL(
                QueryGenerator(ORACLE_DIALECT, FixedPlaceholder("?"))
            ),
            SQLFragment(
                "insert into DFLTR (a, b) values (?, A_SEQ.nextval)", ["hello"]
            ),
        )


    def test_numericParams(self):
        """
        An L{IAsyncTransaction} with the C{numeric} paramstyle attribute will
        cause statements to be generated with parameters in the style of
        C{:1 :2 :3}, as per the DB-API.
        """
        stmts = []

        class FakeOracleTxn(object):
            def execSQL(self, text, params, exc):
                stmts.append((text, params))
            dialect = ORACLE_DIALECT
            paramstyle = "numeric"

        Select(
            [self.schema.FOO.BAR],
            From=self.schema.FOO,
            Where=(self.schema.FOO.BAR == 7).And(self.schema.FOO.BAZ == 9)
        ).on(FakeOracleTxn())

        self.assertEquals(
            stmts,
            [("select BAR from FOO where BAR = :1 and BAZ = :2", [7, 9])]
        )


    def test_rewriteOracleNULLs_Select(self):
        """
        Oracle databases cannot distinguish between the empty string and
        C{NULL}.  When you insert an empty string, C{cx_Oracle} therefore
        treats it as a C{None} and will return that when you select it back
        again.  We address this in the schema by dropping C{not null}
        constraints.

        Therefore, when executing a statement which includes a string column,
        C{on} should rewrite None return values from C{cx_Oracle} to be empty
        bytestrings, but only for string columns.
        """
        rows = resultOf(
            Select(
                [self.schema.NULLCHECK.ASTRING, self.schema.NULLCHECK.ANUMBER],
                From=self.schema.NULLCHECK
            ).on(NullTestingOracleTxn())
        )[0]

        self.assertEquals(rows, [["", None]])


    def test_rewriteOracleNULLs_SelectAllColumns(self):
        """
        Same as L{test_rewriteOracleNULLs_Select}, but with the L{ALL_COLUMNS}
        shortcut.
        """
        rows = resultOf(
            Select(From=self.schema.NULLCHECK).on(NullTestingOracleTxn())
        )[0]
        self.assertEquals(rows, [["", None]])


    def test_nestedLogicalExpressions(self):
        """
        Make sure that logical operator precedence inserts proper parenthesis
        when needed.  e.g. C{a.And(b.Or(c))} needs to be C{a and (b or c)} not
        C{a and b or c}.
        """
        self.assertEquals(
            Select(
                From=self.schema.FOO,
                Where=(
                    (
                        self.schema.FOO.BAR != 7
                    ).And(
                        self.schema.FOO.BAZ != 8
                    ).And(
                        (self.schema.FOO.BAR == 8).Or(self.schema.FOO.BAZ == 0)
                    )
                )
            ).toSQL(),
            SQLFragment(
                "select * from FOO where BAR != ? and BAZ != ? and "
                "(BAR = ? or BAZ = ?)",
                [7, 8, 8, 0]
            )
        )

        self.assertEquals(
            Select(
                From=self.schema.FOO,
                Where=(
                    (
                        self.schema.FOO.BAR != 7
                    ).Or(
                        self.schema.FOO.BAZ != 8
                    ).Or(
                        (
                            self.schema.FOO.BAR == 8
                        ).And(
                            self.schema.FOO.BAZ == 0
                        )
                    )
                )
            ).toSQL(),
            SQLFragment(
                "select * from FOO where BAR != ? or BAZ != ? or "
                "BAR = ? and BAZ = ?",
                [7, 8, 8, 0]
            )
        )

        self.assertEquals(
            Select(
                From=self.schema.FOO,
                Where=(
                    (
                        self.schema.FOO.BAR != 7
                    ).Or(
                        self.schema.FOO.BAZ != 8
                    ).And(
                        (self.schema.FOO.BAR == 8).Or(self.schema.FOO.BAZ == 0)
                    )
                )
            ).toSQL(),
            SQLFragment(
                "select * from FOO where (BAR != ? or BAZ != ?) and "
                "(BAR = ? or BAZ = ?)",
                [7, 8, 8, 0]
            )
        )


    def test_updateWithNULL(self):
        """
        As per the DB-API specification, "SQL NULL values are represented by
        the Python None singleton on input and output."  When a C{None} is
        provided as a value to an L{Update}, it will be relayed to the database
        as a parameter.
        """
        self.assertEquals(
            Update(
                {self.schema.BOZ.QUX: None},
                Where=self.schema.BOZ.QUX == 7
            ).toSQL(),
            SQLFragment("update BOZ set QUX = ? where QUX = ?", [None, 7])
        )


    def test_subSelectComparison(self):
        """
        A comparison of a column to a sub-select in a where clause will result
        in a parenthetical C{where} clause.
        """
        self.assertEquals(
            Update(
                {self.schema.BOZ.QUX: 9},
                Where=(
                    self.schema.BOZ.QUX ==
                    Select(
                        [self.schema.FOO.BAR],
                        From=self.schema.FOO,
                        Where=self.schema.FOO.BAZ == 12
                    )
                )
            ).toSQL(),
            SQLFragment(
                # NOTE: it's very important that the comparison _always_ go in
                # this order (column from the UPDATE first, inner SELECT
                # second) as the other order will be considered a syntax error.
                "update BOZ set QUX = ? "
                "where QUX = (select BAR from FOO where BAZ = ?)",
                [9, 12]
            )
        )


    def test_tupleComparison(self):
        """
        A L{Tuple} allows for simultaneous comparison of multiple values in a
        C{Where} clause.  This feature is particularly useful when issuing an
        L{Update} or L{Delete}, where the comparison is with values from a
        subselect.  (A L{Tuple} will be automatically generated upon comparison
        to a C{tuple} or C{list}.)
        """
        self.assertEquals(
            Update(
                {self.schema.BOZ.QUX: 1},
                Where=(
                    (self.schema.BOZ.QUX, self.schema.BOZ.QUUX) ==
                    Select(
                        [self.schema.FOO.BAR, self.schema.FOO.BAZ],
                        From=self.schema.FOO,
                        Where=self.schema.FOO.BAZ == 2
                    )
                )
            ).toSQL(),
            SQLFragment(
                # NOTE: it's very important that the comparison _always_ go in
                # this order (tuple of columns from the UPDATE first, inner
                # SELECT second) as the other order will be considered a syntax
                # error.
                "update BOZ set QUX = ? where (QUX, QUUX) = ("
                "select BAR, BAZ from FOO where BAZ = ?)", [1, 2]
            )
        )


    def test_tupleOfConstantsComparison(self):
        """
        For some reason Oracle requires multiple parentheses for comparisons.
        """
        self.assertEquals(
            Select(
                [self.schema.FOO.BAR],
                From=self.schema.FOO,
                Where=(
                    Tuple([self.schema.FOO.BAR, self.schema.FOO.BAZ]) ==
                    Tuple([Constant(7), Constant(9)])
                )
            ).toSQL(),
            SQLFragment(
                "select BAR from FOO where (BAR, BAZ) = ((?, ?))", [7, 9]
            )
        )


    def test_oracleTableTruncation(self):
        """
        L{Table}'s SQL generation logic will truncate table names if the
        dialect (i.e. Oracle) demands it.
        (See txdav.common.datastore.sql_tables for the schema translator and
        enforcement of name uniqueness in the derived schema.)
        """
        addSQLToSchema(
            self.schema.model,
            "create table veryveryveryveryveryveryveryverylong "
            "(foo integer);"
        )
        vvl = self.schema.veryveryveryveryveryveryveryverylong
        self.assertEquals(
            Insert({vvl.foo: 1}).toSQL(
                QueryGenerator(ORACLE_DIALECT, FixedPlaceholder("?"))
            ),
            SQLFragment(
                "insert into veryveryveryveryveryveryveryve (foo) values (?)",
                [1]
            )
        )


    def test_columnEqualityTruth(self):
        """
        Mostly in support of L{test_columnsAsDictKeys}, the "same" column
        should compare C{True} to itself and C{False} to other values.
        """
        s = self.schema
        self.assertEquals(bool(s.FOO.BAR == s.FOO.BAR), True)
        self.assertEquals(bool(s.FOO.BAR != s.FOO.BAR), False)
        self.assertEquals(bool(s.FOO.BAZ != s.FOO.BAR), True)


    def test_columnsAsDictKeys(self):
        """
        An odd corner of the syntactic sugar provided by the DAL is that the
        column objects have to participate both in augmented equality
        comparison (C{==} returns an expression object) as well as dictionary
        keys (for Insert and Update statement objects).  Therefore it should be
        possible to I{manipulate} dictionaries of keys as well.
        """
        values = {self.schema.FOO.BAR: 1}
        self.assertEquals(values, {self.schema.FOO.BAR: 1})
        values.pop(self.schema.FOO.BAR)
        self.assertEquals(values, {})



class OracleConnectionMethods(object):
    def test_rewriteOracleNULLs_Insert(self):
        """
        The behavior described in L{test_rewriteOracleNULLs_Select} applies to
        other statement types as well, specifically those with C{returning}
        clauses.
        """
        # Add 2 cursor variable values so that these will be used by
        # FakeVariable.getvalue.
        self.factory.varvals.extend([None, None])
        rows = self.resultOf(
            Insert(
                {
                    self.schema.NULLCHECK.ASTRING: "",
                    self.schema.NULLCHECK.ANUMBER: None,
                },
                Return=[
                    self.schema.NULLCHECK.ASTRING,
                    self.schema.NULLCHECK.ANUMBER,
                ]
            ).on(self.createTransaction())
        )[0]
        self.assertEquals(rows, [["", None]])


    def test_insertMultiReturnOnOracleTxn(self):
        """
        As described in L{test_insertMultiReturnOracle}, Oracle deals with
        C{returning} clauses by using out parameters.  However, this is not
        quite enough, as the code needs to actually retrieve the values from
        the out parameters.
        """
        i = Insert(
            {self.schema.FOO.BAR: 40, self.schema.FOO.BAZ: 50},
            Return=(self.schema.FOO.BAR, self.schema.FOO.BAZ)
        )
        self.factory.varvals.extend(["first val!", "second val!"])
        result = self.resultOf(i.on(self.createTransaction()))
        self.assertEquals(result, [[["first val!", "second val!"]]])
        curvars = self.factory.connections[0].cursors[0].variables
        self.assertEquals(len(curvars), 2)
        self.assertEquals(curvars[0].type, FakeCXOracleModule.NUMBER)
        self.assertEquals(curvars[1].type, FakeCXOracleModule.STRING)


    def test_insertNoReturnOracle(self):
        """
        In addition to being able to execute insert statements with a Return
        attribute, oracle also ought to be able to execute insert statements
        with no Return at all.
        """
        # This statement should return nothing from .fetchall(), so...
        self.factory.hasResults = False
        i = Insert(
            {self.schema.FOO.BAR: 40, self.schema.FOO.BAZ: 50}
        )
        result = self.resultOf(i.on(self.createTransaction()))
        self.assertEquals(result, [None])



class OracleConnectionTests(
    ConnectionPoolHelper, ExampleSchemaHelper, OracleConnectionMethods,
    TestCase
):
    """
    Tests which use an oracle connection.
    """

    dialect = ORACLE_DIALECT

    def setUp(self):
        """
        Create a fake oracle-ish connection pool without using real threads or
        a real database.
        """
        self.patch(syntax, "cx_Oracle", FakeCXOracleModule)
        super(OracleConnectionTests, self).setUp()
        ExampleSchemaHelper.setUp(self)



class OracleNetConnectionTests(
    NetworkedPoolHelper, ExampleSchemaHelper, OracleConnectionMethods,
    TestCase
):

    dialect = ORACLE_DIALECT

    def setUp(self):
        self.patch(syntax, "cx_Oracle", FakeCXOracleModule)
        super(OracleNetConnectionTests, self).setUp()
        ExampleSchemaHelper.setUp(self)
        self.pump.client.dialect = ORACLE_DIALECT
