# -*- coding: Latin-1 -*-

from twisted.trial import unittest
from twisted.python import usage
import usage as newusage

class TestOptions(usage.Options):
    optFlags = [
        ['Flag', 'F', 'This is a flag'],
        ['another', 'a', 'Second flag goes here'],
    ]
    
    optParameters = [
        ['param', 'P', None, 'This is the param'],
        ['noodle', 'd', "10", 'Default for this is "10"'],
        ['noshort', None, 10, 'Default for this is 10'],
        [None, 's', None, 'This only has a short version'],
    ]
    
    def opt_monkey(self):
        """Monkey is a flag"""
    opt_m = opt_monkey
    
    def opt_gorilla(self, arg):
        """Gorilla has no short form but is a param"""

class OptionTestCase(unittest.TestCase):
    def testSimpleOptions(self):
        o = TestOptions()
        o.parseArgs(['--Flag', '-d', 'foo', '--noshort=baz'])
        self.failUnless(o['Flag'])
        self.assertEquals(o['noodle'], 'foo')
        self.assertEquals(o['noshort'], 'baz')
        

    def testWebOptions(self):
        options = [
            '--personal', '--index', 'foo', '--index', 'bar', '--index',
            'baz', '--user', 'UserName', '--mime-type', 'parsing/fun!'
        ]
        from twisted.tap import web
        o = web.Options()
        o.parseArgs(options)
        
        self.failUnless(o['personal'])
        self.assertEquals(o['index'], ['foo', 'bar', 'baz'])
        self.assertEquals(o['user'], 'UserName')
        self.assertEquals(o['mime-type'], 'parsing/fun!')
        