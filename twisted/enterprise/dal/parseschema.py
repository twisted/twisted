# -*- test-case-name: twext.enterprise.dal.test.test_parseschema -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.
from __future__ import print_function

"""
Parser for SQL schema.
"""

__all__ = [
    "tableFromCreateStatement",
    "schemaFromPath",
    "schemaFromString",
    "addSQLToSchema",
    "ViolatedExpectation",
    "nameOrIdentifier",
    "expectSingle",
    "expect",
    "significant",
    "iterSignificant",
]

from itertools import chain
from re import compile

from sqlparse import parse, keywords
from sqlparse.tokens import (
    Keyword, Punctuation, Number, String, Name, Comparison as CompTok
)
from sqlparse.sql import (Comment, Identifier, Parenthesis, IdentifierList,
                          Function, Comparison)

from twext.enterprise.dal.model import (
    Schema, Table, SQLType, ProcedureCall, Constraint, Sequence, Index, Function as FunctionModel)

from twext.enterprise.dal.syntax import (
    ColumnSyntax, CompoundComparison, Constant, Function as FunctionSyntax
)



def _fixKeywords():
    """
    Work around bugs in SQLParse, adding SEQUENCE as a keyword (since it is
    treated as one in postgres) and removing ACCESS and SIZE (since we use
    those as column names).  Technically those are keywords in SQL, but they
    aren't treated as such by postgres's parser.
    """
    keywords.KEYWORDS["SEQUENCE"] = Keyword
    for columnNameKeyword in ["ACCESS", "SIZE"]:
        del keywords.KEYWORDS[columnNameKeyword]

_fixKeywords()



def tableFromCreateStatement(schema, stmt):
    """
    Add a table from a CREATE TABLE sqlparse statement object.

    @param schema: The schema to add the table statement to.
    @type schema: L{Schema}

    @param stmt: The C{CREATE TABLE} statement object.
    @type stmt: L{Statement}
    """
    i = iterSignificant(stmt)
    expect(i, ttype=Keyword.DDL, value="CREATE")
    expect(i, ttype=Keyword, value="TABLE")
    function = expect(i, cls=Function)
    i = iterSignificant(function)
    name = expect(i, cls=Identifier).get_name().encode("utf-8")
    self = Table(schema, name)
    parens = expect(i, cls=Parenthesis)
    cp = _ColumnParser(self, iterSignificant(parens), parens)
    cp.parse()
    return self



def schemaFromPath(path):
    """
    Get a L{Schema}.

    @param path: a L{FilePath}-like object containing SQL.

    @return: a L{Schema} object with the contents of the given C{path} parsed
        and added to it as L{Table} objects.
    """
    schema = Schema(path.basename())
    schemaData = path.getContent()
    addSQLToSchema(schema, schemaData)
    return schema



def schemaFromString(data):
    """
    Get a L{Schema}.

    @param data: a C{str} containing SQL.

    @return: a L{Schema} object with the contents of the given C{str} parsed
        and added to it as L{Table} objects.
    """
    schema = Schema()
    addSQLToSchema(schema, data)
    return schema



def addSQLToSchema(schema, schemaData):
    """
    Add new SQL to an existing schema.

    @param schema: The schema to add the new SQL to.
    @type schema: L{Schema}

    @param schemaData: A string containing some SQL statements.
    @type schemaData: C{str}

    @return: the C{schema} argument
    """
    parsed = parse(schemaData)

    for stmt in parsed:
        preface = ""

        while stmt.tokens and not significant(stmt.tokens[0]):
            preface += str(stmt.tokens.pop(0))

        if not stmt.tokens:
            continue

        if stmt.get_type() == "CREATE":
            createType = stmt.token_next(1, True).value.upper()

            if createType == u"TABLE":
                t = tableFromCreateStatement(schema, stmt)
                t.addComment(preface)

            elif createType == u"SEQUENCE":
                Sequence(
                    schema,
                    stmt.token_next(2, True).get_name().encode("utf-8")
                )

            elif createType in (u"INDEX", u"UNIQUE"):
                signifindex = iterSignificant(stmt)
                expect(signifindex, ttype=Keyword.DDL, value="CREATE")
                token = signifindex.next()
                unique = False

                if token.match(Keyword, "UNIQUE"):
                    unique = True
                    token = signifindex.next()

                if not token.match(Keyword, "INDEX"):
                    raise ViolatedExpectation("INDEX or UNQIUE", token.value)

                indexName = nameOrIdentifier(signifindex.next())
                expect(signifindex, ttype=Keyword, value="ON")
                token = signifindex.next()

                if isinstance(token, Function):
                    [tableName, columnArgs] = iterSignificant(token)
                else:
                    tableName = token
                    token = signifindex.next()

                    if token.match(Keyword, "USING"):
                        [_ignore, columnArgs] = iterSignificant(
                            expect(signifindex, cls=Function)
                        )
                    else:
                        raise ViolatedExpectation("USING", token)

                tableName = nameOrIdentifier(tableName)
                arggetter = iterSignificant(columnArgs)

                expect(arggetter, ttype=Punctuation, value=u"(")
                valueOrValues = arggetter.next()

                if isinstance(valueOrValues, IdentifierList):
                    valuelist = valueOrValues.get_identifiers()
                else:
                    valuelist = [valueOrValues]

                expect(arggetter, ttype=Punctuation, value=u")")

                idx = Index(
                    schema, indexName, schema.tableNamed(tableName), unique
                )

                for token in valuelist:
                    columnName = nameOrIdentifier(token)
                    idx.addColumn(idx.table.columnNamed(columnName))

            elif createType == u"FUNCTION":
                parseFunction(schema, stmt)

        elif stmt.get_type() == "INSERT":
            insertTokens = iterSignificant(stmt)
            expect(insertTokens, ttype=Keyword.DML, value="INSERT")
            expect(insertTokens, ttype=Keyword, value="INTO")

            token = insertTokens.next()

            if isinstance(token, Function):
                [tableName, columnArgs] = iterSignificant(token)
                tableName = tableName.get_name()
                columns = namesInParens(columnArgs)
            else:
                tableName = token.get_name()
                columns = None

            expect(insertTokens, ttype=Keyword, value="VALUES")

            values = expect(insertTokens, cls=Parenthesis)
            vals = iterSignificant(values)
            expect(vals, ttype=Punctuation, value="(")

            valuelist = expect(vals, cls=IdentifierList)
            expect(vals, ttype=Punctuation, value=")")

            rowData = []

            for ident in valuelist.get_identifiers():
                rowData.append(
                    {Number.Integer: int,
                     String.Single: _destringify}
                    [ident.ttype](ident.value)
                )

            schema.tableNamed(tableName).insertSchemaRow(rowData, columns=columns)

        elif stmt.get_type() == "CREATE OR REPLACE":
            createType = stmt.token_next(1, True).value.upper()

            if createType == u"FUNCTION":
                parseFunction(schema, stmt)

        else:
            print("unknown type:", stmt.get_type())

    return schema



def parseFunction(schema, stmt):
    """
    A FUNCTION may or may not have an argument list, so we need to account for
    both possibilities.
    """
    fn_name = stmt.token_next(2, True)
    if isinstance(fn_name, Function):
        [fn_name, _ignore_args] = iterSignificant(fn_name)
        fn_name = fn_name.get_name()
    else:
        fn_name = fn_name.get_name()

    FunctionModel(
        schema,
        fn_name.encode("utf-8"),
    )



class _ColumnParser(object):
    """
    Stateful parser for the things between commas.
    """

    def __init__(self, table, parenIter, parens):
        """
        @param table: the L{Table} to add data to.

        @param parenIter: the iterator.
        """
        self.parens = parens
        self.iter = parenIter
        self.table = table


    def __iter__(self):
        """
        This object is an iterator; return itself.
        """
        return self


    def next(self):
        """
        Get the next L{IdentifierList}.
        """
        result = self.iter.next()
        if isinstance(result, IdentifierList):
            # Expand out all identifier lists, since they seem to pop up
            # incorrectly.  We should never see one in a column list anyway.
            # http://code.google.com/p/python-sqlparse/issues/detail?id=25
            while result.tokens:
                it = result.tokens.pop()
                if significant(it):
                    self.pushback(it)
            return self.next()
        return result


    def pushback(self, value):
        """
        Push the value back onto this iterator so it will be returned by the
        next call to C{next}.
        """
        self.iter = chain(iter((value,)), self.iter)


    def parse(self):
        """
        Parse everything.
        """
        expect(self.iter, ttype=Punctuation, value=u"(")
        while self.nextColumn():
            pass


    def nextColumn(self):
        """
        Parse the next column or constraint, depending on the next token.
        """
        maybeIdent = self.next()
        if maybeIdent.ttype == Name:
            return self.parseColumn(maybeIdent.value)
        elif isinstance(maybeIdent, Identifier):
            return self.parseColumn(maybeIdent.get_name())
        else:
            return self.parseConstraint(maybeIdent)


    def readExpression(self, parens):
        """
        Read a given expression from a Parenthesis object.  (This is currently
        a limited parser in support of simple CHECK constraints, not something
        suitable for a full WHERE Clause.)
        """
        parens = iterSignificant(parens)
        expect(parens, ttype=Punctuation, value="(")
        nexttok = parens.next()

        if isinstance(nexttok, Comparison):
            lhs, op, rhs = list(iterSignificant(nexttok))
            result = CompoundComparison(
                self.nameOrValue(lhs),
                op.value.encode("ascii"),
                self.nameOrValue(rhs)
            )

        elif isinstance(nexttok, Identifier):
            # our version of SQLParse seems to break down and not create a nice
            # "Comparison" object when a keyword is present.  This is just a
            # simple workaround.
            lhs = self.nameOrValue(nexttok)
            op = expect(parens, ttype=CompTok).value.encode("ascii")
            funcName = expect(parens, ttype=Keyword).value.encode("ascii")
            rhs = FunctionSyntax(funcName)(*[
                ColumnSyntax(self.table.columnNamed(x)) for x in
                namesInParens(expect(parens, cls=Parenthesis))
            ])
            result = CompoundComparison(lhs, op, rhs)

        expect(parens, ttype=Punctuation, value=")")
        return result


    def nameOrValue(self, tok):
        """
        Inspecting a token present in an expression (for a CHECK constraint on
        this table), return a L{twext.enterprise.dal.syntax} object for that
        value.
        """
        if isinstance(tok, Identifier):
            return ColumnSyntax(self.table.columnNamed(tok.get_name()))
        elif tok.ttype == Number.Integer:
            return Constant(int(tok.value))


    def parseConstraint(self, constraintType):
        """
        Parse a C{free} constraint, described explicitly in the table as
        opposed to being implicitly associated with a column by being placed
        after it.
        """
        ident = None
        # TODO: make use of identifier in tableConstraint, currently only used
        # for checkConstraint.
        if constraintType.match(Keyword, "CONSTRAINT"):
            ident = expect(self, cls=Identifier).get_name()
            constraintType = expect(self, ttype=Keyword)

        if constraintType.match(Keyword, "PRIMARY"):
            expect(self, ttype=Keyword, value="KEY")
            names = namesInParens(expect(self, cls=Parenthesis))
            self.table.primaryKey = [self.table.columnNamed(n) for n in names]
        elif constraintType.match(Keyword, "UNIQUE"):
            names = namesInParens(expect(self, cls=Parenthesis))
            self.table.tableConstraint(Constraint.UNIQUE, names)
        elif constraintType.match(Keyword, "CHECK"):
            self.table.checkConstraint(self.readExpression(self.next()), ident)
        else:
            raise ViolatedExpectation("PRIMARY or UNIQUE", constraintType)

        return self.checkEnd(self.next())


    def checkEnd(self, val):
        """
        After a column or constraint, check the end.
        """
        if val.value == u",":
            return True
        elif val.value == u")":
            return False
        else:
            raise ViolatedExpectation(", or )", val)


    def parseColumn(self, name):
        """
        Parse a column with the given name.
        """
        typeName = self.next()
        if isinstance(typeName, Function):
            [funcIdent, args] = iterSignificant(typeName)
            typeName = funcIdent
            arggetter = iterSignificant(args)
            expect(arggetter, value=u"(")
            typeLength = int(
                expect(
                    arggetter,
                    ttype=Number.Integer
                ).value.encode("utf-8")
            )
        else:
            maybeTypeArgs = self.next()
            if isinstance(maybeTypeArgs, Parenthesis):
                # type arguments
                significant = iterSignificant(maybeTypeArgs)
                expect(significant, value=u"(")
                typeLength = int(significant.next().value)
            else:
                # something else
                typeLength = None
                self.pushback(maybeTypeArgs)

        theType = SQLType(typeName.value.encode("utf-8"), typeLength)
        theColumn = self.table.addColumn(
            name=name.encode("utf-8"), type=theType
        )

        for val in self:
            if val.ttype == Punctuation:
                return self.checkEnd(val)
            else:
                expected = True

                def oneConstraint(t):
                    self.table.tableConstraint(t, [theColumn.name])

                if val.match(Keyword, "PRIMARY"):
                    expect(self, ttype=Keyword, value="KEY")
                    # XXX check to make sure there's no other primary key yet
                    self.table.primaryKey = [theColumn]

                elif val.match(Keyword, "UNIQUE"):
                    # XXX add UNIQUE constraint
                    oneConstraint(Constraint.UNIQUE)

                elif val.match(Keyword, "NOT"):
                    # possibly not necessary, as "NOT NULL" is a single keyword
                    # in sqlparse as of 0.1.2
                    expect(self, ttype=Keyword, value="NULL")
                    oneConstraint(Constraint.NOT_NULL)

                elif val.match(Keyword, "NOT NULL"):
                    oneConstraint(Constraint.NOT_NULL)

                elif val.match(Keyword, "CHECK"):
                    self.table.checkConstraint(
                        self.readExpression(self.next())
                    )

                elif val.match(Keyword, "DEFAULT"):
                    theDefault = self.next()

                    if isinstance(theDefault, Parenthesis):
                        iDefault = iterSignificant(theDefault)
                        expect(iDefault, ttype=Punctuation, value="(")
                        theDefault = iDefault.next()

                    if isinstance(theDefault, Function):
                        thingo = theDefault.tokens[0].get_name()
                        parens = expectSingle(
                            theDefault.tokens[-1], cls=Parenthesis
                        )
                        pareniter = iterSignificant(parens)
                        if thingo.upper() == "NEXTVAL":
                            expect(pareniter, ttype=Punctuation, value="(")
                            seqname = _destringify(
                                expect(pareniter, ttype=String.Single).value
                            )
                            defaultValue = self.table.schema.sequenceNamed(
                                seqname
                            )
                            defaultValue.referringColumns.append(theColumn)
                        else:
                            defaultValue = ProcedureCall(
                                thingo.encode("utf-8"), namesInParens(parens),
                            )

                    elif theDefault.ttype == Number.Integer:
                        defaultValue = int(theDefault.value)

                    elif (
                        theDefault.ttype == Keyword and
                        theDefault.value.lower() == "false"
                    ):
                        defaultValue = False

                    elif (
                        theDefault.ttype == Keyword and
                        theDefault.value.lower() == "true"
                    ):
                        defaultValue = True

                    elif (
                        theDefault.ttype == Keyword and
                        theDefault.value.lower() == "null"
                    ):
                        defaultValue = None

                    elif theDefault.ttype == String.Single:
                        defaultValue = _destringify(theDefault.value)

                    # Oracle format for current timestamp mapped to postgres variant
                    elif (
                        theDefault.ttype == Keyword and
                        theDefault.value.lower() == "current_timestamp"
                    ):
                        expect(self, ttype=Keyword, value="at")
                        expect(self, ttype=None, value="time")
                        expect(self, ttype=None, value="zone")
                        expect(self, ttype=String.Single, value="'UTC'")
                        defaultValue = ProcedureCall("timezone", [u"UTC", u"CURRENT_TIMESTAMP"])

                    else:
                        raise RuntimeError(
                            "not sure what to do: default %r"
                            % (theDefault,)
                        )

                    theColumn.setDefaultValue(defaultValue)

                elif val.match(Keyword, "REFERENCES"):
                    target = nameOrIdentifier(self.next())
                    theColumn.doesReferenceName(target)

                elif val.match(Keyword, "ON"):
                    expect(self, ttype=Keyword.DML, value="DELETE")
                    refAction = self.next()

                    if (
                        refAction.ttype == Keyword and
                        refAction.value.upper() == "CASCADE"
                    ):
                        theColumn.deleteAction = "cascade"

                    elif (
                        refAction.ttype == Keyword and
                        refAction.value.upper() == "SET"
                    ):
                        setAction = self.next()

                        if (
                            setAction.ttype == Keyword and
                            setAction.value.upper() == "NULL"
                        ):
                            theColumn.deleteAction = "set null"

                        elif (
                            setAction.ttype == Keyword and
                            setAction.value.upper() == "DEFAULT"
                        ):
                            theColumn.deleteAction = "set default"

                        else:
                            raise RuntimeError(
                                "Invalid on delete set %r"
                                % (setAction.value,)
                            )

                    else:
                        raise RuntimeError(
                            "Invalid on delete %r"
                            % (refAction.value,)
                        )

                else:
                    expected = False

                if not expected:
                    print("UNEXPECTED TOKEN:", repr(val), theColumn)
                    print(self.parens)
                    import pprint
                    pprint.pprint(self.parens.tokens)
                    return 0



class ViolatedExpectation(Exception):
    """
    An expectation about the structure of the SQL syntax was violated.
    """

    def __init__(self, expected, got):
        self.expected = expected
        self.got = got
        super(ViolatedExpectation, self).__init__(
            "Expected %r got %s" % (expected, got)
        )



def nameOrIdentifier(token):
    """
    Determine if the given object is a name or an identifier, and return the
    textual value of that name or identifier.

    @rtype: L{str}
    """
    if isinstance(token, Identifier):
        return token.get_name()
    elif token.ttype == Name:
        return token.value
    elif token.ttype == String.Single:
        return _destringify(token.value)
    elif token.ttype == Keyword:
        return token.value
    else:
        raise ViolatedExpectation("identifier or name", repr(token))



def namesInParens(parens):
    parens = iterSignificant(parens)
    expect(parens, ttype=Punctuation, value="(")
    idorids = parens.next()

    if isinstance(idorids, Identifier):
        idnames = [idorids.get_name()]
    elif isinstance(idorids, IdentifierList):
        idnames = [nameOrIdentifier(x) for x in idorids.get_identifiers()]
    elif idorids.ttype == String.Single:
        idnames = [nameOrIdentifier(idorids)]
    else:
        expectSingle(idorids, ttype=Punctuation, value=")")
        return []

    expect(parens, ttype=Punctuation, value=")")
    return idnames



def expectSingle(nextval, ttype=None, value=None, cls=None):
    """
    Expect some properties from retrieved value.

    @param ttype: A token type to compare against.

    @param value: A value to compare against.

    @param cls: A class to check if the value is an instance of.

    @raise ViolatedExpectation: if an unexpected token is found.

    @return: C{nextval}, if it matches.
    """
    if ttype is not None:
        if nextval.ttype != ttype:
            raise ViolatedExpectation(
                ttype, "%s:%r" % (nextval.ttype, nextval)
            )
    if value is not None:
        if nextval.value.upper() != value.upper():
            raise ViolatedExpectation(value, nextval.value)
    if cls is not None:
        if nextval.__class__ != cls:
            raise ViolatedExpectation(
                cls, "%s:%r" % (nextval.__class__.__name__, nextval)
            )
    return nextval



def expect(iterator, **kw):
    """
    Retrieve a value from an iterator and check its properties.  Same signature
    as L{expectSingle}, except it takes an iterator instead of a value.

    @see: L{expectSingle}
    """
    nextval = iterator.next()
    return expectSingle(nextval, **kw)



def significant(token):
    """
    Determine if the token is "significant", i.e. that it is not a comment and
    not whitespace.
    """
    # comment has None is_whitespace() result.  intentional?
    return (not isinstance(token, Comment) and not token.is_whitespace())



def iterSignificant(tokenList):
    """
    Iterate tokens that pass the test given by L{significant}, from a given
    L{TokenList}.
    """
    for token in tokenList.tokens:
        if significant(token):
            yield token



def _destringify(strval):
    """
    Convert a single-quoted SQL string into its actual repsresented value.
    (Assumes standards compliance, since we should be controlling all the input
    here.  The only quoting syntax respected is "''".)
    """
    return strval[1:-1].replace("''", "'")



def splitSQLString(sqlString):
    """
    Strings which mix zero or more sql statements with zero or more pl/sql
    statements need to be split into individual sql statements for execution.
    This function was written to allow execution of pl/sql during Oracle schema
    upgrades.
    """
    aggregated = ''
    inPlSQL = None
    parsed = parse(sqlString)
    for stmt in parsed:
        while stmt.tokens and not significant(stmt.tokens[0]):
            stmt.tokens.pop(0)
        if not stmt.tokens:
            continue
        if inPlSQL is not None:
            agg = str(stmt).strip()
            if "end;".lower() in agg.lower():
                inPlSQL = None
                aggregated += agg
                rex = compile("\n +")
                aggregated = rex.sub('\n', aggregated)
                yield aggregated.strip()
                continue
            aggregated += agg
            continue
        if inPlSQL is None:
            # if 'begin'.lower() in str(stmt).split()[0].lower():
            if str(stmt).lower().strip().startswith('begin'):
                inPlSQL = True
                aggregated += str(stmt)
                continue
        else:
            continue
        yield str(stmt).rstrip().rstrip(";")
