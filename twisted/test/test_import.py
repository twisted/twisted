
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
from twisted.python.runtime import platformType

class AtLeastImportTestCase(unittest.TestCase):

    """I test that there are no syntax errors which will not allow importing.
    """

    failureException = ImportError

    def test_misc(self):
        """Test importing other misc. modules
        """
        from twisted import copyright

    def test_persisted(self):
        """Test importing persisted
        """
        from twisted.persisted import dirdbm
        from twisted.persisted import styles

    def test_internet(self):
        """Test importing internet
        """
        from twisted.internet import tcp
        from twisted.internet import main
        from twisted.internet import app
        # from twisted.internet import ssl    
        from twisted.internet import abstract
        from twisted.internet import udp
        from twisted.internet import protocol
        from twisted.internet import defer

    def test_unix(self):
        """internet modules for unix."""
        from twisted.internet import stdio
        from twisted.internet import process
        from twisted.internet import unix
    
    if platformType != "posix":
        test_unix.skip = "UNIX-only modules"
    
    def test_spread(self):
        """Test importing spreadables
        """
        from twisted.spread import pb
        from twisted.spread import jelly
        from twisted.spread import banana
        from twisted.spread import flavors
    
    def test_twistedPython(self):
        """Test importing twisted.python
        """
        from twisted.python import hook
        from twisted.python import log
        from twisted.python import reflect
        from twisted.python import threadable
        from twisted.python import threadpool
        from twisted.python import usage
        from twisted.python import otp
    
    def test_protocols(self):
        """Test importing protocols
        """
        from twisted.protocols import basic
        from twisted.protocols import ftp
        from twisted.protocols import http
        from twisted.protocols import irc
        from twisted.protocols import pop3
        from twisted.protocols import smtp
        from twisted.protocols import telnet
        from twisted.protocols import oscar
        from twisted.protocols import toc
        from twisted.protocols import imap4
        from twisted.protocols import policies
    
    def test_web(self):
        """Test importing web
        """
        from twisted.web import server
        from twisted.web import html
        from twisted.web import twcgi
        from twisted.web import widgets
        from twisted.web import script
        from twisted.web import static
        from twisted.web import test
        from twisted.web import vhost
        from twisted.web import guard
        from twisted.web import error
    
    def test_words(self):
        """Test importing words
        """
        from twisted.words import service
        from twisted.words import ircservice

    def test_names(self):
        """Test importing names
        """
        from twisted.names import authority
        from twisted.names import cache
        from twisted.names import common
        from twisted.names import hosts
        from twisted.names import resolve
        from twisted.names import server
        from twisted.names import tap

    def test_mail(self):
        """Test importing mail
        """
        from twisted.mail import mail
        from twisted.mail import maildir
        from twisted.mail import pb
        from twisted.mail import relaymanager
        from twisted.mail import protocols
        from twisted.mail import tap

    def test_enterprise(self):
        from twisted.enterprise import adbapi
        from twisted.enterprise import reflector
        from twisted.enterprise import sqlreflector
        from twisted.enterprise import xmlreflector
        from twisted.enterprise import row

    def test_lore(self):
        from twisted.lore import tree
        from twisted.lore import latex
        from twisted.lore import slides
        from twisted.lore import lmath

    def test_test(self):
        import os, sys
        oldargv = sys.argv
        sys.argv = sys.argv[:1]
        try:
            tests = os.listdir(os.path.dirname(__file__))
            for f in tests:
                if f.startswith('test_') and f.endswith('.py'):
                    __import__('twisted.test.%s' % f[:-3])
        finally:
            sys.argv = oldargv

testCases = [AtLeastImportTestCase]
