from pyunit import unittest
from twisted.eco import eco

class EcoTestCase(unittest.TestCase):
    
    def testConsify(self):
        c = eco.consify([1,2,3,["a","b"]])
        assert c == [1, [2, [3, [["a", ["b", []]], []]]]]

    def testEval(self):
        assert eco.eval('[+ 2 3]') == 5
        assert eco.eval("[let [[x 1] [y 2]] [+ x y]]") == 3
        assert eco.eval('''[if [eq [+ 3 3] 0] [foo 1 2 3]
                            [list 1 2 3]]''') == [1, [2, [3, []]]]
