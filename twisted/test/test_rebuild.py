
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
