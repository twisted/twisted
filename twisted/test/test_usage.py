from pyunit import unittest
from twisted.python import usage
import string

class WellBehaved(usage.Options):
    parameters = [['long', 'w', 'default', 'and a docstring'],
                  ['another', 'n', 'no docstring'],
                  ['longonly', None, 'noshort'],
                  ['shortless', None, 'except', 'this one got docstring'],
                  ]
    flags = [['aflag', 'f', 'flagallicious docstringness for this here'],
             ['flout', 'o'],
             ]

    def opt_myflag(self):        
        self.myflag = "PONY!"

    def opt_myparam(self, value):
        self.myparam = "%s WITH A PONY!" % (value,)


class ParseCorrectnessTest(unittest.TestCase):
    """Test Options.parseArgs for correct values under good conditions.
    """
    def setUp(self):
        """Instantiate and parseOptions a well-behaved Options class.
        """
        
        self.niceArgV = string.split("--long Alpha -n Beta "
                                     "--shortless Gamma -f --myflag "
                                     "--myparam Tofu")
        
        self.nice = WellBehaved()

        self.nice.parseOptions(self.niceArgV)
        
    def test_checkParameters(self):
        """Checking that parameters have correct values.
        """
        self.failUnlessEqual(self.nice.long, "Alpha")
        self.failUnlessEqual(self.nice.another, "Beta")
        self.failUnlessEqual(self.nice.longonly, "noshort")
        self.failUnlessEqual(self.nice.shortless, "Gamma")

    def test_checkFlags(self):
        """Checking that flags have correct values.
        """
        self.failUnlessEqual(self.nice.aflag, 1)
        self.failUnlessEqual(self.nice.flout, 0)

    def test_checkCustoms(self):
        """Checking that custom flags and parameters have correct values.
        """
        self.failUnlessEqual(self.nice.myflag, "PONY!")
        self.failUnlessEqual(self.nice.myparam, "Tofu WITH A PONY!")

class HelpStringTest(unittest.TestCase):
    def setUp(self):
        """Instantiate a well-behaved Options class.
        """
        
        self.niceArgV = string.split("--long Alpha -n Beta "
                                     "--shortless Gamma -f --myflag "
                                     "--myparam Tofu")
        
        self.nice = WellBehaved()
    
    def test_noGoBoom(self):
        """__str__ shouldn't go boom.
        """

        try:
            self.nice.__str__()
        except Exception, e:
            self.fail(e)
        
if __name__ == '__main__':
    unittest.main()
