
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
import os

class DirDbmTestCase(unittest.TestCase):

    def setUp(self):
        self.dbm = dirdbm.open("/tmp/dirdbm")

    def tearDown(self):
        os.rmdir("/tmp/dirdbm")

    def testDbm(self):
        self.dbm['hello'] = 'world'
        if self.dbm['hello'] != 'world':
            raise AssertionError(self.dbm['hello'])
        if not self.dbm.has_key('hello'):
            raise AssertionError
        if self.dbm.has_key('goodbye'):
            raise AssertionError
        del self.dbm['hello']

testCases = [DirDbmTestCase]
