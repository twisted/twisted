
# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
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


"""
Test cases for dirdbm module.
"""

from pyunit import unittest
from twisted.persisted import dirdbm
import os, tempfile

class DirDbmTestCase(unittest.TestCase):

    def setUp(self):
        self.path = tempfile.mktemp()
        self.dbm = dirdbm.open(self.path)
        self.items = (('abc', 'foo'), ('/lalal', '\000\001'), ('\000\012', 'baz'))
    
    def tearDown(self):
        os.rmdir(self.path)

    def testDbm(self):
        d = self.dbm
        
        # insert keys
        keys = []
        values = []
        for k, v in self.items:
            d[k] = v
            keys.append(k)
            values.append(v)
        keys.sort()
        values.sort()
        
        # check they exist
        for k, v in self.items:
            assert d.has_key(k), "has_key() failed"
            assert d[k] == v, "database has wrong value"
        
        # check non existent key
        try:
            d["XXX"]
        except KeyError:
            pass
        else:
            assert 0, "didn't raise KeyError on non-existent key"
        
        # check keys(), values() and items()
        dbkeys = list(d.keys())
        dbvalues = list(d.values())
        dbitems = list(d.items())
        dbkeys.sort()
        dbvalues.sort()
        dbitems.sort()
        items = list(self.items)
        items.sort()
        assert keys == dbkeys, ".keys() output didn't match: %s != %s" % (repr(keys), repr(dbkeys))
        assert values == dbvalues, ".values() output didn't match: %s != %s" % (repr(values), repr(dbvalues))
        assert items == dbitems, "items() didn't match: %s != %s" % (repr(items), repr(dbitems))
        
        # delete items
        for k, v in self.items:
            del d[k]
            assert not d.has_key(k), "has_key() even though we deleted it"
        assert len(d.keys()) == 0, "database has keys"
        assert len(d.values()) == 0, "database has values"
        assert len(d.items()) == 0, "database has items"


testCases = [DirDbmTestCase]
