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

import os, sys
from twisted.trial import unittest
import twisted
d = os.path.dirname(os.path.dirname(twisted.__file__))
if os.path.isfile(os.path.join(d, 'setup.py')):
    sys.path.insert(0, d)
    import setup
    sys.path.pop(0)
else:
     setup = None

class CheckingPackagesTestCase(unittest.TestCase):

    def setUp(self):
        self.curDir = os.getcwd()

    def tearDown(self):
        os.chdir(self.curDir)

    def testPackages(self):
        """Making sure all packages are in setup"""
        if setup is None:
            raise unittest.SkipTest("no setup -- installed version?")
        foundPackages = []
        os.chdir(os.path.dirname(setup.__file__))
        def visit(dirlist, directory, files):
            if directory.endswith('CVS'):
                # Ignore CVS administrative directories.
                return
            if '__init__.py' in files:
                # This directory is a package.
                dirlist.append(directory)
            else:
                # There is a directory, but it's not a package, so it has no
                # bearing on whether or not setup_args['packages'] is correct
                # or not.
                pass
        os.path.walk('twisted', visit, foundPackages)
        foundPackages = [x.replace(os.sep, '.') for x in foundPackages]
        setupPackages = setup.setup_args['packages']

        for package in setupPackages:
            try:
                foundPackages.remove(package)
            except ValueError:
                self.fail("Package %r listed in setup.py but was not found in"
                          " the source tree." % (package,))

        # Everything in foundPackages should have been removed by its match
        # in setupPackages, nothing should be left.
        self.failIf(foundPackages, "Packages found which are not in setup.py: "
                    "%s\n" % (foundPackages,))
