# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Test cases for L{twext.enterprise.dal.record}.
"""

import datetime

from twisted.internet.defer import inlineCallbacks, gatherResults, returnValue
from twisted.trial.unittest import TestCase, SkipTest

from twext.enterprise.dal.record import (
    Record, fromTable, ReadOnly, NoSuchRecord,
    SerializableRecord)
from twext.enterprise.dal.test.test_parseschema import SchemaTestHelper
from twext.enterprise.dal.syntax import SchemaSyntax
from twext.enterprise.fixtures import buildConnectionPool

# from twext.enterprise.dal.syntax import


sth = SchemaTestHelper()
sth.id = lambda: __name__
schemaString = """
create table ALPHA (BETA integer primary key, GAMMA text);
create table DELTA (PHI integer primary key default (nextval('myseq')),
                    EPSILON text not null,
                    ZETA timestamp not null default '2012-12-12 12:12:12' );
"""

# sqlite can be made to support nextval() as a function, but 'create sequence'
# is syntax and can't.
parseableSchemaString = """
create sequence myseq;
""" + schemaString

try:
    testSchema = SchemaSyntax(sth.schemaFromString(parseableSchemaString))
except SkipTest as e:
    Alpha = Delta = object
    skip = e
else:
    Alpha = fromTable(testSchema.ALPHA)
    Delta = fromTable(testSchema.DELTA)
    skip = False



class TestRecord(Record, Alpha):
    """
    A sample test record.
    """



class TestSerializeRecord(SerializableRecord, Alpha):
    """
    A sample test serializable record with default values specified.
    """



class TestAutoRecord(Record, Delta):
    """
    A sample test record with default values specified.
    """



class TestCRUD(TestCase):
    """
    Tests for creation, mutation, and deletion operations.
    """

    def setUp(self):
        self.pool = buildConnectionPool(self, schemaString)


    @inlineCallbacks
    def test_simpleLoad(self):
        """
        Loading an existing row from the database by its primary key will
        populate its attributes from columns of the corresponding row in the
        database.
        """
        txn = self.pool.connection()
        yield txn.execSQL("insert into ALPHA values (:1, :2)", [234, "one"])
        yield txn.execSQL("insert into ALPHA values (:1, :2)", [456, "two"])

        rec = yield TestRecord.load(txn, 456)
        self.assertIsInstance(rec, TestRecord)
        self.assertEquals(rec.beta, 456)
        self.assertEquals(rec.gamma, "two")

        rec2 = yield TestRecord.load(txn, 234)
        self.assertIsInstance(rec2, TestRecord)
        self.assertEqual(rec2.beta, 234)
        self.assertEqual(rec2.gamma, "one")


    @inlineCallbacks
    def test_missingLoad(self):
        """
        Try loading an row which doesn't exist
        """
        txn = self.pool.connection()
        yield txn.execSQL("insert into ALPHA values (:1, :2)", [234, "one"])
        yield self.assertFailure(TestRecord.load(txn, 456), NoSuchRecord)


    @inlineCallbacks
    def test_simpleCreate(self):
        """
        When a record object is created, a row with matching column values will
        be created in the database.
        """
        txn = self.pool.connection()

        rec = yield TestRecord.create(txn, beta=3, gamma=u'epsilon')
        self.assertEquals(rec.beta, 3)
        self.assertEqual(rec.gamma, u'epsilon')

        rows = yield txn.execSQL("select BETA, GAMMA from ALPHA")
        self.assertEqual(rows, [tuple([3, u'epsilon'])])


    @inlineCallbacks
    def test_simpleDelete(self):
        """
        When a record object is deleted, a row with a matching primary key will
        be deleted in the database.
        """
        txn = self.pool.connection()

        def mkrow(beta, gamma):
            return txn.execSQL("insert into ALPHA values (:1, :2)",
                               [beta, gamma])

        yield gatherResults(
            [mkrow(123, u"one"), mkrow(234, u"two"), mkrow(345, u"three")]
        )
        tr = yield TestRecord.load(txn, 234)
        yield tr.delete()
        rows = yield txn.execSQL("select BETA, GAMMA from ALPHA order by BETA")
        self.assertEqual(rows, [(123, u"one"), (345, u"three")])


    @inlineCallbacks
    def oneRowCommitted(self, beta=123, gamma=u'456'):
        """
        Create, commit, and return one L{TestRecord}.
        """
        txn = self.pool.connection(self.id())
        row = yield TestRecord.create(txn, beta=beta, gamma=gamma)
        yield txn.commit()
        returnValue(row)


    @inlineCallbacks
    def test_deleteWhenDeleted(self):
        """
        When a record object is deleted, if it's already been deleted, it will
        raise L{NoSuchRecord}.
        """
        row = yield self.oneRowCommitted()
        txn = self.pool.connection(self.id())
        newRow = yield TestRecord.load(txn, row.beta)
        yield newRow.delete()
        yield self.assertFailure(newRow.delete(), NoSuchRecord)


    @inlineCallbacks
    def test_cantCreateWithoutRequiredValues(self):
        """
        When a L{Record} object is created without required values, it raises a
        L{TypeError}.
        """
        txn = self.pool.connection()
        te = yield self.assertFailure(TestAutoRecord.create(txn), TypeError)
        self.assertIn("required attribute 'epsilon' not passed", str(te))


    @inlineCallbacks
    def test_datetimeType(self):
        """
        When a L{Record} references a timestamp column, it retrieves the date
        as UTC.
        """
        txn = self.pool.connection()
        # Create ...
        rec = yield TestAutoRecord.create(txn, epsilon=1)
        self.assertEquals(
            rec.zeta,
            datetime.datetime(2012, 12, 12, 12, 12, 12)
        )
        yield txn.commit()
        # ... should have the same effect as loading.

        txn = self.pool.connection()
        rec = (yield TestAutoRecord.all(txn))[0]
        self.assertEquals(
            rec.zeta,
            datetime.datetime(2012, 12, 12, 12, 12, 12)
        )


    @inlineCallbacks
    def test_tooManyAttributes(self):
        """
        When a L{Record} object is created with unknown attributes (those which
        don't map to any column), it raises a L{TypeError}.
        """
        txn = self.pool.connection()
        te = yield self.assertFailure(
            TestRecord.create(
                txn, beta=3, gamma=u'three',
                extraBonusAttribute=u'nope',
                otherBonusAttribute=4321,
            ),
            TypeError
        )
        self.assertIn("extraBonusAttribute, otherBonusAttribute", str(te))


    @inlineCallbacks
    def test_createFillsInPKey(self):
        """
        If L{Record.create} is called without an auto-generated primary key
        value for its row, that value will be generated and set on the returned
        object.
        """
        txn = self.pool.connection()
        tr = yield TestAutoRecord.create(txn, epsilon=u'specified')
        tr2 = yield TestAutoRecord.create(txn, epsilon=u'also specified')
        self.assertEquals(tr.phi, 1)
        self.assertEquals(tr2.phi, 2)


    @inlineCallbacks
    def test_attributesArentMutableYet(self):
        """
        Changing attributes on a database object is not supported yet, because
        it's not entirely clear when to flush the SQL to the database.
        Instead, for the time being, use C{.update}.  When you attempt to set
        an attribute, an error will be raised informing you of this fact, so
        that the error is clear.
        """
        txn = self.pool.connection()
        rec = yield TestRecord.create(txn, beta=7, gamma=u'what')

        def setit():
            rec.beta = 12

        ro = self.assertRaises(ReadOnly, setit)
        self.assertEqual(rec.beta, 7)
        self.assertIn("SQL-backed attribute 'TestRecord.beta' is read-only. "
                      "Use '.update(...)' to modify attributes.", str(ro))


    @inlineCallbacks
    def test_simpleUpdate(self):
        """
        L{Record.update} will change the values on the record and in te
        database.
        """
        txn = self.pool.connection()
        rec = yield TestRecord.create(txn, beta=3, gamma=u'epsilon')
        yield rec.update(gamma=u'otherwise')
        self.assertEqual(rec.gamma, u'otherwise')
        yield txn.commit()
        # Make sure that it persists.
        txn = self.pool.connection()
        rec = yield TestRecord.load(txn, 3)
        self.assertEqual(rec.gamma, u'otherwise')


    @inlineCallbacks
    def test_simpleQuery(self):
        """
        L{Record.query} will allow you to query for a record by its class
        attributes as columns.
        """
        txn = self.pool.connection()
        for beta, gamma in [(123, u"one"), (234, u"two"), (345, u"three"),
                            (356, u"three"), (456, u"four")]:
            yield txn.execSQL("insert into ALPHA values (:1, :2)",
                              [beta, gamma])
        records = yield TestRecord.query(txn, TestRecord.gamma == u"three")
        self.assertEqual(len(records), 2)
        records.sort(key=lambda x: x.beta)
        self.assertEqual(records[0].beta, 345)
        self.assertEqual(records[1].beta, 356)


    @inlineCallbacks
    def test_querySimple(self):
        """
        L{Record.querysimple} will allow you to query for a record by its class
        attributes as columns.
        """
        txn = self.pool.connection()
        for beta, gamma in [(123, u"one"), (234, u"two"), (345, u"three"),
                            (356, u"three"), (456, u"four")]:
            yield txn.execSQL("insert into ALPHA values (:1, :2)",
                              [beta, gamma])
        records = yield TestRecord.querysimple(txn, gamma=u"three")
        self.assertEqual(len(records), 2)
        records.sort(key=lambda x: x.beta)
        self.assertEqual(records[0].beta, 345)
        self.assertEqual(records[1].beta, 356)


    @inlineCallbacks
    def test_eq(self):
        """
        L{Record.__eq__} works.
        """
        txn = self.pool.connection()
        data = [(123, u"one"), (456, u"four"), (345, u"three"),
                (234, u"two"), (356, u"three")]
        for beta, gamma in data:
            yield txn.execSQL("insert into ALPHA values (:1, :2)",
                              [beta, gamma])

        one = yield TestRecord.load(txn, 123)
        one_copy = yield TestRecord.load(txn, 123)
        two = yield TestRecord.load(txn, 234)

        self.assertTrue(one == one_copy)
        self.assertFalse(one == two)


    @inlineCallbacks
    def test_all(self):
        """
        L{Record.all} will return all instances of the record, sorted by
        primary key.
        """
        txn = self.pool.connection()
        data = [(123, u"one"), (456, u"four"), (345, u"three"),
                (234, u"two"), (356, u"three")]
        for beta, gamma in data:
            yield txn.execSQL("insert into ALPHA values (:1, :2)",
                              [beta, gamma])
        self.assertEqual(
            [(x.beta, x.gamma) for x in (yield TestRecord.all(txn))],
            sorted(data)
        )


    @inlineCallbacks
    def test_updatesome(self):
        """
        L{Record.updatesome} will update all instances of the matching records.
        """
        txn = self.pool.connection()
        data = [(123, u"one"), (456, u"four"), (345, u"three"),
                (234, u"two"), (356, u"three")]
        for beta, gamma in data:
            yield txn.execSQL("insert into ALPHA values (:1, :2)",
                              [beta, gamma])

        yield TestRecord.updatesome(txn, where=(TestRecord.beta == 123), gamma=u"changed")
        yield txn.commit()

        txn = self.pool.connection()
        records = yield TestRecord.all(txn)
        self.assertEqual(
            set([(record.beta, record.gamma,) for record in records]),
            set([
                (123, u"changed"), (456, u"four"), (345, u"three"),
                (234, u"two"), (356, u"three")
            ])
        )

        yield TestRecord.updatesome(txn, where=(TestRecord.beta.In((234, 345,))), gamma=u"changed-2")
        yield txn.commit()

        txn = self.pool.connection()
        records = yield TestRecord.all(txn)
        self.assertEqual(
            set([(record.beta, record.gamma,) for record in records]),
            set([
                (123, u"changed"), (456, u"four"), (345, u"changed-2"),
                (234, u"changed-2"), (356, u"three")
            ])
        )


    @inlineCallbacks
    def test_deleteall(self):
        """
        L{Record.deleteall} will delete all instances of the record.
        """
        txn = self.pool.connection()
        data = [(123, u"one"), (456, u"four"), (345, u"three"),
                (234, u"two"), (356, u"three")]
        for beta, gamma in data:
            yield txn.execSQL("insert into ALPHA values (:1, :2)",
                              [beta, gamma])

        yield TestRecord.deleteall(txn)
        all = yield TestRecord.all(txn)
        self.assertEqual(len(all), 0)


    @inlineCallbacks
    def test_deletesome(self):
        """
        L{Record.deletesome} will delete all instances of the matching records.
        """
        txn = self.pool.connection()
        data = [(123, u"one"), (456, u"four"), (345, u"three"),
                (234, u"two"), (356, u"three")]
        for beta, gamma in data:
            yield txn.execSQL("insert into ALPHA values (:1, :2)",
                              [beta, gamma])

        yield TestRecord.deletesome(txn, TestRecord.gamma == u"three")
        all = yield TestRecord.all(txn)
        self.assertEqual(set([record.beta for record in all]), set((123, 456, 234,)))

        yield TestRecord.deletesome(txn, (TestRecord.gamma == u"one").Or(TestRecord.gamma == u"two"))
        all = yield TestRecord.all(txn)
        self.assertEqual(set([record.beta for record in all]), set((456,)))


    @inlineCallbacks
    def test_deletesimple(self):
        """
        L{Record.deletesimple} will delete all instances of the matching records.
        """
        txn = self.pool.connection()
        data = [(123, u"one"), (456, u"four"), (345, u"three"),
                (234, u"two"), (356, u"three")]
        for beta, gamma in data:
            yield txn.execSQL("insert into ALPHA values (:1, :2)",
                              [beta, gamma])

        yield TestRecord.deletesimple(txn, gamma=u"three")
        all = yield TestRecord.all(txn)
        self.assertEqual(set([record.beta for record in all]), set((123, 456, 234,)))

        yield TestRecord.deletesimple(txn, beta=123, gamma=u"one")
        all = yield TestRecord.all(txn)
        self.assertEqual(set([record.beta for record in all]), set((456, 234)))


    @inlineCallbacks
    def test_repr(self):
        """
        The C{repr} of a L{Record} presents all its values.
        """
        txn = self.pool.connection()
        yield txn.execSQL("insert into ALPHA values (:1, :2)", [789, u'nine'])
        rec = list((yield TestRecord.all(txn)))[0]
        self.assertIn(" beta=789", repr(rec))
        self.assertIn(" gamma=u'nine'", repr(rec))


    @inlineCallbacks
    def test_orderedQuery(self):
        """
        L{Record.query} takes an 'order' argument which will allow the objects
        returned to be ordered.
        """
        txn = self.pool.connection()
        for beta, gamma in [(123, u"one"), (234, u"two"), (345, u"three"),
                            (356, u"three"), (456, u"four")]:
            yield txn.execSQL("insert into ALPHA values (:1, :2)",
                              [beta, gamma])

        records = yield TestRecord.query(
            txn, TestRecord.gamma == u"three", TestRecord.beta
        )
        self.assertEqual([record.beta for record in records], [345, 356])

        records = yield TestRecord.query(
            txn, TestRecord.gamma == u"three", TestRecord.beta, ascending=False
        )
        self.assertEqual([record.beta for record in records], [356, 345])


    @inlineCallbacks
    def test_pop(self):
        """
        A L{Record} may be loaded and deleted atomically, with L{Record.pop}.
        """
        txn = self.pool.connection()
        for beta, gamma in [
            (123, u"one"),
            (234, u"two"),
            (345, u"three"),
            (356, u"three"),
            (456, u"four"),
        ]:
            yield txn.execSQL(
                "insert into ALPHA values (:1, :2)", [beta, gamma]
            )

        rec = yield TestRecord.pop(txn, 234)
        self.assertEqual(rec.gamma, u'two')
        self.assertEqual(
            (yield txn.execSQL(
                "select count(*) from ALPHA where BETA = :1", [234]
            )),
            [tuple([0])]
        )
        yield self.assertFailure(TestRecord.pop(txn, 234), NoSuchRecord)


    def test_columnNamingConvention(self):
        """
        The naming convention maps columns C{LIKE_THIS} to be attributes
        C{likeThis}.
        """
        self.assertEqual(
            Record.namingConvention(u"like_this"),
            "likeThis"
        )
        self.assertEqual(
            Record.namingConvention(u"LIKE_THIS"),
            "likeThis"
        )
        self.assertEqual(
            Record.namingConvention(u"LIKE_THIS_ID"),
            "likeThisID"
        )


    @inlineCallbacks
    def test_lock(self):
        """
        A L{Record} may be locked, with L{Record.lock}.
        """
        txn = self.pool.connection()
        for beta, gamma in [
            (123, u"one"),
            (234, u"two"),
            (345, u"three"),
            (356, u"three"),
            (456, u"four"),
        ]:
            yield txn.execSQL(
                "insert into ALPHA values (:1, :2)", [beta, gamma]
            )

        rec = yield TestRecord.load(txn, 234)
        yield rec.lock()
        self.assertEqual(rec.gamma, u'two')


    @inlineCallbacks
    def test_trylock(self):
        """
        A L{Record} may be locked, with L{Record.trylock}.
        """
        txn = self.pool.connection()
        for beta, gamma in [
            (123, u"one"),
            (234, u"two"),
            (345, u"three"),
            (356, u"three"),
            (456, u"four"),
        ]:
            yield txn.execSQL(
                "insert into ALPHA values (:1, :2)", [beta, gamma]
            )

        rec = yield TestRecord.load(txn, 234)
        result = yield rec.trylock()
        self.assertTrue(result)


    @inlineCallbacks
    def test_serialize(self):
        """
        A L{SerializableRecord} may be serialized.
        """
        txn = self.pool.connection()
        for beta, gamma in [
            (123, u"one"),
            (234, u"two"),
            (345, u"three"),
            (356, u"three"),
            (456, u"four"),
        ]:
            yield txn.execSQL(
                "insert into ALPHA values (:1, :2)", [beta, gamma]
            )

        rec = yield TestSerializeRecord.load(txn, 234)
        result = rec.serialize()
        self.assertEqual(result, {"beta": 234, "gamma": u"two"})


    @inlineCallbacks
    def test_deserialize(self):
        """
        A L{SerializableRecord} may be deserialized.
        """
        txn = self.pool.connection()

        rec = yield TestSerializeRecord.deserialize({"beta": 234, "gamma": u"two"})
        yield rec.insert(txn)
        yield txn.commit()

        txn = self.pool.connection()
        rec = yield TestSerializeRecord.query(txn, TestSerializeRecord.beta == 234)
        self.assertEqual(len(rec), 1)
        self.assertEqual(rec[0].gamma, u"two")
        yield txn.commit()

        # Check that attributes can be changed prior to insert, and not after
        txn = self.pool.connection()
        rec = yield TestSerializeRecord.deserialize({"beta": 456, "gamma": u"one"})
        rec.gamma = u"four"
        yield rec.insert(txn)
        def _raise():
            rec.gamma = u"five"
        self.assertRaises(ReadOnly, _raise)
        yield txn.commit()

        txn = self.pool.connection()
        rec = yield TestSerializeRecord.query(txn, TestSerializeRecord.beta == 456)
        self.assertEqual(len(rec), 1)
        self.assertEqual(rec[0].gamma, u"four")
        yield txn.commit()
