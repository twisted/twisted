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

"""Test cases for bounce message generation
"""

from twisted.trial import unittest
from twisted.mail import bounce
import rfc822, cStringIO

class BounceTestCase(unittest.TestCase):
    """
    testcases for bounce message generation
    """

    def testBounceFormat(self):
        from_, to, s = bounce.generateBounce(cStringIO.StringIO('''\
From: Moshe Zadka <moshez@example.com>
To: nonexistant@example.org
Subject: test

'''), 'moshez@example.com', 'nonexistant@example.org')
        self.assertEquals(from_, '')
        self.assertEquals(to, 'moshez@example.com')
        mess = rfc822.Message(cStringIO.StringIO(s))
        self.assertEquals(mess['To'], 'moshez@example.com')
        self.assertEquals(mess['From'], 'postmaster@example.org')
        self.assertEquals(mess['subject'], 'Returned Mail: see transcript for details')

    def testBounceMIME(self):
        pass
