from pyunit import unittest

from twisted.python import failure

class TestFailure(unittest.TestCase):
    def testFailAndTrap(self):
        try:
            raise NotImplementedError('test')
        except:
            f = failure.Failure()
        f.trap(SystemExit, RuntimeError)
        try:
            raise ValueError()
        except:
            f = failure.Failure()
        self.assertRaises(failure.Failure,f.trap,OverflowError)
