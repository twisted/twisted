#
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

import sys, os
from twisted.trial import unittest

from twisted.protocols.jabber import jid

class JIDParsingTest(unittest.TestCase):
    def testParse(self):
        # Basic forms
        self.assertEquals(jid.parse("user@host/resource"),
                          ("user", "host", "resource"))
        self.assertEquals(jid.parse("user@host"),
                          ("user", "host", None))
        self.assertEquals(jid.parse("host"),
                          (None, "host", None))
        self.assertEquals(jid.parse("host/resource"),
                          (None, "host", "resource"))

        # More interesting forms
        self.assertEquals(jid.parse("foo/bar@baz"),
                          (None, "foo", "bar@baz"))
        self.assertEquals(jid.parse("boo@foo/bar@baz"),
                          ("boo", "foo", "bar@baz"))
        self.assertEquals(jid.parse("boo@foo/bar/baz"),
                          ("boo", "foo", "bar/baz"))
        self.assertEquals(jid.parse("boo/foo@bar@baz"),
                          (None, "boo", "foo@bar@baz"))
        self.assertEquals(jid.parse("boo/foo/bar"),
                          (None, "boo", "foo/bar"))
        self.assertEquals(jid.parse("boo//foo"),
                          (None, "boo", "/foo"))
        
    def testInvalid(self):
        # No host
        try:
            jid.parse("user@")
            assert 0
        except jid.InvalidFormat:
            assert 1

        # Double @@
        try:
            jid.parse("user@@host")
            assert 0
        except jid.InvalidFormat:
            assert 1

        # Multiple @
        try:
            jid.parse("user@host@host")
            assert 0
        except jid.InvalidFormat:
            assert 1
            

class JIDClassTest(unittest.TestCase):
    def testBasic(self):
        j = jid.intern("user@host")
        self.assertEquals(j.userhost(), "user@host")
        self.assertEquals(j.user, "user")
        self.assertEquals(j.host, "host")
        self.assertEquals(j.resource, None)

        j2 = jid.intern("user@host")
        self.assertEquals(id(j), id(j2))

        j_uhj = j.userhostJID()
        self.assertEquals(id(j), id(j_uhj))
