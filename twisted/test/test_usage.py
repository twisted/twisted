
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

from twisted.trial import unittest
from twisted.python import usage
import string

class WellBehaved(usage.Options):
    optParameters = [['long', 'w', 'default', 'and a docstring'],
                     ['another', 'n', 'no docstring'],
                     ['longonly', None, 'noshort'],
                     ['shortless', None, 'except',
                      'this one got docstring'],
                  ]
    optFlags = [['aflag', 'f',
                 'flagallicious docstringness for this here'],
                ['flout', 'o'],
                ]

    def opt_myflag(self):
        self.opts['myflag'] = "PONY!"

    def opt_myparam(self, value):
        self.opts['myparam'] = "%s WITH A PONY!" % (value,)


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
        self.failUnlessEqual(self.nice.opts['long'], "Alpha")
        self.failUnlessEqual(self.nice.opts['another'], "Beta")
        self.failUnlessEqual(self.nice.opts['longonly'], "noshort")
        self.failUnlessEqual(self.nice.opts['shortless'], "Gamma")

    def test_checkFlags(self):
        """Checking that flags have correct values.
        """
        self.failUnlessEqual(self.nice.opts['aflag'], 1)
        self.failUnlessEqual(self.nice.opts['flout'], 0)

    def test_checkCustoms(self):
        """Checking that custom flags and parameters have correct values.
        """
        self.failUnlessEqual(self.nice.opts['myflag'], "PONY!")
        self.failUnlessEqual(self.nice.opts['myparam'], "Tofu WITH A PONY!")

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
