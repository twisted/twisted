# Twisted, the Framework of Your Internet
# Copyright (C) 2001-2003 Matthew W. Lefkowitz
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
#
from twisted.application import strports
from twisted.trial import unittest

class ParserTestCase(unittest.TestCase):

    f = "Factory"

    def testSimpleNumeric(self):
        self.assertEqual(strports.parse('80', self.f),
                         ('TCP', (80, self.f), {'interface':'', 'backlog':5}))

    def testSimpleTCP(self):
        self.assertEqual(strports.parse('tcp:80', self.f),
                         ('TCP', (80, self.f), {'interface':'', 'backlog':5}))

    def testInterfaceTCP(self):
        self.assertEqual(strports.parse('tcp:80:interface=127.0.0.1', self.f),
                         ('TCP', (80, self.f),
                                 {'interface':'127.0.0.1', 'backlog':5}))

    def testBacklogTCP(self):
        self.assertEqual(strports.parse('tcp:80:backlog=6', self.f),
                         ('TCP', (80, self.f),
                                 {'interface':'', 'backlog':6}))

    def testSimpleUnix(self):
        self.assertEqual(strports.parse('unix:/var/run/finger', self.f),
                         ('UNIX', ('/var/run/finger', self.f),
                                 {'mode':0666, 'backlog':5}))

    def testModedUNIX(self):
        self.assertEqual(strports.parse('unix:/var/run/finger:mode=0660',
                                        self.f),
                         ('UNIX', ('/var/run/finger', self.f),
                                 {'mode':0660, 'backlog':5}))

    def testAllKeywords(self):
        self.assertEqual(strports.parse('port=80', self.f),
                         ('TCP', (80, self.f), {'interface':'', 'backlog':5}))

    def testEscape(self):
        self.assertEqual(strports.parse(r'unix:foo\:bar\=baz\:qux\\', self.f),
                         ('UNIX', ('foo:bar=baz:qux\\', self.f),
                                 {'mode':0666, 'backlog':5}))

    def testImpliedEscape(self):
        self.assertEqual(strports.parse(r'unix:address=foo=bar', self.f),
                         ('UNIX', ('foo=bar', self.f),
                                 {'mode':0666, 'backlog':5}))

    def testNonstandardDefault(self):
        self.assertEqual(strports.parse('filename', self.f, 'unix'),
                         ('UNIX', ('filename', self.f),
                                 {'mode':0666, 'backlog':5}))
