# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.python.usage}, a command line option parsing library.
"""

from twisted.trial import unittest
from twisted.python import usage


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
    """
    Test Options.parseArgs for correct values under good conditions.
    """
    def setUp(self):
        """
        Instantiate and parseOptions a well-behaved Options class.
        """

        self.niceArgV = ("--long Alpha -n Beta "
                         "--shortless Gamma -f --myflag "
                         "--myparam Tofu").split()

        self.nice = WellBehaved()

        self.nice.parseOptions(self.niceArgV)

    def test_checkParameters(self):
        """
        Checking that parameters have correct values.
        """
        self.assertEqual(self.nice.opts['long'], "Alpha")
        self.assertEqual(self.nice.opts['another'], "Beta")
        self.assertEqual(self.nice.opts['longonly'], "noshort")
        self.assertEqual(self.nice.opts['shortless'], "Gamma")

    def test_checkFlags(self):
        """
        Checking that flags have correct values.
        """
        self.assertEqual(self.nice.opts['aflag'], 1)
        self.assertEqual(self.nice.opts['flout'], 0)

    def test_checkCustoms(self):
        """
        Checking that custom flags and parameters have correct values.
        """
        self.assertEqual(self.nice.opts['myflag'], "PONY!")
        self.assertEqual(self.nice.opts['myparam'], "Tofu WITH A PONY!")



class TypedOptions(usage.Options):
    optParameters = [
        ['fooint', None, 392, 'Foo int', int],
        ['foofloat', None, 4.23, 'Foo float', float],
        ['eggint', None, None, 'Egg int without default', int],
        ['eggfloat', None, None, 'Egg float without default', float],
    ]

    def opt_under_score(self, value):
        """
        This option has an underscore in its name to exercise the _ to -
        translation.
        """
        self.underscoreValue = value
    opt_u = opt_under_score



class TypedTestCase(unittest.TestCase):
    """
    Test Options.parseArgs for options with forced types.
    """
    def setUp(self):
        self.usage = TypedOptions()

    def test_defaultValues(self):
        """
        Test parsing of default values.
        """
        argV = []
        self.usage.parseOptions(argV)
        self.assertEqual(self.usage.opts['fooint'], 392)
        self.assert_(isinstance(self.usage.opts['fooint'], int))
        self.assertEqual(self.usage.opts['foofloat'], 4.23)
        self.assert_(isinstance(self.usage.opts['foofloat'], float))
        self.assertEqual(self.usage.opts['eggint'], None)
        self.assertEqual(self.usage.opts['eggfloat'], None)


    def test_parsingValues(self):
        """
        Test basic parsing of int and float values.
        """
        argV = ("--fooint 912 --foofloat -823.1 "
                "--eggint 32 --eggfloat 21").split()
        self.usage.parseOptions(argV)
        self.assertEqual(self.usage.opts['fooint'], 912)
        self.assert_(isinstance(self.usage.opts['fooint'], int))
        self.assertEqual(self.usage.opts['foofloat'], -823.1)
        self.assert_(isinstance(self.usage.opts['foofloat'], float))
        self.assertEqual(self.usage.opts['eggint'], 32)
        self.assert_(isinstance(self.usage.opts['eggint'], int))
        self.assertEqual(self.usage.opts['eggfloat'], 21.)
        self.assert_(isinstance(self.usage.opts['eggfloat'], float))


    def test_underscoreOption(self):
        """
        A dash in an option name is translated to an underscore before being
        dispatched to a handler.
        """
        self.usage.parseOptions(['--under-score', 'foo'])
        self.assertEqual(self.usage.underscoreValue, 'foo')


    def test_underscoreOptionAlias(self):
        """
        An option name with a dash in it can have an alias.
        """
        self.usage.parseOptions(['-u', 'bar'])
        self.assertEqual(self.usage.underscoreValue, 'bar')


    def test_invalidValues(self):
        """
        Check that passing wrong values raises an error.
        """
        argV = "--fooint egg".split()
        self.assertRaises(usage.UsageError, self.usage.parseOptions, argV)



class WrongTypedOptions(usage.Options):
    optParameters = [
        ['barwrong', None, None, 'Bar with wrong coerce', 'he']
    ]


class WeirdCallableOptions(usage.Options):
    def _bar(value):
        raise RuntimeError("Ouch")
    def _foo(value):
        raise ValueError("Yay")
    optParameters = [
        ['barwrong', None, None, 'Bar with strange callable', _bar],
        ['foowrong', None, None, 'Foo with strange callable', _foo]
    ]


class WrongTypedTestCase(unittest.TestCase):
    """
    Test Options.parseArgs for wrong coerce options.
    """
    def test_nonCallable(self):
        """
        Check that using a non callable type fails.
        """
        us =  WrongTypedOptions()
        argV = "--barwrong egg".split()
        self.assertRaises(TypeError, us.parseOptions, argV)

    def test_notCalledInDefault(self):
        """
        Test that the coerce functions are not called if no values are
        provided.
        """
        us = WeirdCallableOptions()
        argV = []
        us.parseOptions(argV)

    def test_weirdCallable(self):
        """
        Test what happens when coerce functions raise errors.
        """
        us = WeirdCallableOptions()
        argV = "--foowrong blah".split()
        # ValueError is swallowed as UsageError
        e = self.assertRaises(usage.UsageError, us.parseOptions, argV)
        self.assertEqual(str(e), "Parameter type enforcement failed: Yay")

        us = WeirdCallableOptions()
        argV = "--barwrong blah".split()
        # RuntimeError is not swallowed
        self.assertRaises(RuntimeError, us.parseOptions, argV)


class OutputTest(unittest.TestCase):
    def test_uppercasing(self):
        """
        Error output case adjustment does not mangle options
        """
        opt = WellBehaved()
        e = self.assertRaises(usage.UsageError,
                              opt.parseOptions, ['-Z'])
        self.assertEqual(str(e), 'option -Z not recognized')


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
        ('inquisition', 'inquest', InquisitionOptions,
            'Perform an inquisition'),
        ('holyquest', 'quest', HolyQuestOptions,
            'Embark upon a holy quest'),
        ]


class SubCommandTest(unittest.TestCase):

    def test_simpleSubcommand(self):
        o = SubCommandOptions()
        o.parseOptions(['--europian-swallow', 'inquisition'])
        self.assertEqual(o['europian-swallow'], True)
        self.assertEqual(o.subCommand, 'inquisition')
        self.failUnless(isinstance(o.subOptions, InquisitionOptions))
        self.assertEqual(o.subOptions['expect'], False)
        self.assertEqual(o.subOptions['torture-device'], 'comfy-chair')

    def test_subcommandWithFlagsAndOptions(self):
        o = SubCommandOptions()
        o.parseOptions(['inquisition', '--expect', '--torture-device=feather'])
        self.assertEqual(o['europian-swallow'], False)
        self.assertEqual(o.subCommand, 'inquisition')
        self.failUnless(isinstance(o.subOptions, InquisitionOptions))
        self.assertEqual(o.subOptions['expect'], True)
        self.assertEqual(o.subOptions['torture-device'], 'feather')

    def test_subcommandAliasWithFlagsAndOptions(self):
        o = SubCommandOptions()
        o.parseOptions(['inquest', '--expect', '--torture-device=feather'])
        self.assertEqual(o['europian-swallow'], False)
        self.assertEqual(o.subCommand, 'inquisition')
        self.failUnless(isinstance(o.subOptions, InquisitionOptions))
        self.assertEqual(o.subOptions['expect'], True)
        self.assertEqual(o.subOptions['torture-device'], 'feather')

    def test_anotherSubcommandWithFlagsAndOptions(self):
        o = SubCommandOptions()
        o.parseOptions(['holyquest', '--for-grail'])
        self.assertEqual(o['europian-swallow'], False)
        self.assertEqual(o.subCommand, 'holyquest')
        self.failUnless(isinstance(o.subOptions, HolyQuestOptions))
        self.assertEqual(o.subOptions['horseback'], False)
        self.assertEqual(o.subOptions['for-grail'], True)

    def test_noSubcommand(self):
        o = SubCommandOptions()
        o.parseOptions(['--europian-swallow'])
        self.assertEqual(o['europian-swallow'], True)
        self.assertEqual(o.subCommand, None)
        self.failIf(hasattr(o, 'subOptions'))

    def test_defaultSubcommand(self):
        o = SubCommandOptions()
        o.defaultSubCommand = 'inquest'
        o.parseOptions(['--europian-swallow'])
        self.assertEqual(o['europian-swallow'], True)
        self.assertEqual(o.subCommand, 'inquisition')
        self.failUnless(isinstance(o.subOptions, InquisitionOptions))
        self.assertEqual(o.subOptions['expect'], False)
        self.assertEqual(o.subOptions['torture-device'], 'comfy-chair')

    def test_subCommandParseOptionsHasParent(self):
        class SubOpt(usage.Options):
            def parseOptions(self, *a, **kw):
                self.sawParent = self.parent
                usage.Options.parseOptions(self, *a, **kw)
        class Opt(usage.Options):
            subCommands = [
                ('foo', 'f', SubOpt, 'bar'),
                ]
        o = Opt()
        o.parseOptions(['foo'])
        self.failUnless(hasattr(o.subOptions, 'sawParent'))
        self.assertEqual(o.subOptions.sawParent , o)

    def test_subCommandInTwoPlaces(self):
        """
        The .parent pointer is correct even when the same Options class is
        used twice.
        """
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
        oFoo = OptFoo()
        oFoo.parseOptions(['foo'])
        oBar=OptBar()
        oBar.parseOptions(['bar'])
        self.failUnless(hasattr(oFoo.subOptions, 'parent'))
        self.failUnless(hasattr(oBar.subOptions, 'parent'))
        self.failUnlessIdentical(oFoo.subOptions.parent, oFoo)
        self.failUnlessIdentical(oBar.subOptions.parent, oBar)


class HelpStringTest(unittest.TestCase):
    def setUp(self):
        """
        Instantiate a well-behaved Options class.
        """

        self.niceArgV = ("--long Alpha -n Beta "
                         "--shortless Gamma -f --myflag "
                         "--myparam Tofu").split()

        self.nice = WellBehaved()

    def test_noGoBoom(self):
        """
        __str__ shouldn't go boom.
        """
        try:
            self.nice.__str__()
        except Exception, e:
            self.fail(e)

    def test_whitespaceStripFlagsAndParameters(self):
        """
        Extra whitespace in flag and parameters docs is stripped.
        """
        # We test this by making sure aflag and it's help string are on the
        # same line.
        lines = [s for s in str(self.nice).splitlines() if s.find("aflag")>=0]
        self.failUnless(len(lines) > 0)
        self.failUnless(lines[0].find("flagallicious") >= 0)


class PortCoerceTestCase(unittest.TestCase):
    """
    Test the behavior of L{usage.portCoerce}.
    """
    def test_validCoerce(self):
        """
        Test the answers with valid input.
        """
        self.assertEqual(0, usage.portCoerce("0"))
        self.assertEqual(3210, usage.portCoerce("3210"))
        self.assertEqual(65535, usage.portCoerce("65535"))

    def test_errorCoerce(self):
        """
        Test error path.
        """
        self.assertRaises(ValueError, usage.portCoerce, "")
        self.assertRaises(ValueError, usage.portCoerce, "-21")
        self.assertRaises(ValueError, usage.portCoerce, "212189")
        self.assertRaises(ValueError, usage.portCoerce, "foo")



class ZshCompleterTestCase(unittest.TestCase):
    """
    Test the behavior of the various L{twisted.usage.Completer} classes
    for producing output usable by zsh tab-completion system.
    """
    def test_completer(self):
        """
        Completer produces zsh shell-code that produces no completion matches.
        """
        c = usage.Completer()
        got = c._shellCode('some-option', usage._ZSH)
        self.assertEqual(got, ':some-option:')

        c = usage.Completer(descr='some action', repeat=True)
        got = c._shellCode('some-option', usage._ZSH)
        self.assertEqual(got, '*:some action:')


    def test_files(self):
        """
        CompleteFiles produces zsh shell-code that completes file names
        according to a glob.
        """
        c = usage.CompleteFiles()
        got = c._shellCode('some-option', usage._ZSH)
        self.assertEqual(got, ':some-option (*):_files -g "*"')

        c = usage.CompleteFiles('*.py')
        got = c._shellCode('some-option', usage._ZSH)
        self.assertEqual(got, ':some-option (*.py):_files -g "*.py"')

        c = usage.CompleteFiles('*.py', descr="some action", repeat=True)
        got = c._shellCode('some-option', usage._ZSH)
        self.assertEqual(got, '*:some action (*.py):_files -g "*.py"')


    def test_dirs(self):
        """
        CompleteDirs produces zsh shell-code that completes directory names.
        """
        c = usage.CompleteDirs()
        got = c._shellCode('some-option', usage._ZSH)
        self.assertEqual(got, ':some-option:_directories')

        c = usage.CompleteDirs(descr="some action", repeat=True)
        got = c._shellCode('some-option', usage._ZSH)
        self.assertEqual(got, '*:some action:_directories')


    def test_list(self):
        """
        CompleteList produces zsh shell-code that completes words from a fixed
        list of possibilities.
        """
        c = usage.CompleteList('ABC')
        got = c._shellCode('some-option', usage._ZSH)
        self.assertEqual(got, ':some-option:(A B C)')

        c = usage.CompleteList(['1', '2', '3'])
        got = c._shellCode('some-option', usage._ZSH)
        self.assertEqual(got, ':some-option:(1 2 3)')

        c = usage.CompleteList(['1', '2', '3'], descr='some action',
                               repeat=True)
        got = c._shellCode('some-option', usage._ZSH)
        self.assertEqual(got, '*:some action:(1 2 3)')


    def test_multiList(self):
        """
        CompleteMultiList produces zsh shell-code that completes multiple
        comma-separated words from a fixed list of possibilities.
        """
        c = usage.CompleteMultiList('ABC')
        got = c._shellCode('some-option', usage._ZSH)
        self.assertEqual(got, ':some-option:_values -s , \'some-option\' A B C')

        c = usage.CompleteMultiList(['1','2','3'])
        got = c._shellCode('some-option', usage._ZSH)
        self.assertEqual(got, ':some-option:_values -s , \'some-option\' 1 2 3')

        c = usage.CompleteMultiList(['1','2','3'], descr='some action',
                                    repeat=True)
        got = c._shellCode('some-option', usage._ZSH)
        expected = '*:some action:_values -s , \'some action\' 1 2 3'
        self.assertEqual(got, expected)


    def test_usernames(self):
        """
        CompleteUsernames produces zsh shell-code that completes system
        usernames.
        """
        c = usage.CompleteUsernames()
        out = c._shellCode('some-option', usage._ZSH)
        self.assertEqual(out, ':some-option:_users')

        c = usage.CompleteUsernames(descr='some action', repeat=True)
        out = c._shellCode('some-option', usage._ZSH)
        self.assertEqual(out, '*:some action:_users')


    def test_groups(self):
        """
        CompleteGroups produces zsh shell-code that completes system group
        names.
        """
        c = usage.CompleteGroups()
        out = c._shellCode('some-option', usage._ZSH)
        self.assertEqual(out, ':group:_groups')

        c = usage.CompleteGroups(descr='some action', repeat=True)
        out = c._shellCode('some-option', usage._ZSH)
        self.assertEqual(out, '*:some action:_groups')


    def test_hostnames(self):
        """
        CompleteHostnames produces zsh shell-code that completes hostnames.
        """
        c = usage.CompleteHostnames()
        out = c._shellCode('some-option', usage._ZSH)
        self.assertEqual(out, ':some-option:_hosts')

        c = usage.CompleteHostnames(descr='some action', repeat=True)
        out = c._shellCode('some-option', usage._ZSH)
        self.assertEqual(out, '*:some action:_hosts')


    def test_userAtHost(self):
        """
        CompleteUserAtHost produces zsh shell-code that completes hostnames or
        a word of the form <username>@<hostname>.
        """
        c = usage.CompleteUserAtHost()
        out = c._shellCode('some-option', usage._ZSH)
        self.assertTrue(out.startswith(':host | user@host:'))

        c = usage.CompleteUserAtHost(descr='some action', repeat=True)
        out = c._shellCode('some-option', usage._ZSH)
        self.assertTrue(out.startswith('*:some action:'))


    def test_netInterfaces(self):
        """
        CompleteNetInterfaces produces zsh shell-code that completes system
        network interface names.
        """
        c = usage.CompleteNetInterfaces()
        out = c._shellCode('some-option', usage._ZSH)
        self.assertEqual(out, ':some-option:_net_interfaces')

        c = usage.CompleteNetInterfaces(descr='some action', repeat=True)
        out = c._shellCode('some-option', usage._ZSH)
        self.assertEqual(out, '*:some action:_net_interfaces')



class CompleterNotImplementedTestCase(unittest.TestCase):
    """
    Using an unknown shell constant with the various Completer() classes
    should raise NotImplementedError
    """
    def test_unknownShell(self):
        """
        Using an unknown shellType should raise NotImplementedError
        """
        classes = [usage.Completer, usage.CompleteFiles,
                   usage.CompleteDirs, usage.CompleteList,
                   usage.CompleteMultiList, usage.CompleteUsernames,
                   usage.CompleteGroups, usage.CompleteHostnames,
                   usage.CompleteUserAtHost, usage.CompleteNetInterfaces]

        for cls in classes:
            try:
                action = cls()
            except:
                action = cls(None)
            self.assertRaises(NotImplementedError, action._shellCode,
                              None, "bad_shell_type")
