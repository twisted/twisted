# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Test cases for twisted.python.zshcomp
"""
import os
import os.path
from cStringIO import StringIO

from twisted.trial import unittest
from twisted.python import zshcomp, usage



class ZshcompTestCase(unittest.TestCase):
    """
    Tests for the zsh completion function builder in twisted/python/zshcomp.py
    """
    def test_buildAll(self):
        """
        Build all the completion functions for twisted commands - no errors
        should be raised
        """
        dirname = self.mktemp()
        os.mkdir(dirname)
        skippedCmds = [x[0] for x in zshcomp.makeCompFunctionFiles(dirname)]

        # verify a zsh function was created for each twisted command
        for info in zshcomp.generateFor:
            if info[0] in skippedCmds:
                continue
            funcPath = os.path.join(dirname, '_' + info[0])
            self.assertTrue(os.path.exists(funcPath))


    def test_accumulateMetadata(self):
        """
        The zsh_* variables you can place on Options classes are
        picked up correctly?
        """
        opts = FighterAceExtendedOptions()
        ag = zshcomp.ArgumentsGenerator('dummy_cmd', opts, 'dummy_value')

        altArgDescr = FighterAceOptions.zsh_altArgDescr.copy()
        altArgDescr.update(FighterAceExtendedOptions.zsh_altArgDescr)

        actionDescr = FighterAceOptions.zsh_actionDescr.copy()
        actionDescr.update(FighterAceExtendedOptions.zsh_actionDescr)

        self.assertEqual(ag.altArgDescr, altArgDescr)
        self.assertEqual(ag.actionDescr, actionDescr)
        self.assertEqual(ag.multiUse, FighterAceOptions.zsh_multiUse)
        self.assertEqual(ag.mutuallyExclusive,
                          FighterAceOptions.zsh_mutuallyExclusive)
        self.assertEqual(ag.actions, FighterAceOptions.zsh_actions)
        self.assertEqual(ag.extras, FighterAceOptions.zsh_extras)


    def test_accumulateAdditionalOptions(self):
        """
        We pick up options that are only defined by having an
        appropriately named method on your Options class,
        e.g. def opt_foo(self, foo)
        """
        opts = FighterAceExtendedOptions()
        ag = zshcomp.ArgumentsGenerator('dummy_cmd', opts, 'dummy_value')

        self.assertIn('nocrash', ag.optFlags_d)
        self.assertIn('nocrash', ag.optAll_d)

        self.assertIn('difficulty', ag.optParams_d)
        self.assertIn('difficulty', ag.optAll_d)


    def test_verifyZshNames(self):
        """
        Using a parameter/flag name that doesn't exist
        will raise an error
        """
        class TmpOptions(FighterAceExtendedOptions):
            zsh_actions = {'detaill' : 'foo'} # Note typo of detail

        opts = TmpOptions()
        self.assertRaises(ValueError, zshcomp.ArgumentsGenerator,
                              'dummy_cmd', opts, 'dummy_value')


    def test_zshCode(self):
        """
        Generate a completion function, and test the textual output
        against a known correct output
        """
        cmd_name = 'testprog'
        opts = SillyOptions()
        f = StringIO()
        b = zshcomp.Builder(cmd_name, opts, f)
        b.write()
        f.reset()
        self.assertEqual(f.read(), testOutput1)


    def test_skipBuild(self):
        """
        makeCompFunctionFiles skips building for commands whos
        script module cannot be imported
        """
        generateFor = [('test_cmd', 'no.way.your.gonna.import.this', 'Foo')]
        skips = zshcomp.makeCompFunctionFiles('out_dir', generateFor, {})
        # no exceptions should be raised. hooray.
        self.assertEqual(len(skips), 1)
        self.assertEqual(len(skips[0]), 2)
        self.assertEqual(skips[0][0], 'test_cmd')
        self.assertTrue(isinstance(skips[0][1], ImportError))



class FighterAceOptions(usage.Options):
    """
    Command-line options for an imaginary "Fighter Ace" game
    """
    optFlags = [['fokker', 'f',
                 'Select the Fokker Dr.I as your dogfighter aircraft'],
                ['albatros', 'a',
                 'Select the Albatros D-III as your dogfighter aircraft'],
                ['spad', 's',
                 'Select the SPAD S.VII as your dogfighter aircraft'],
                ['bristol', 'b',
                 'Select the Bristol Scout as your dogfighter aircraft'],
                ['physics', 'p',
                 'Enable secret Twisted physics engine'],
                ['jam', 'j',
                 'Enable a small chance that your machine guns will jam!'],
                ['verbose', 'v',
                 'Verbose logging (may be specified more than once)'],
                ]

    optParameters = [['pilot-name', None, "What's your name, Ace?",
                      'Manfred von Richthofen'],
                     ['detail', 'd',
                      'Select the level of rendering detail (1-5)', '3'],
                     ]

    zsh_altArgDescr = {'physics' : 'Twisted-Physics',
                       'detail' : 'Rendering detail level'}
    zsh_actionDescr = {'detail' : 'Pick your detail'}
    zsh_multiUse = ['verbose']
    zsh_mutuallyExclusive = [['fokker', 'albatros', 'spad', 'bristol']]
    zsh_actions = {'detail' : '(1 2 3 4 5)'}
    zsh_extras = [':saved game file to load:_files']



class FighterAceExtendedOptions(FighterAceOptions):
    """
    Extend the options and zsh metadata provided by FighterAceOptions. zshcomp
    must accumulate options and metadata from all classes in the hiearchy so
    this is important for testing
    """
    optFlags = [['no-stalls', None,
                 'Turn off the ability to stall your aircraft']]
    optParameters = [['reality-level', None,
                      'Select the level of physics reality (1-5)', '5']]

    zsh_altArgDescr = {'no-stalls' : 'Can\'t stall your plane'}
    zsh_actionDescr = {'reality-level' : 'Physics reality level'}


    def opt_nocrash(self):
        """Select that you can't crash your plane"""


    def opt_difficulty(self, difficulty):
        """How tough are you? (1-10)"""



def _accuracyAction():
    return '(1 2 3)'



class SillyOptions(usage.Options):
    """
    Command-line options for a "silly" program
    """
    optFlags = [['color', 'c', 'Turn on color output'],
                ['gray', 'g', 'Turn on gray-scale output'],
                ['verbose', 'v',
                 'Verbose logging (may be specified more than once)'],
                ]

    optParameters = [['optimization', None,
                      'Select the level of optimization (1-5)', '5'],
                     ['accuracy', 'a',
                      'Select the level of accuracy (1-3)', '3'],
                     ]


    zsh_altArgDescr = {'color' : 'Color on',
                       'optimization' : 'Optimization level'}
    zsh_actionDescr = {'optimization' : 'Optimization?',
                       'accuracy' : 'Accuracy?'}
    zsh_multiUse = ['verbose']
    zsh_mutuallyExclusive = [['color', 'gray']]
    zsh_actions = {'optimization' : '(1 2 3 4 5)',
                   'accuracy' : _accuracyAction}
    zsh_extras = [':output file:_files']



testOutput1 = """#compdef testprog
_arguments -s -A "-*" \\
':output file:_files' \\
'(--accuracy)-a[3]:Accuracy?:(1 2 3)' \\
'(-a)--accuracy=[3]:Accuracy?:(1 2 3)' \\
'(--gray -g --color)-c[Color on]' \\
'(--gray -g -c)--color[Color on]' \\
'(--color -c --gray)-g[Turn on gray-scale output]' \\
'(--color -c -g)--gray[Turn on gray-scale output]' \\
'--help[Display this help and exit.]' \\
'--optimization=[Optimization level]:Optimization?:(1 2 3 4 5)' \\
'*-v[Verbose logging (may be specified more than once)]' \\
'*--verbose[Verbose logging (may be specified more than once)]' \\
'--version[Display Twisted version and exit.]' \\
&& return 0
"""

