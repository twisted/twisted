
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
                 """

                 flagallicious docstringness for this here

                 """],
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

class InquisitionOptions(usage.Options):
    optFlags = [
        ('expect', 'e'),
        ]
    optParameters = [
        ('torture-device', 't',
         'comfy-chair',
         'set preferred torture device'),
        ]

class HolyQuestOptions(usage.Options):
    optFlags = [('horseback', 'h',
                 'use a horse'),
                ('for-grail', 'g'),
                ]

class SubCommandOptions(usage.Options):
    optFlags = [('europian-swallow', None,
                 'set default swallow type to Europian'),
                ]
    subCommands = [
        ('inquisition', 'inquest', InquisitionOptions, 'Perform an inquisition'),
        ('holyquest', 'quest', HolyQuestOptions, 'Embark upon a holy quest'),
        ]

class SubCommandTest(unittest.TestCase):

    def test_simpleSubcommand(self):
        o=SubCommandOptions()
        o.parseOptions(['--europian-swallow', 'inquisition'])
        self.failUnlessEqual(o['europian-swallow'], True)
        self.failUnlessEqual(o.subCommand, 'inquisition')
        self.failUnless(isinstance(o.subOptions, InquisitionOptions))
        self.failUnlessEqual(o.subOptions['expect'], False)
        self.failUnlessEqual(o.subOptions['torture-device'], 'comfy-chair')

    def test_subcommandWithFlagsAndOptions(self):
        o=SubCommandOptions()
        o.parseOptions(['inquisition', '--expect', '--torture-device=feather'])
        self.failUnlessEqual(o['europian-swallow'], False)
        self.failUnlessEqual(o.subCommand, 'inquisition')
        self.failUnless(isinstance(o.subOptions, InquisitionOptions))
        self.failUnlessEqual(o.subOptions['expect'], True)
        self.failUnlessEqual(o.subOptions['torture-device'], 'feather')

    def test_subcommandAliasWithFlagsAndOptions(self):
        o=SubCommandOptions()
        o.parseOptions(['inquest', '--expect', '--torture-device=feather'])
        self.failUnlessEqual(o['europian-swallow'], False)
        self.failUnlessEqual(o.subCommand, 'inquisition')
        self.failUnless(isinstance(o.subOptions, InquisitionOptions))
        self.failUnlessEqual(o.subOptions['expect'], True)
        self.failUnlessEqual(o.subOptions['torture-device'], 'feather')

    def test_anotherSubcommandWithFlagsAndOptions(self):
        o=SubCommandOptions()
        o.parseOptions(['holyquest', '--for-grail'])
        self.failUnlessEqual(o['europian-swallow'], False)
        self.failUnlessEqual(o.subCommand, 'holyquest')
        self.failUnless(isinstance(o.subOptions, HolyQuestOptions))
        self.failUnlessEqual(o.subOptions['horseback'], False)
        self.failUnlessEqual(o.subOptions['for-grail'], True)

    def test_noSubcommand(self):
        o=SubCommandOptions()
        o.parseOptions(['--europian-swallow'])
        self.failUnlessEqual(o['europian-swallow'], True)
        self.failUnlessEqual(o.subCommand, None)
        self.failIf(hasattr(o, 'subOptions'))

    def test_defaultSubcommand(self):
        o=SubCommandOptions()
        o.defaultSubCommand = 'inquest'
        o.parseOptions(['--europian-swallow'])
        self.failUnlessEqual(o['europian-swallow'], True)
        self.failUnlessEqual(o.subCommand, 'inquisition')
        self.failUnless(isinstance(o.subOptions, InquisitionOptions))
        self.failUnlessEqual(o.subOptions['expect'], False)
        self.failUnlessEqual(o.subOptions['torture-device'], 'comfy-chair')

    def test_subCommandParseOptionsHasParent(self):
        class SubOpt(usage.Options):
            def parseOptions(self, *a, **kw):
                self.sawParent = self.parent
                usage.Options.parseOptions(self, *a, **kw)
        class Opt(usage.Options):
            subCommands = [
                ('foo', 'f', SubOpt, 'bar'),
                ]
        o=Opt()
        o.parseOptions(['foo'])
        self.failUnless(hasattr(o.subOptions, 'sawParent'))
        self.failUnlessEqual(o.subOptions.sawParent , o)

    def test_subCommandInTwoPlaces(self):
        """The .parent pointer is correct even when the same Options class is used twice."""
        class SubOpt(usage.Options):
            pass
        class OptFoo(usage.Options):
            subCommands = [
                ('foo', 'f', SubOpt, 'quux'),
                ]
        class OptBar(usage.Options):
            subCommands = [
                ('bar', 'b', SubOpt, 'quux'),
                ]
        oFoo=OptFoo()
        oFoo.parseOptions(['foo'])
        oBar=OptBar()
        oBar.parseOptions(['bar'])
        self.failUnless(hasattr(oFoo.subOptions, 'parent'))
        self.failUnless(hasattr(oBar.subOptions, 'parent'))
        self.failUnlessIdentical(oFoo.subOptions.parent, oFoo)
        self.failUnlessIdentical(oBar.subOptions.parent, oBar)

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

    def test_whitespaceStripFlagsAndParameters(self):
        """Extra whitespace in flag and parameters docs is stripped"""
        # We test this by making sure aflag and it's help string are on the same line.
        lines = [s for s in str(self.nice).splitlines() if s.find("aflag")>=0]
        self.failUnless(len(lines) > 0)
        self.failUnless(lines[0].find("flagallicious") >= 0)

if __name__ == '__main__':
    unittest.main()
