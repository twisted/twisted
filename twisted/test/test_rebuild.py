
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


from pyunit import unittest
from twisted.python import rebuild

import crash_test_dummy
from twisted.python.rebuild import rebuild
from twisted.reality import thing
from twisted.web import server
from twisted.python import delay
f = crash_test_dummy.foo

class RebuildTestCase(unittest.TestCase):
    """Simple testcase for rebuilding, to at least exercise the code.
    """
    def testRebuild(self):
        x = crash_test_dummy.X('a')
        x = [x]
        d = delay.Delayed()
        d.later(x[0].do, 1)
        d.run()
        d.run()
        d.run()
        
        d.later(x[0].do, 1)
        rebuild(crash_test_dummy,0)
        d.run()
        d.run()
        d.run()
        
        rebuild(thing,0)
        rebuild(server,0)
        assert f is crash_test_dummy.foo, 'huh?'
        #x[0].do()
        assert x[0].__class__ is crash_test_dummy.X, 'huh?'

testCases = [RebuildTestCase]
