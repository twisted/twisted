# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Test cases for dirdbm module.
"""

import os, shutil, glob

from twisted.trial import unittest
from twisted.persisted import dirdbm



class DirDbmTests(unittest.TestCase):

    def setUp(self):
        self.path = self.mktemp()
        self.dbm = dirdbm.open(self.path)
        self.items = (('abc', 'foo'), ('/lalal', '\000\001'), ('\000\012', 'baz'))


    def testAll(self):
        k = "//==".decode("base64")
        self.dbm[k] = "a"
        self.dbm[k] = "a"
        self.assertEqual(self.dbm[k], "a")


    def testRebuildInteraction(self):
        from twisted.persisted import dirdbm
        from twisted.python import rebuild

        s = dirdbm.Shelf('dirdbm.rebuild.test')
        s['key'] = 'value'
        rebuild.rebuild(dirdbm)
        # print s['key']


    def testDbm(self):
        d = self.dbm

        # insert keys
        keys = []
        values = set()
        for k, v in self.items:
            d[k] = v
            keys.append(k)
            values.add(v)
        keys.sort()

        # check they exist
        for k, v in self.items:
            self.assertIn(k, d)
            self.assertEqual(d[k], v)

        # check non existent key
        try:
            d["XXX"]
        except KeyError:
            pass
        else:
            assert 0, "didn't raise KeyError on non-existent key"

        # check keys(), values() and items()
        dbkeys = list(d.keys())
        dbvalues = set(d.values())
        dbitems = set(d.items())
        dbkeys.sort()
        items = set(self.items)
        assert keys == dbkeys, ".keys() output didn't match: %s != %s" % (repr(keys), repr(dbkeys))
        assert values == dbvalues, ".values() output didn't match: %s != %s" % (repr(values), repr(dbvalues))
        assert items == dbitems, "items() didn't match: %s != %s" % (repr(items), repr(dbitems))

        copyPath = self.mktemp()
        d2 = d.copyTo(copyPath)

        copykeys = list(d.keys())
        copyvalues = set(d.values())
        copyitems = set(d.items())
        copykeys.sort()

        assert dbkeys == copykeys, ".copyTo().keys() didn't match: %s != %s" % (repr(dbkeys), repr(copykeys))
        assert dbvalues == copyvalues, ".copyTo().values() didn't match: %s != %s" % (repr(dbvalues), repr(copyvalues))
        assert dbitems == copyitems, ".copyTo().items() didn't match: %s != %s" % (repr(dbkeys), repr(copyitems))

        d2.clear()
        assert len(d2.keys()) == len(d2.values()) == len(d2.items()) == 0, ".clear() failed"
        shutil.rmtree(copyPath)

        # delete items
        for k, v in self.items:
            del d[k]
            self.assertNotIn(k, d, "key is still in database, even though we deleted it")
        assert len(d.keys()) == 0, "database has keys"
        assert len(d.values()) == 0, "database has values"
        assert len(d.items()) == 0, "database has items"


    def testModificationTime(self):
        import time
        # the mtime value for files comes from a different place than the
        # gettimeofday() system call. On linux, gettimeofday() can be
        # slightly ahead (due to clock drift which gettimeofday() takes into
        # account but which open()/write()/close() do not), and if we are
        # close to the edge of the next second, time.time() can give a value
        # which is larger than the mtime which results from a subsequent
        # write(). I consider this a kernel bug, but it is beyond the scope
        # of this test. Thus we keep the range of acceptability to 3 seconds time.
        # -warner
        self.dbm["k"] = "v"
        self.assertTrue(abs(time.time() - self.dbm.getModificationTime("k")) <= 3)


    def testRecovery(self):
        """DirDBM: test recovery from directory after a faked crash"""
        k = self.dbm._encode("key1")
        with open(os.path.join(self.path, k + ".rpl"), "wb") as f:
            f.write("value")

        k2 = self.dbm._encode("key2")
        with open(os.path.join(self.path, k2), "wb") as f:
            f.write("correct")
        with open(os.path.join(self.path, k2 + ".rpl"), "wb") as f:
            f.write("wrong")

        with open(os.path.join(self.path, "aa.new"), "wb") as f:
            f.write("deleted")

        dbm = dirdbm.DirDBM(self.path)
        assert dbm["key1"] == "value"
        assert dbm["key2"] == "correct"
        assert not glob.glob(os.path.join(self.path, "*.new"))
        assert not glob.glob(os.path.join(self.path, "*.rpl"))


    def test_nonStringKeys(self):
        """
        L{dirdbm.DirDBM} operations only support string keys: other types
        should raise a C{AssertionError}. This really ought to be a
        C{TypeError}, but it'll stay like this for backward compatibility.
        """
        self.assertRaises(AssertionError, self.dbm.__setitem__, 2, "3")
        try:
            self.assertRaises(AssertionError, self.dbm.__setitem__, "2", 3)
        except unittest.FailTest:
            # dirdbm.Shelf.__setitem__ supports non-string values
            self.assertIsInstance(self.dbm, dirdbm.Shelf)
        self.assertRaises(AssertionError, self.dbm.__getitem__, 2)
        self.assertRaises(AssertionError, self.dbm.__delitem__, 2)
        self.assertRaises(AssertionError, self.dbm.has_key, 2)
        self.assertRaises(AssertionError, self.dbm.__contains__, 2)
        self.assertRaises(AssertionError, self.dbm.getModificationTime, 2)



class ShelfTests(DirDbmTests):

    def setUp(self):
        self.path = self.mktemp()
        self.dbm = dirdbm.Shelf(self.path)
        self.items = (('abc', 'foo'), ('/lalal', '\000\001'), ('\000\012', 'baz'),
                      ('int', 12), ('float', 12.0), ('tuple', (None, 12)))


testCases = [DirDbmTests, ShelfTests]
