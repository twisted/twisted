
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

# System Imports
from pyunit import unittest
import cPickle

# Twisted Imports
from twisted.persisted import styles


class VersionTestCase(unittest.TestCase):
    def testNullVersionUpgrade(self):
        global NullVersioned
        class NullVersioned:
            ok = 0
        pkcl = cPickle.dumps(NullVersioned())
        class NullVersioned(styles.Versioned):
            def upgradeToVersion1(self):
                self.ok = 1
        mnv = cPickle.loads(pkcl)
        styles.doUpgrade()
        assert mnv.ok, "initial upgrade not run!"

    def testVersionUpgrade(self):
        global MyVersioned
        class MyVersioned(styles.Versioned):
            persistenceVersion = 2
            v3 = 0
            v4 = 0

            def __init__(self):
                self.somedata = 'xxx'

            def upgradeToVersion3(self):
                self.v3 = self.v3 + 1

            def upgradeToVersion4(self):
                self.v4 = self.v4 + 1
        mv = MyVersioned()
        assert not (mv.v3 or mv.v4), "hasn't been upgraded yet"
        pickl = cPickle.dumps(mv)
        MyVersioned.persistenceVersion = 4
        obj = cPickle.loads(pickl)
        styles.doUpgrade()
        assert obj.v3, "didn't do version 3 upgrade"
        assert obj.v4, "didn't do version 4 upgrade"
        pickl = cPickle.dumps(obj)
        obj = cPickle.loads(pickl)
        styles.doUpgrade()
        assert obj.v3 == 1, "upgraded unnecessarily"
        assert obj.v4 == 1, "upgraded unnecessarily"

testCases = [VersionTestCase]

