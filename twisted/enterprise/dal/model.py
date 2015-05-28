# -*- test-case-name: twext.enterprise.dal.test.test_parseschema -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Model classes for SQL.
"""

__all__ = [
    "SQLType",
    "Constraint",
    "Check",
    "ProcedureCall",
    "NO_DEFAULT",
    "Column",
    "Table",
    "Index",
    "PseudoIndex",
    "Sequence",
    "Function",
    "Schema",
]

from twisted.python.util import FancyEqMixin



class SQLType(object):
    """
    A data-type as defined in SQL; like C{integer} or C{real} or
    C{varchar(255)}.

    @ivar name: the name of this type.
    @type name: C{str}

    @ivar length: the length of this type, if it is a type like C{varchar} or
        C{character} that comes with a parenthetical length.
    @type length: C{int} or C{NoneType}
    """

    def __init__(self, name, length):
        _checkstr(name)
        self.name = name
        self.length = length if length else 0


    def __eq__(self, other):
        """
        Compare equal to other L{SQLTypes} with matching name and length. The name is
        normalized so we can compare schema from different types of DB implementations.
        """
        if not isinstance(other, SQLType):
            return NotImplemented
        return (self.normalizedName(), self.length) == (other.normalizedName(), other.length)


    def __ne__(self, other):
        """
        (Inequality is the opposite of equality.)
        """
        if not isinstance(other, SQLType):
            return NotImplemented
        return not self.__eq__(other)


    def __repr__(self):
        """
        A useful string representation which includes the name and length if
        present.
        """
        if self.length:
            lendesc = "(%s)" % (self.length)
        else:
            lendesc = ""
        return "<SQL Type: %r%s>" % (self.name, lendesc)


    def normalizedName(self):
        """
        Map type names to standard names.
        """
        return {
            "nchar": "char",
            "varchar2": "varchar",
            "nvarchar2": "varchar",
            "clob": "text",
            "nclob": "text",
            "boolean": "integer",
        }.get(self.name, self.name)



class Constraint(object):
    """
    A constraint on a set of columns.

    @ivar type: the type of constraint.  Currently, only C{"UNIQUE"} and C{"NOT
        NULL"} are supported.
    @type type: C{str}

    @ivar affectsColumns: Columns affected by this constraint.

    @type affectsColumns: C{list} of L{Column}
    """

    # Values for "type" attribute:
    NOT_NULL = "NOT NULL"
    UNIQUE = "UNIQUE"

    def __init__(self, type, affectsColumns, name=None):
        self.type = type
        self.affectsColumns = affectsColumns
        self.columnNames = tuple([c.name for c in self.affectsColumns])
        self.name = name


    def __repr__(self):
        return "<Constraint: ({} {} {})>".format(self.type, self.columnNames, self.name)


    def __hash__(self):
        return hash((self.type, self.columnNames, self.name,))


    def __eq__(self, other):
        return (
            self.type == other.type and
            self.columnNames == other.columnNames and
            self.name == other.name
        )


    def __ne__(self, other):
        return not self.__eq__(other)



class Check(Constraint):
    """
    A C{check} constraint, which evaluates an SQL expression.

    @ivar expression: the expression that should evaluate to True.
    @type expression: L{twext.enterprise.dal.syntax.ExpressionSyntax}
    """
    # XXX TODO: model for expression, rather than

    def __init__(self, syntaxExpression, name=None):
        self.expression = syntaxExpression
        super(Check, self).__init__(
            "CHECK", [c.model for c in self.expression.allColumns()], name
        )



class ProcedureCall(FancyEqMixin):
    """
    An invocation of a stored procedure or built-in function.
    """

    compareAttributes = 'name args'.split()

    def __init__(self, name, args):
        _checkstr(name)
        self.name = name
        self.args = args



class NO_DEFAULT(object):
    """
    Placeholder value for not having a default.  (C{None} would not be
    suitable, as that would imply a default of C{NULL}).
    """



def _checkstr(x):
    """
    Verify that C{x} is a C{str}.  Raise a L{ValueError} if not.  This is to
    prevent pollution with unicode values.
    """
    if not isinstance(x, str):
        raise ValueError("%r is not a str." % (x,))



def listIfNone(x):
    return [] if x is None else x



def stringIfNone(x, attr=None):
    if attr:
        return "" if x is None else getattr(x, attr)
    else:
        return "" if x is None else x



class Column(FancyEqMixin, object):
    """
    A column from a table.

    @ivar table: The L{Table} to which this L{Column} belongs.
    @type table: L{Table}

    @ivar name: The unqualified name of this column.  For example, in the case
        of a column BAR in a table FOO, this would be the string C{'BAR'}.
    @type name: C{str}

    @ivar type: The declared type of this column.
    @type type: L{SQLType}

    @ivar references: If this column references a foreign key on another table,
        this will be a reference to that table; otherwise (normally) C{None}.
    @type references: L{Table} or C{NoneType}

    @ivar deleteAction: If this column references another table, home will this
        column's row be altered when the matching row in that other table is
        deleted? Possible values are:
        C{None} - for "on delete no action";
        C{"cascade"} - for "on delete cascade";
        C{"set null"} - for "on delete set null";
        C{"set default"} - for "on delete set default".
    @type deleteAction: C{str}
    """

    compareAttributes = 'table name'.split()

    def __init__(self, table, name, type, default=NO_DEFAULT):
        _checkstr(name)
        self.table = table
        self.name = name
        self.type = type
        self.default = default
        self.references = None
        self.deleteAction = None


    def __repr__(self):
        return "<Column (%s %r)>" % (self.name, self.type)


    def compare(self, other):
        """
        Return the differences between two columns.

        @param other: the column to compare with
        @type other: L{Column}
        """

        results = []

        if self.name != other.name:
            results.append("Table: %s, column names %s and %s do not match" % (self.table.name, self.name, other.name,))
        if self.type != other.type:
            results.append("Table: %s, column name %s type mismatch" % (self.table.name, self.name,))
        if self.default != other.default:
            # Some DBs don't allow sequence as a default
            if (
                isinstance(self.default, Sequence) and other.default == NO_DEFAULT or
                self.default == NO_DEFAULT and isinstance(other.default, Sequence) or
                self.default is None and other.default == NO_DEFAULT or
                self.default == NO_DEFAULT and other.default is None
            ):
                pass
            else:
                results.append("Table: %s, column name %s default mismatch" % (self.table.name, self.name,))
        if stringIfNone(self.references, "name") != stringIfNone(other.references, "name"):
            results.append("Table: %s, column name %s references mismatch" % (self.table.name, self.name,))
        if stringIfNone(self.deleteAction, "") != stringIfNone(other.deleteAction, ""):
            results.append("Table: %s, column name %s delete action mismatch" % (self.table.name, self.name,))
        return results


    def canBeNull(self):
        """
        Can this column ever be C{NULL}, i.e. C{None}?  In other words, is it
        free of any C{NOT NULL} constraints?

        @return: C{True} if so, C{False} if not.
        """
        for constraint in self.table.constraints:
            if self in constraint.affectsColumns:
                if constraint.type is Constraint.NOT_NULL:
                    return False
        return True


    def setDefaultValue(self, value):
        """
        Change the default value of this column.  (Should only be called during
        schema parsing.)
        """
        self.default = value


    def needsValue(self):
        """
        Does this column require a value in C{INSERT} statements which create
        rows?

        @return: C{True} for L{Column}s with no default specified which also
            cannot be NULL, C{False} otherwise.

        @rtype: C{bool}
        """
        return not (self.canBeNull() or
                    (self.default not in (None, NO_DEFAULT)))


    def doesReferenceName(self, name):
        """
        Change this column to refer to a table in the schema.  (Should only be
        called during schema parsing.)

        @param name: the name of a L{Table} in this L{Column}'s L{Schema}.
        @type name: L{str}
        """
        self.references = self.table.schema.tableNamed(name)



class Table(FancyEqMixin, object):
    """
    A set of columns.

    @ivar descriptiveComment: A docstring for the table.  Parsed from a C{--}
        comment preceding this table in the SQL schema file that was parsed, if
        any.
    @type descriptiveComment: C{str}

    @ivar schema: a reference to the L{Schema} to which this table belongs.

    @ivar primaryKey: a C{list} of L{Column} objects representing the primary
        key of this table, or C{None} if no primary key has been specified.
    """

    compareAttributes = "schema name".split()

    def __init__(self, schema, name):
        _checkstr(name)
        self.descriptiveComment = ""
        self.schema = schema
        self.name = name
        self.columns = []
        self.constraints = []
        self.schemaRows = []
        self.primaryKey = None
        self.schema.tables.append(self)


    def __repr__(self):
        return "<Table %r:%r>" % (self.name, self.columns)


    def compare(self, other):
        """
        Return the differences between two tables.

        @param other: the table to compare with
        @type other: L{Table}
        """

        results = []

        myColumns = dict([(item.name.lower(), item) for item in self.columns])
        otherColumns = dict([
            (item.name.lower(), item) for item in other.columns
        ])
        for item in set(myColumns.keys()) - set(otherColumns.keys()):
            results.append(
                "Table: %s, extra column: %s" % (self.name, myColumns[item].name,)
            )
        for item in set(otherColumns.keys()) - set(myColumns.keys()):
            results.append(
                "Table: %s, missing column: %s" % (self.name, otherColumns[item].name,)
            )

        for name in set(myColumns.keys()) & set(otherColumns.keys()):
            results.extend(myColumns[name].compare(otherColumns[name]))

        if not all([len(a.compare(b)) == 0 for a, b in zip(
            listIfNone(self.primaryKey),
            listIfNone(other.primaryKey),
        )]):
            results.append("Table: %s, mismatched primary key" % (self.name,))

        for myRow, otherRow in zip(self.schemaRows, other.schemaRows):
            myRows = dict([(column.name, value) for column, value in myRow.items()])
            otherRows = dict([(column.name, value) for column, value in otherRow.items()])
            if myRows != otherRows:
                results.append("Table: %s, mismatched schema rows: %s" % (self.name, myRows))

        # Compare psuedo-constraints - ones which include implicit primary key and unique
        # index items.
        diff_constraints = set(self.pseudoConstraints()) ^ set(other.pseudoConstraints())
        if diff_constraints:
            results.append("Table: %s, mismatched constraints: %s" % (self.name, diff_constraints))

        return results


    def columnNamed(self, name):
        """
        Retrieve a column from this table with a given name.

        @raise KeyError: if no such table exists.

        @return: a column

        @rtype: L{Column}
        """
        for column in self.columns:
            if column.name == name:
                return column
        raise KeyError("no such column: %r" % (name,))


    def addColumn(self, name, type, default=NO_DEFAULT, notNull=False, primaryKey=False):
        """
        A new column was parsed for this table.

        @param name: The unqualified name of the column.

        @type name: C{str}

        @param type: The L{SQLType} describing the column's type.
        """
        column = Column(self, name, type, default=default)
        self.columns.append(column)
        if notNull:
            self.tableConstraint(Constraint.NOT_NULL, [name])
        if primaryKey:
            self.primaryKey = [column]
        return column


    def tableConstraint(self, constraintType, columnNames):
        """
        This table is affected by a constraint.  (Should only be called during
        schema parsing.)

        @param constraintType: the type of constraint; either
            L{Constraint.NOT_NULL} or L{Constraint.UNIQUE}, currently.
        """
        affectsColumns = []
        for name in columnNames:
            affectsColumns.append(self.columnNamed(name))
        self.constraints.append(Constraint(constraintType, affectsColumns))


    def checkConstraint(self, protoExpression, name=None):
        """
        This table is affected by a C{check} constraint.  (Should only be
        called during schema parsing.)

        @param protoExpression: proto expression.
        """
        self.constraints.append(Check(protoExpression, name))


    def insertSchemaRow(self, values, columns=None):
        """
        A statically-defined row was inserted as part of the schema itself.
        This is used for tables that want to track static enumerations, for
        example, but want to be referred to by a foreign key in other tables
        for proper referential integrity.

        Append this data to this L{Table}'s L{Table.schemaRows}.

        (Should only be called during schema parsing.)

        @param values: a C{list} of data items, one for each column in this
            table's current list of L{Column}s.
        @param columns: a C{list} of column names to insert into. If C{None}
            then use all table columns.
        """
        row = {}
        columns = self.columns if columns is None else [self.columnNamed(name) for name in columns]
        for column, value in zip(columns, values):
            row[column] = value
        self.schemaRows.append(row)


    def addComment(self, comment):
        """
        Add a comment to C{descriptiveComment}.

        @param comment: some additional descriptive text
        @type comment: C{str}
        """
        self.descriptiveComment = comment


    def uniques(self):
        """
        Get the groups of unique columns for this L{Table}.

        @return: an iterable of C{list}s of C{Column}s which are unique within
            this table.
        """
        for constraint in self.constraints:
            if constraint.type is Constraint.UNIQUE:
                yield list(constraint.affectsColumns)


    def pseudoConstraints(self):
        """
        Get constraints and pseudo constraints (ones for implicit not null
        of a primary key or unique indexes).

        @return: an iterable of C{list}s of C{Constraints}s which are related to
            this table.
        """
        constraints = set(self.constraints)

        if self.primaryKey:
            for column in self.primaryKey:
                constraints.add(Constraint(Constraint.NOT_NULL, [column, ]))
            constraints.add(Constraint(Constraint.UNIQUE, self.primaryKey))

        for idx in self.schema.indexes:
            if idx.unique and idx.table is self:
                if self.primaryKey is None or idx.columns != self.primaryKey:
                    constraints.add(Constraint(Constraint.UNIQUE, idx.columns))

        return (constraint for constraint in constraints)



class Index(object):
    """
    An L{Index} is an SQL index.
    """

    def __init__(self, schema, name, table, unique=False):
        self.name = name
        self.table = table
        self.unique = unique
        self.columns = []
        schema.indexes.append(self)


    def addColumn(self, column):
        self.columns.append(column)



class PseudoIndex(object):
    """
    A class used to represent explicit and implicit indexes. An implicit index
    is one the DB creates for primary key and unique columns in a table. An
    explicit index is one created by a CREATE [UNIQUE] INDEX statement. Because
    the name of an implicit index is implementation-defined, instead we create
    a name based on the table name, uniqueness and column names.
    """

    def __init__(self, table, columns, unique=False):
        if unique:
            suffix = "-unique"
        else:
            suffix = ""

        self.name = (
            "%s%s:(%s)"
            % (table.name, suffix, ",".join([col.name for col in columns]))
        )
        self.table = table
        self.unique = unique
        self.columns = columns


    def compare(self, other):
        """
        Return the differences between two indexes.

        @param other: the index to compare with
        @type other: L{Index}
        """

        # Nothing to do as name comparison will catch differences
        return []



class Sequence(FancyEqMixin, object):
    """
    A sequence object.
    """

    compareAttributes = "name".split()

    def __init__(self, schema, name):
        _checkstr(name)
        self.name = name
        self.referringColumns = []
        schema.sequences.append(self)


    def __repr__(self):
        return "<Sequence %r>" % (self.name,)


    def compare(self, other):
        """
        Return the differences between two sequences.

        @param other: the sequence to compare with
        @type other: L{Sequence}
        """

        # TODO: figure out whether to compare referringColumns attribute
        return []



class Function(FancyEqMixin, object):
    """
    A function object.
    """

    compareAttributes = "name".split()

    def __init__(self, schema, name):
        _checkstr(name)
        self.name = name
        schema.functions.append(self)


    def __repr__(self):
        return "<Function %r>" % (self.name,)


    def compare(self, other):
        """
        Return the differences between two functions.

        @param other: the function to compare with
        @type other: L{Function}
        """

        # TODO: ought to compare function body but we don't track that
        return []



def _namedFrom(name, sequence):
    """
    Retrieve an item with a given name attribute from a given sequence, or
    raise a L{KeyError}.
    """
    for item in sequence:
        if item.name == name:
            return item
    raise KeyError(name)



class Schema(object):
    """
    A schema containing tables, indexes, and sequences.
    """

    def __init__(self, filename="<string>"):
        self.filename = filename
        self.tables = []
        self.indexes = []
        self.sequences = []
        self.functions = []


    def __repr__(self):
        return "<Schema %r>" % (self.filename,)


    def compare(self, other):
        """
        Return the differences between two schemas.

        @param other: the schema to compare with
        @type other: L{Schema}
        """

        results = []

        def _compareLists(list1, list2, descriptor):
            myItems = dict([(item.name.lower()[:63], item) for item in list1])
            otherItems = dict([
                (item.name.lower()[:63], item) for item in list2
            ])
            for item in set(myItems.keys()) - set(otherItems.keys()):
                results.append(
                    "Schema: %s, extra %s: %s"
                    % (other.filename, descriptor, myItems[item].name)
                )
            for item in set(otherItems.keys()) - set(myItems.keys()):
                results.append(
                    "Schema: %s, missing %s: %s"
                    % (self.filename, descriptor, otherItems[item].name)
                )

            for name in set(myItems.keys()) & set(otherItems.keys()):
                results.extend(myItems[name].compare(otherItems[name]))

        _compareLists(self.tables, other.tables, "table")
        _compareLists(self.pseudoIndexes(), other.pseudoIndexes(), "index")
        _compareLists(self.sequences, other.sequences, "sequence")
        _compareLists(self.functions, other.functions, "functions")

        return results


    def pseudoIndexes(self):
        """
        Return a set of indexes that include "implicit" indexes from
        table/column constraints. The name of the index is formed from the
        table name and then list of columns.
        """
        results = []

        # First add the list of explicit indexes we have
        for index in self.indexes:
            results.append(
                PseudoIndex(index.table, index.columns, index.unique)
            )

        # Now do implicit index for each table
        for table in self.tables:
            if table.primaryKey is not None:
                results.append(PseudoIndex(table, table.primaryKey, True))
            for constraint in table.constraints:
                if constraint.type == Constraint.UNIQUE:
                    results.append(
                        PseudoIndex(table, constraint.affectsColumns, True)
                    )

        return results


    def tableNamed(self, name):
        return _namedFrom(name, self.tables)


    def sequenceNamed(self, name):
        return _namedFrom(name, self.sequences)


    def indexNamed(self, name):
        return _namedFrom(name, self.indexes)


    def functionNamed(self, name):
        return _namedFrom(name, self.functions)
