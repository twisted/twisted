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

from twisted.python import util
import os, sys

class UtilTestCase(unittest.TestCase):

    def testUniq(self):
        l = ["a", 1, "ab", "a", 3, 4, 1, 2, 2, 4, 6]
        self.assertEquals(util.uniquify(l), ["a", 1, "ab", 3, 4, 2, 6])


class OrderedDictTest(unittest.TestCase):
    def testOrderedDict(self):
        d = util.OrderedDict()
        d['a'] = 'b'
        d['b'] = 'a'
        d[3] = 12
        d[1234] = 4321
        self.assertEquals(repr(d), "{'a': 'b', 'b': 'a', 3: 12, 1234: 4321}")
        self.assertEquals(d.values(), ['b', 'a', 12, 4321])
        del d[3]
        self.assertEquals(repr(d), "{'a': 'b', 'b': 'a', 1234: 4321}")
        self.assertEquals(d, {'a': 'b', 'b': 'a', 1234:4321})
        self.assertEquals(d.keys(), ['a', 'b', 1234])

    def testInitialization(self):
        d = util.OrderedDict({'monkey': 'ook',
                              'apple': 'red'})
        self.failUnless(d._order)


def reversePassword():
    password = util.getPassword()
    return reverseString(password)

def reverseString(s):
    s = list(s)
    s.reverse()
    s = ''.join(s)
    return s

class GetPasswordTest(unittest.TestCase):
    def testStdIn(self):
        """Making sure getPassword accepts a password from standard input.
        """
        script = "from twisted.test import test_util; print test_util.reversePassword()"
        cmd_in, cmd_out, cmd_err = os.popen3("%(python)s -c '%(script)s'" %
                                             {'python': sys.executable,
                                              'script': script}, 'rw')
        cmd_in.write("secret\n")
        cmd_in.close()
        # stripping print's trailing newline.
        secret = cmd_out.read()[:-1]
        errors = cmd_err.read()
        self.failIf(errors, errors)
        # The reversing trick it so make sure that there's not some weird echo
        # thing just sending back what we type in.
        self.failUnlessEqual(reverseString(secret), "secret")
