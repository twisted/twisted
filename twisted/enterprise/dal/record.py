# -*- test-case-name: twext.enterprise.dal.test.test_record -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
RECORD: Relational Entity Creation from Objects Representing Data.

This is an asynchronous object-relational mapper based on
L{twext.enterprise.dal.syntax}.
"""

__all__ = [
    "ReadOnly",
    "NoSuchRecord",
    "fromTable",
    "Record",
]

from twisted.internet.defer import inlineCallbacks, returnValue
from twext.enterprise.dal.syntax import (
    Select, Tuple, Constant, ColumnSyntax, Insert, Update, Delete, SavepointAction
)
from twext.enterprise.util import parseSQLTimestamp
# from twext.enterprise.dal.syntax import ExpressionSyntax



class ReadOnly(AttributeError):
    """
    A caller attempted to set an attribute on a database-backed record, rather
    than updating it through L{Record.update}.
    """

    def __init__(self, className, attributeName):
        self.className = className
        self.attributeName = attributeName
        super(ReadOnly, self).__init__(
            "SQL-backed attribute '{0}.{1}' is read-only. "
            "Use '.update(...)' to modify attributes."
            .format(className, attributeName)
        )



class NoSuchRecord(Exception):
    """
    No matching record could be found.
    """



class _RecordMeta(type):
    """
    Metaclass for associating a L{fromTable} with a L{Record} at inheritance
    time.
    """

    def __new__(cls, name, bases, ns):
        """
        Create a new instance of this meta-type.
        """
        newbases = []
        table = None
        namer = None

        for base in bases:
            if isinstance(base, fromTable):
                if table is not None:
                    raise RuntimeError(
                        "Can't define a class from two or more tables at once."
                    )
                table = base.table
            elif getattr(base, "table", None) is not None:
                raise RuntimeError(
                    "Can't define a record class by inheriting one already "
                    "mapped to a table."
                    # TODO: more info
                )
            else:
                if namer is None:
                    if isinstance(base, _RecordMeta):
                        namer = base
                newbases.append(base)

        if table is not None:
            attrmap = {}
            colmap = {}
            allColumns = list(table)
            for column in allColumns:
                attrname = namer.namingConvention(column.model.name)
                attrmap[attrname] = column
                colmap[column] = attrname
            ns.update(table=table, __attrmap__=attrmap, __colmap__=colmap)
            ns.update(attrmap)

        return super(_RecordMeta, cls).__new__(cls, name, tuple(newbases), ns)



class fromTable(object):
    """
    Inherit from this after L{Record} to specify which table your L{Record}
    subclass is mapped to.
    """

    def __init__(self, aTable):
        """
        @param table: The table to map to.
        @type table: L{twext.enterprise.dal.syntax.TableSyntax}
        """
        self.table = aTable



class Record(object):
    """
    Superclass for all database-backed record classes.  (i.e.  an object mapped
    from a database record).

    @cvar table: the table that represents this L{Record} in the database.
    @type table: L{TableSyntax}

    @ivar transaction: The L{IAsyncTransaction} where this record is being
        loaded.  This may be C{None} if this L{Record} is not participating in
        a transaction, which may be true if it was instantiated but never
        saved.

    @cvar __colmap__: map of L{ColumnSyntax} objects to attribute names.
    @type __colmap__: L{dict}

    @cvar __attrmap__: map of attribute names to L{ColumnSyntax} objects.
    @type __attrmap__: L{dict}
    """

    __metaclass__ = _RecordMeta

    transaction = None

    def __setattr__(self, name, value):
        """
        Once the transaction is initialized, this object is immutable.  If you
        want to change it, use L{Record.update}.
        """
        if self.transaction is not None:
            raise ReadOnly(self.__class__.__name__, name)

        return super(Record, self).__setattr__(name, value)


    def __repr__(self):
        r = (
            "<{0} record from table {1}"
            .format(self.__class__.__name__, self.table.model.name)
        )
        for k in sorted(self.__attrmap__.keys()):
            r += " {0}={1}".format(k, repr(getattr(self, k)))
        r += ">"
        return r


    def __hash__(self):
        return hash(tuple([getattr(self, attr) for attr in self.__attrmap__.keys()]))


    def __eq__(self, other):
        if type(self) != type(other):
            return False
        attrs = dict([(attr, getattr(self, attr),) for attr in self.__attrmap__.keys()])
        otherattrs = dict([(attr, getattr(other, attr),) for attr in other.__attrmap__.keys()])
        return attrs == otherattrs


    @classmethod
    def fromTable(cls, table):
        """
        Initialize from a L{Table} at run time.

        @param table: table containing the record data
        @type table: L{Table}
        """
        cls.__attrmap__ = {}
        cls.__colmap__ = {}
        allColumns = list(table)
        for column in allColumns:
            attrname = cls.namingConvention(column.model.name)
            cls.__attrmap__[attrname] = column
            cls.__colmap__[column] = attrname


    @staticmethod
    def namingConvention(columnName):
        """
        Implement the convention for naming-conversion between column names
        (typically, upper-case database names map to lower-case attribute
        names).
        """
        words = columnName.lower().split("_")

        def cap(word):
            if word.lower() in ("id", "uid", "guid",):
                return word.upper()
            else:
                return word.capitalize()

        return words[0] + "".join(map(cap, words[1:]))


    @classmethod
    def _primaryKeyExpression(cls):
        return Tuple([ColumnSyntax(c) for c in cls.table.model.primaryKey])


    def _primaryKeyValue(self):
        val = []
        for col in self._primaryKeyExpression().columns:
            val.append(getattr(self, self.__class__.__colmap__[col]))
        return val


    @classmethod
    def _primaryKeyComparison(cls, primaryKey):
        return cls._primaryKeyExpression() == Tuple(map(Constant, primaryKey))


    @classmethod
    @inlineCallbacks
    def load(cls, transaction, *primaryKey):
        results = yield cls.query(
            transaction,
            cls._primaryKeyComparison(primaryKey)
        )
        if len(results) != 1:
            raise NoSuchRecord()
        else:
            returnValue(results[0])


    @classmethod
    @inlineCallbacks
    def create(cls, transaction, **k):
        """
        Create a row.

        Used like this::

            MyRecord.create(transaction, column1=1, column2=u"two")
        """
        self = cls.make(**k)
        yield self.insert(transaction)
        returnValue(self)


    @classmethod
    def make(cls, **k):
        """
        Make a record without creating one in the database - this will not have an
        associated L{transaction}. When the record is ready to be written to the database
        use L{SerializeableRecord.insert} to add it. Before it gets written to the DB, the
        attributes can be changed.
        """
        self = cls()
        attrtocol = cls.__attrmap__

        for attr in attrtocol:
            col = attrtocol[attr]
            if attr in k:
                value = k.pop(attr)
                setattr(self, attr, value)
            else:
                if col.model.needsValue():
                    raise TypeError(
                        "required attribute {0!r} not passed"
                        .format(attr)
                    )

        if k:
            raise TypeError("received unknown attribute{0}: {1}".format(
                "s" if len(k) > 1 else "", ", ".join(sorted(k))
            ))

        return self


    def duplicate(self):
        return self.make(**dict([(attr, getattr(self, attr),) for attr in self.__attrmap__.keys()]))


    def isnew(self):
        return self.transaction is None


    def _attributesFromRow(self, attributeList):
        """
        Take some data loaded from a row and apply it to this instance,
        converting types as necessary.

        @param attributeList: a C{list} of 2-C{tuples} of C{(attributeName,
            attributeValue)}.
        """
        for setAttribute, setValue in attributeList:
            setColumn = self.__attrmap__[setAttribute]
            if setColumn.model.type.name == "timestamp" and setValue is not None:
                setValue = parseSQLTimestamp(setValue)
            setattr(self, setAttribute, setValue)


    @inlineCallbacks
    def insert(self, transaction):
        """
        Insert a new a row for an existing record that was not initially created in the database.
        """

        # Cannot do this if a transaction has already been assigned because that means
        # the record already exists in the DB.

        if self.transaction is not None:
            raise ReadOnly(self.__class__.__name__, "Cannot insert")

        colmap = {}
        attrtocol = self.__attrmap__
        needsCols = []
        needsAttrs = []

        for attr in attrtocol:
            col = attrtocol[attr]
            v = getattr(self, attr)
            if not isinstance(v, ColumnSyntax):
                colmap[col] = v
            else:
                if col.model.needsValue():
                    raise TypeError(
                        "required attribute {0!r} not passed"
                        .format(attr)
                    )
                else:
                    needsCols.append(col)
                    needsAttrs.append(attr)

        result = yield (Insert(colmap, Return=needsCols if needsCols else None)
                        .on(transaction))
        if needsCols:
            self._attributesFromRow(zip(needsAttrs, result[0]))

        self.transaction = transaction


    def delete(self):
        """
        Delete this row from the database.

        @return: a L{Deferred} which fires with C{None} when the underlying row
            has been deleted, or fails with L{NoSuchRecord} if the underlying
            row was already deleted.
        """
        return Delete(
            From=self.table,
            Where=self._primaryKeyComparison(self._primaryKeyValue())
        ).on(self.transaction, raiseOnZeroRowCount=NoSuchRecord)


    @inlineCallbacks
    def update(self, **kw):
        """
        Modify the given attributes in the database.

        @return: a L{Deferred} that fires when the updates have been sent to
            the database.
        """
        colmap = {}
        for k, v in kw.iteritems():
            colmap[self.__attrmap__[k]] = v

        yield Update(
            colmap,
            Where=self._primaryKeyComparison(self._primaryKeyValue())
        ).on(self.transaction)

        self.__dict__.update(kw)


    @inlineCallbacks
    def lock(self, where=None):
        """
        Lock with a select for update.

        @param where: SQL expression used to match the rows to lock, by default this is just an expression
            that matches the primary key of this L{Record}, but it can be used to lock multiple L{Records}
            matching the expression in one go. If it is an L{str}, then all rows will be matched.
        @type where: L{SQLExpression} or L{None}
        @return: a L{Deferred} that fires when the lock has been acquired.
        """
        if where is None:
            where = self._primaryKeyComparison(self._primaryKeyValue())
        elif isinstance(where, str):
            where = None
        yield Select(
            list(self.table),
            From=self.table,
            Where=where,
            ForUpdate=True,
        ).on(self.transaction)


    @inlineCallbacks
    def trylock(self, where=None):
        """
        Try to lock with a select for update no wait. If it fails, rollback to
        a savepoint and return L{False}, else return L{True}.

        @param where: SQL expression used to match the rows to lock, by default this is just an expression
            that matches the primary key of this L{Record}, but it can be used to lock multiple L{Records}
            matching the expression in one go. If it is an L{str}, then all rows will be matched.
        @type where: L{SQLExpression} or L{None}
        @return: a L{Deferred} that fires when the updates have been sent to
            the database.
        """

        if where is None:
            where = self._primaryKeyComparison(self._primaryKeyValue())
        elif isinstance(where, str):
            where = None
        savepoint = SavepointAction("Record_trylock_{}".format(self.__class__.__name__))
        yield savepoint.acquire(self.transaction)
        try:
            yield Select(
                list(self.table),
                From=self.table,
                Where=where,
                ForUpdate=True,
                NoWait=True,
            ).on(self.transaction)
        except:
            yield savepoint.rollback(self.transaction)
            returnValue(False)
        else:
            yield savepoint.release(self.transaction)
            returnValue(True)


    @classmethod
    def pop(cls, transaction, *primaryKey):
        """
        Atomically retrieve and remove a row from this L{Record}'s table
        with a primary key value of C{primaryKey}.

        @return: a L{Deferred} that fires with an instance of C{cls}, or fails
            with L{NoSuchRecord} if there were no records in the database.
        @rtype: L{Deferred}
        """
        return cls._rowsFromQuery(
            transaction,
            Delete(
                Where=cls._primaryKeyComparison(primaryKey),
                From=cls.table,
                Return=list(cls.table)
            ),
            lambda: NoSuchRecord()
        ).addCallback(lambda x: x[0])


    @classmethod
    def query(cls, transaction, expr, order=None, group=None, limit=None, forUpdate=False, noWait=False, ascending=True, distinct=False):
        """
        Query the table that corresponds to C{cls}, and return instances of
        C{cls} corresponding to the rows that are returned from that table.

        @param expr: An L{ExpressionSyntax} that constraints the results of the
            query.  This is most easily produced by accessing attributes on the
            class; for example, C{MyRecordType.query((MyRecordType.col1 >
            MyRecordType.col2).And(MyRecordType.col3 == 7))}

        @param order: A L{ColumnSyntax} to order the resulting record objects
            by.

        @param ascending: A boolean; if C{order} is not C{None}, whether to
            sort in ascending or descending order.

        @param group: a L{ColumnSyntax} to group the resulting record objects
            by.

        @param forUpdate: do a SELECT ... FOR UPDATE
        @type forUpdate: L{bool}
        @param noWait: include NOWAIT with the FOR UPDATE
        @type noWait: L{bool}
        """
        return cls._rowsFromQuery(
            transaction,
            cls.queryExpr(
                expr,
                order=order,
                group=group,
                limit=limit,
                forUpdate=forUpdate,
                noWait=noWait,
                ascending=ascending,
                distinct=distinct,
            ),
            None
        )


    @classmethod
    def queryExpr(cls, expr, attributes=None, order=None, group=None, limit=None, forUpdate=False, noWait=False, ascending=True, distinct=False):
        """
        Query expression that corresponds to C{cls}. Used in cases where a sub-select
        on this record's table is needed.

        @param expr: An L{ExpressionSyntax} that constraints the results of the
            query.  This is most easily produced by accessing attributes on the
            class; for example, C{MyRecordType.query((MyRecordType.col1 >
            MyRecordType.col2).And(MyRecordType.col3 == 7))}

        @param order: A L{ColumnSyntax} to order the resulting record objects
            by.

        @param ascending: A boolean; if C{order} is not C{None}, whether to
            sort in ascending or descending order.

        @param group: a L{ColumnSyntax} to group the resulting record objects
            by.

        @param forUpdate: do a SELECT ... FOR UPDATE
        @type forUpdate: L{bool}
        @param noWait: include NOWAIT with the FOR UPDATE
        @type noWait: L{bool}
        """
        kw = {}
        if order is not None:
            kw.update(OrderBy=order, Ascending=ascending)
        if group is not None:
            kw.update(GroupBy=group)
        if limit is not None:
            kw.update(Limit=limit)
        if forUpdate:
            kw.update(ForUpdate=True)
            if noWait:
                kw.update(NoWait=True)
        if distinct:
            kw.update(Distinct=True)
        if attributes is None:
            attributes = list(cls.table)
        return Select(
            attributes,
            From=cls.table,
            Where=expr,
            **kw
        )


    @classmethod
    def querysimple(cls, transaction, **kw):
        """
        Match all rows matching the specified attribute/values from the table that corresponds to C{cls}.
        All attributes are logically AND'ed.
        """
        where = None
        for k, v in kw.iteritems():
            subexpr = (cls.__attrmap__[k] == v)
            if where is None:
                where = subexpr
            else:
                where = where.And(subexpr)
        return cls.query(transaction, where)


    @classmethod
    def all(cls, transaction):
        """
        Load all rows from the table that corresponds to C{cls} and return
        instances of C{cls} corresponding to all.
        """
        return cls._rowsFromQuery(
            transaction,
            Select(
                list(cls.table),
                From=cls.table,
                OrderBy=cls._primaryKeyExpression()
            ),
            None
        )


    @classmethod
    def updatesome(cls, transaction, where, **kw):
        """
        Update rows matching the where expression from the table that corresponds to C{cls}.
        """
        colmap = {}
        for k, v in kw.iteritems():
            colmap[cls.__attrmap__[k]] = v

        return Update(
            colmap,
            Where=where
        ).on(transaction)


    @classmethod
    def deleteall(cls, transaction):
        """
        Delete all rows from the table that corresponds to C{cls}.
        """
        return cls.deletesome(transaction, None)


    @classmethod
    def deletesome(cls, transaction, where, returnCols=None):
        """
        Delete all rows matching the where expression from the table that corresponds to C{cls}.
        """
        return Delete(
            From=cls.table,
            Where=where,
            Return=returnCols,
        ).on(transaction)


    @classmethod
    def deletesimple(cls, transaction, **kw):
        """
        Delete all rows matching the specified attribute/values from the table that corresponds to C{cls}.
        All attributes are logically AND'ed.
        """
        where = None
        for k, v in kw.iteritems():
            subexpr = (cls.__attrmap__[k] == v)
            if where is None:
                where = subexpr
            else:
                where = where.And(subexpr)
        return cls.deletesome(transaction, where)


    @classmethod
    @inlineCallbacks
    def _rowsFromQuery(cls, transaction, qry, rozrc):
        """
        Execute the given query, and transform its results into instances of
        C{cls}.

        @param transaction: an L{IAsyncTransaction} to execute the query on.

        @param qry: a L{_DMLStatement} (XXX: maybe _DMLStatement or some
            interface that defines "on" should be public?) whose results are
            the list of columns in C{self.table}.

        @param rozrc: The C{raiseOnZeroRowCount} argument.

        @return: a L{Deferred} that succeeds with a C{list} of instances of
            C{cls} or fails with an exception produced by C{rozrc}.
        """
        rows = yield qry.on(transaction, raiseOnZeroRowCount=rozrc)
        selves = []
        names = [cls.__colmap__[column] for column in list(cls.table)]
        for row in rows:
            self = cls()
            self._attributesFromRow(zip(names, row))
            self.transaction = transaction
            selves.append(self)
        returnValue(selves)



class SerializableRecord(Record):
    """
    An L{Record} that serializes/deserializes its attributes for a text-based
    transport (e.g., JSON-over-HTTP) to allow records to be transferred from
    one system to another (with potentially mismatched schemas).
    """

    def serialize(self):
        """
        Create an L{dict} of each attribute with L{str} values for each attribute
        value. Sub-classes may need to override this to specialize certain value
        conversions.

        @return: mapping of attribute to string values
        @rtype: L{dict} of L{str}:L{str}
        """

        # Certain values have to be mapped to str
        result = {}
        for attr in self.__attrmap__:
            value = getattr(self, attr)
            col = self.__attrmap__[attr]
            if col.model.type.name == "timestamp" and value is not None:
                value = str(value)
            result[attr] = value
        return result


    @classmethod
    def deserialize(cls, attrmap):
        """
        Given an L{dict} mapping attributes to values, create an L{Record} with
        the specified values. Sub-classes may need to override this to handle special
        values that need to be converted to specific types. They also need to override
        this to handle possible schema mismatches (attributes no longer used, new
        attributes not present in the map).

        @param attrmap: serialized representation of a record
        @type attrmap: L{dict} of L{str}:L{str}

        @return: a newly created, but not inserted, record
        @rtype: L{SerializableRecord}
        """

        # Certain values have to be mapped to non-str types
        mapped = {}
        for attr in attrmap:
            value = attrmap[attr]
            col = cls.__attrmap__[attr]
            if col.model.type.name == "timestamp" and value is not None:
                value = parseSQLTimestamp(value)
            mapped[attr] = value

        record = cls.make(**mapped)
        return record
