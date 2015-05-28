# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for parsing an SQL schema, which cover L{twext.enterprise.dal.model}
and L{twext.enterprise.dal.parseschema}.
"""

from twext.enterprise.dal.model import Schema, ProcedureCall
from twext.enterprise.dal.syntax import CompoundComparison, ColumnSyntax

try:
    from twext.enterprise.dal.parseschema import addSQLToSchema
except ImportError as e:
    def addSQLToSchema(*args, **kwargs):
        raise SkipTest("addSQLToSchema is not available: {0}".format(e))

from twisted.trial.unittest import TestCase, SkipTest



class SchemaTestHelper(object):
    """
    Mix-in that can parse a schema from a string.
    """

    def schemaFromString(self, string):
        """
        Createa a L{Schema}
        """
        s = Schema(self.id())
        addSQLToSchema(s, string)
        return s



class ParsingExampleTests(TestCase, SchemaTestHelper):
    """
    Tests for parsing some sample schemas.
    """

    def test_simplest(self):
        """
        Parse an extremely simple schema with one table in it.
        """
        s = self.schemaFromString("create table foo (bar integer);")
        self.assertEquals(len(s.tables), 1)
        foo = s.tableNamed('foo')
        self.assertEquals(len(foo.columns), 1)
        bar = foo.columns[0]
        self.assertEquals(bar.name, "bar")
        self.assertEquals(bar.type.name, "integer")


    def test_stringTypes(self):
        """
        Table and column names should be byte strings.
        """
        s = self.schemaFromString("create table foo (bar integer);")
        self.assertEquals(len(s.tables), 1)
        foo = s.tableNamed('foo')
        self.assertIsInstance(foo.name, str)
        self.assertIsInstance(foo.columnNamed('bar').name, str)


    def test_typeWithLength(self):
        """
        Parse a type with a length.
        """
        s = self.schemaFromString("create table foo (bar varchar(6543))")
        bar = s.tableNamed('foo').columnNamed('bar')
        self.assertEquals(bar.type.name, "varchar")
        self.assertEquals(bar.type.length, 6543)


    def test_sequence(self):
        """
        Parsing a 'create sequence' statement adds a L{Sequence} to the
        L{Schema}.
        """
        s = self.schemaFromString("create sequence myseq;")
        self.assertEquals(len(s.sequences), 1)
        self.assertEquals(s.sequences[0].name, "myseq")


    def test_sequenceColumn(self):
        """
        Parsing a 'create sequence' statement adds a L{Sequence} to the
        L{Schema}, and then a table that contains a column which uses the SQL
        C{nextval()} function to retrieve its default value from that sequence,
        will cause the L{Column} object to refer to the L{Sequence} and vice
        versa.
        """
        s = self.schemaFromString(
            """
            create sequence thingy;
            create table thetable (
                thecolumn integer default nextval('thingy')
            );
            create table thetable2 (
                thecolumn2 integer primary key default nextval('thingy'),
                ignoreme integer
            );
            """)
        self.assertEquals(len(s.sequences), 1)
        self.assertEquals(s.sequences[0].name, "thingy")
        self.assertEquals(s.tables[0].columns[0].default, s.sequences[0])
        self.assertEquals(s.tables[1].columns[0].default, s.sequences[0])
        self.assertEquals(s.sequences[0].referringColumns,
                          [s.tables[0].columns[0], s.tables[1].columns[0]])


    def test_sequenceDefault(self):
        """
        Default sequence column.
        """
        s = self.schemaFromString(
            """
            create sequence alpha;
            create table foo (
                bar integer default nextval('alpha') not null,
                qux integer not null
            );
            """)
        self.assertEquals(s.tableNamed("foo").columnNamed("bar").needsValue(),
                          False)


    def test_sequenceDefaultWithParens(self):
        """
        SQLite requires 'default' expression to be in parentheses, and that
        should be equivalent on other databases; we should be able to parse
        that too.
        """
        s = self.schemaFromString(
            """
            create sequence alpha;
            create table foo (
                bar integer default (nextval('alpha')) not null,
                qux integer not null
            );
            """
        )
        self.assertEquals(s.tableNamed("foo").columnNamed("bar").needsValue(),
                          False)


    def test_defaultConstantColumns(self):
        """
        Parsing a 'default' column with an appropriate type in it will return
        that type as the 'default' attribute of the Column object.
        """
        s = self.schemaFromString(
            """
            create table a (
                b integer default 4321,
                c boolean default false,
                d boolean default true,
                e varchar(255) default 'sample value',
                f varchar(255) default null
            );
            """)
        table = s.tableNamed("a")
        self.assertEquals(table.columnNamed("b").default, 4321)
        self.assertEquals(table.columnNamed("c").default, False)
        self.assertEquals(table.columnNamed("d").default, True)
        self.assertEquals(table.columnNamed("e").default, 'sample value')
        self.assertEquals(table.columnNamed("f").default, None)


    def test_defaultFunctionColumns(self):
        """
        Parsing a 'default' column with a function call in it will return
        that function as the 'default' attribute of the Column object.
        """
        s = self.schemaFromString(
            """
            create table a (
                b1 integer default tz(),
                b2 integer default tz('UTC'),
                b3 integer default tz('UTC', 'GMT'),
                b4 integer default timezone('UTC', CURRENT_TIMESTAMP),
                b5 integer default CURRENT_TIMESTAMP at time zone 'UTC'
            );
            """)
        table = s.tableNamed("a")
        self.assertEquals(table.columnNamed("b1").default, ProcedureCall("tz", []))
        self.assertEquals(table.columnNamed("b2").default, ProcedureCall("tz", ["UTC"]))
        self.assertEquals(table.columnNamed("b3").default, ProcedureCall("tz", ["UTC", "GMT"]))
        self.assertEquals(table.columnNamed("b4").default, ProcedureCall("timezone", ["UTC", "CURRENT_TIMESTAMP"]))
        self.assertEquals(table.columnNamed("b5").default, ProcedureCall("timezone", ["UTC", "CURRENT_TIMESTAMP"]))


    def test_needsValue(self):
        """
        Columns with defaults, or with a 'not null' constraint don't need a
        value; columns without one don't.
        """
        s = self.schemaFromString(
            """
            create table a (
                b integer default 4321 not null,
                c boolean default false,
                d integer not null,
                e integer
            )
            """)
        table = s.tableNamed("a")
        # Has a default, NOT NULL.
        self.assertEquals(table.columnNamed("b").needsValue(), False)
        # Has a default _and_ nullable.
        self.assertEquals(table.columnNamed("c").needsValue(), False)
        # No default, not nullable.
        self.assertEquals(table.columnNamed("d").needsValue(), True)
        # Just nullable.
        self.assertEquals(table.columnNamed("e").needsValue(), False)


    def test_notNull(self):
        """
        A column with a NOT NULL constraint in SQL will be parsed as a
        constraint which returns False from its C{canBeNull()} method.
        """
        s = self.schemaFromString(
            "create table alpha (beta integer, gamma integer not null);"
        )
        t = s.tableNamed('alpha')
        self.assertEquals(True, t.columnNamed('beta').canBeNull())
        self.assertEquals(False, t.columnNamed('gamma').canBeNull())


    def test_unique(self):
        """
        A column with a UNIQUE constraint in SQL will result in the table
        listing that column as a unique set.
        """
        for identicalSchema in [
                "create table sample (example integer unique);",
                "create table sample (example integer, unique (example));",
                "create table sample "
                "(example integer, constraint unique_example unique (example))"
        ]:
            s = self.schemaFromString(identicalSchema)
            table = s.tableNamed('sample')
            column = table.columnNamed('example')
            self.assertEquals(list(table.uniques()), [[column]])


    def test_checkExpressionConstraint(self):
        """
        A column with a CHECK constraint in SQL that uses an inequality will
        result in a L{Check} constraint being added to the L{Table} object.
        """
        def checkOneConstraint(sqlText, checkName=None):
            s = self.schemaFromString(sqlText)
            table = s.tableNamed('sample')
            self.assertEquals(len(table.constraints), 1)
            constraint = table.constraints[0]
            expr = constraint.expression
            self.assertIsInstance(expr, CompoundComparison)
            self.assertEqual(expr.a.model, table.columnNamed('example'))
            self.assertEqual(expr.b.value, 5)
            self.assertEqual(expr.op, '>')
            self.assertEqual(constraint.name, checkName)
        checkOneConstraint(
            "create table sample (example integer check (example >  5));"
        )
        checkOneConstraint(
            "create table sample (example integer, check (example  > 5));"
        )
        checkOneConstraint(
            "create table sample "
            "(example integer, constraint gt_5 check (example>5))", "gt_5"
        )


    def test_checkKeywordConstraint(self):
        """
        A column with a CHECK constraint in SQL that compares with a keyword
        expression such as 'lower' will result in a L{Check} constraint being
        added to the L{Table} object.
        """
        def checkOneConstraint(sqlText):
            s = self.schemaFromString(sqlText)
            table = s.tableNamed('sample')
            self.assertEquals(len(table.constraints), 1)
            expr = table.constraints[0].expression
            self.assertEquals(expr.a.model, table.columnNamed("example"))
            self.assertEquals(expr.op, "=")
            self.assertEquals(expr.b.function.name, "lower")
            self.assertEquals(
                expr.b.args,
                tuple([ColumnSyntax(table.columnNamed("example"))])
            )
        checkOneConstraint(
            "create table sample "
            "(example integer check (example = lower (example)));"
        )


    def test_multiUnique(self):
        """
        A column with a UNIQUE constraint in SQL will result in the table
        listing that column as a unique set.
        """
        s = self.schemaFromString(
            "create table a (b integer, c integer, unique (b, c), unique (c));"
        )
        a = s.tableNamed('a')
        b = a.columnNamed('b')
        c = a.columnNamed('c')
        self.assertEquals(list(a.uniques()), [[b, c], [c]])


    def test_singlePrimaryKey(self):
        """
        A table with a multi-column PRIMARY KEY clause will be parsed as a list
        of a single L{Column} object and stored as a C{primaryKey} attribute on
        the L{Table} object.
        """
        s = self.schemaFromString(
            "create table a (b integer primary key, c integer)"
        )
        a = s.tableNamed("a")
        self.assertEquals(a.primaryKey, [a.columnNamed("b")])


    def test_multiPrimaryKey(self):
        """
        A table with a multi-column PRIMARY KEY clause will be parsed as a list
        C{primaryKey} attribute on the Table object.
        """
        s = self.schemaFromString(
            "create table a (b integer, c integer, primary key (b, c))"
        )
        a = s.tableNamed("a")
        self.assertEquals(
            a.primaryKey, [a.columnNamed("b"), a.columnNamed("c")]
        )


    def test_deleteAction(self):
        """
        A column with an 'on delete cascade' constraint will have its
        C{cascade} attribute set to True.
        """
        s = self.schemaFromString(
            """
            create table a1 (b1 integer primary key);
            create table c2 (d2 integer references a1 on delete cascade);
            create table ee3 (f3 integer references a1 on delete set null);
            create table g4 (h4 integer references a1 on delete set default);
            """
        )
        self.assertEquals(
            s.tableNamed("a1").columnNamed("b1").deleteAction,
            None
        )
        self.assertEquals(
            s.tableNamed("c2").columnNamed("d2").deleteAction,
            "cascade"
        )
        self.assertEquals(
            s.tableNamed("ee3").columnNamed("f3").deleteAction,
            "set null"
        )
        self.assertEquals(
            s.tableNamed("g4").columnNamed("h4").deleteAction,
            "set default"
        )


    def test_indexes(self):
        """
        A 'create index' statement will add an L{Index} object to a L{Schema}'s
        C{indexes} list.
        """
        s = self.schemaFromString(
            """
            create table q (b integer); -- noise
            create table a (b integer primary key, c integer);
            create table z (c integer); -- make sure we get the right table

            create index idx_a_b on a(b);
            create index idx_a_b_c on a (c, b);
            create index idx_c on z using btree (c);
            """
        )
        a = s.tableNamed("a")
        b = s.indexNamed("idx_a_b")
        bc = s.indexNamed('idx_a_b_c')
        self.assertEquals(b.table, a)
        self.assertEquals(b.columns, [a.columnNamed("b")])
        self.assertEquals(bc.table, a)
        self.assertEquals(bc.columns, [a.columnNamed("c"), a.columnNamed("b")])


    def test_pseudoIndexes(self):
        """
        A implicit and explicit indexes are listed.
        """
        s = self.schemaFromString(
            """
            create table q (b integer); -- noise
            create table a (b integer primary key, c integer);
            create table z (c integer, unique (c) );

            create unique index idx_a_c on a(c);
            create index idx_a_b_c on a (c, b);
            """
        )
        self.assertEqual(
            set([pseudo.name for pseudo in s.pseudoIndexes()]),
            set((
                "a-unique:(c)",
                "a:(c,b)",
                "a-unique:(b)",
                "z-unique:(c)",
            ))
        )


    def test_functions(self):
        """
        A 'create (or replace) function' statement will add an L{Function} object to a L{Schema}'s
        C{functions} list.
        """
        s = self.schemaFromString(
            """
CREATE FUNCTION increment(i integer) RETURNS integer AS $$
BEGIN
    RETURN i + 1;
END;
$$ LANGUAGE plpgsql;
CREATE FUNCTION autoincrement RETURNS integer AS $$
BEGIN
    RETURN 1;
END;
$$ LANGUAGE plpgsql;
CREATE OR REPLACE FUNCTION decrement(i integer) RETURNS integer AS $$
BEGIN
    RETURN i - 1;
END;
$$ LANGUAGE plpgsql;
CREATE OR REPLACE FUNCTION autodecrement (i integer) RETURNS integer AS $$
BEGIN
    RETURN i - 1;
END;
$$ LANGUAGE plpgsql;
            """
        )
        self.assertTrue(s.functionNamed("increment") is not None)
        self.assertTrue(s.functionNamed("decrement") is not None)
        self.assertRaises(KeyError, s.functionNamed, "merge")


    def test_insert(self):
        """
        An 'insert' statement will add an L{schemaRows} to an L{Table}.
        """
        s = self.schemaFromString(
            """
            create table alpha (beta integer, gamma integer not null);

            insert into alpha values (1, 2);
            insert into alpha (gamma, beta) values (3, 4);
            """
        )
        self.assertTrue(s.tableNamed("alpha") is not None)
        self.assertEqual(len(s.tableNamed("alpha").schemaRows), 2)
        rows = [[(column.name, value) for column, value in sorted(row.items(), key=lambda x:x[0].name)] for row in s.tableNamed("alpha").schemaRows]
        self.assertEqual(
            rows,
            [
                [("beta", 1), ("gamma", 2)],
                [("beta", 4), ("gamma", 3)],
            ]
        )
