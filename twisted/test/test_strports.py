# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

#
from twisted.application import strports
from twisted.trial import unittest

class ParserTestCase(unittest.TestCase):

    f = "Factory"

    def testSimpleNumeric(self):
        self.assertEqual(strports.parse('80', self.f),
                         ('TCP', (80, self.f), {'interface':'', 'backlog':50}))

    def testSimpleTCP(self):
        self.assertEqual(strports.parse('tcp:80', self.f),
                         ('TCP', (80, self.f), {'interface':'', 'backlog':50}))

    def testInterfaceTCP(self):
        self.assertEqual(strports.parse('tcp:80:interface=127.0.0.1', self.f),
                         ('TCP', (80, self.f),
                                 {'interface':'127.0.0.1', 'backlog':50}))

    def testBacklogTCP(self):
        self.assertEqual(strports.parse('tcp:80:backlog=6', self.f),
                         ('TCP', (80, self.f),
                                 {'interface':'', 'backlog':6}))


    def test_simpleUNIX(self):
        """
        L{strports.parse} returns a C{'UNIX'} port description with defaults
        for C{'mode'}, C{'backlog'}, and C{'wantPID'} when passed a string with
        the C{'unix:'} prefix and no other parameter values.
        """
        self.assertEqual(
            strports.parse('unix:/var/run/finger', self.f),
            ('UNIX', ('/var/run/finger', self.f),
             {'mode': 0666, 'backlog': 50, 'wantPID': True}))


    def test_modeUNIX(self):
        """
        C{mode} can be set by including C{"mode=<some integer>"}.
        """
        self.assertEqual(
            strports.parse('unix:/var/run/finger:mode=0660', self.f),
            ('UNIX', ('/var/run/finger', self.f),
             {'mode': 0660, 'backlog': 50, 'wantPID': True}))


    def test_wantPIDUNIX(self):
        """
        C{wantPID} can be set to false by included C{"lockfile=0"}.
        """
        self.assertEqual(
            strports.parse('unix:/var/run/finger:lockfile=0', self.f),
            ('UNIX', ('/var/run/finger', self.f),
             {'mode': 0666, 'backlog': 50, 'wantPID': False}))


    def testAllKeywords(self):
        self.assertEqual(strports.parse('port=80', self.f),
                         ('TCP', (80, self.f), {'interface':'', 'backlog':50}))

    def testEscape(self):
        self.assertEqual(
            strports.parse(r'unix:foo\:bar\=baz\:qux\\', self.f),
            ('UNIX', ('foo:bar=baz:qux\\', self.f),
             {'mode': 0666, 'backlog': 50, 'wantPID': True}))


    def testImpliedEscape(self):
        self.assertEqual(
            strports.parse(r'unix:address=foo=bar', self.f),
            ('UNIX', ('foo=bar', self.f),
             {'mode': 0666, 'backlog': 50, 'wantPID': True}))

    def testNonstandardDefault(self):
        self.assertEqual(
            strports.parse('filename', self.f, 'unix'),
            ('UNIX', ('filename', self.f),
             {'mode': 0666, 'backlog': 50, 'wantPID': True}))
