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

import os
import setup
from twisted.trial import unittest
import twisted

class CheckingPackagesTestCase(unittest.TestCase):

    def setUp(self):
        self.curDir = os.getcwd()

    def tearDown(self):
        os.chdir(self.curDir)

    def testListen(self):
        l = []
        os.chdir(os.path.dirname(setup.__file__))
        os.path.walk('twisted', 
                     lambda l,d,n:not d.endswith('CVS') and l.append(d),
                     l)
        l = [x.replace(os.sep, '.') for x in l]
        p = setup.setup_args['packages']

        for package in p:
            l.remove(package)
        # special treatment of cReactor
        l.remove('twisted.internet.cReactor')
        self.failUnlessEqual(l, [])
