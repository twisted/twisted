
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

from pyunit import unittest

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
        # from twisted.internet import ssl
        from twisted.internet import stdio
        from twisted.internet import abstract
        from twisted.internet import process
        from twisted.internet import task
        from twisted.internet import threadtask

    def test_spread(self):
        """Test importing spreadables
        """
        from twisted.spread import pb
        from twisted.spread import jelly

    def test_twistedPython(self):
        """Test importing twisted.python
        """
        from twisted.python import delay
        from twisted.python import hook
        from twisted.python import log
        from twisted.python import observable
        from twisted.python import reference
        from twisted.python import reflect
        from twisted.python import threadable
        from twisted.python import threadpool
        from twisted.python import usage

    def test_reality(self):
        """Test importing reality
        """
        from twisted.reality import reality
        from twisted.reality import thing
        from twisted.reality import sentence
        from twisted.reality import source
        from twisted.reality import error
        from twisted.reality import player
        from twisted.reality import plumbing
        from twisted.reality import room
        from twisted.reality import container
        from twisted.reality import geometry
        from twisted.reality import clothing
        from twisted.reality import door
        from twisted.reality import furniture
        from twisted.reality import lock

    def test_protocols(self):
        """Test importing protocols
        """
        from twisted.protocols import basic
        from twisted.protocols import ftp
        from twisted.protocols import http
        from twisted.protocols import irc
        from twisted.protocols import pop3
        from twisted.protocols import protocol
        from twisted.protocols import smtp
        from twisted.protocols import telnet

    def test_web(self):
        """Test importing web
        """
        from twisted.web import server
        from twisted.web import html
        from twisted.web import twcgi
        ## from twisted.web import distributed
        from twisted.web import cal
        from twisted.web import script
        from twisted.web import static
        from twisted.web import test
        from twisted.web import utils
        from twisted.web import vhost
        from twisted.web import weblog

    def test_words(self):
        """Test importing words
        """
        from twisted.words import service
        from twisted.words import ircservice

    def test_mail(self):
        """Test importing mail
        """
        from twisted.mail import mail
        from twisted.mail import maildir
        from twisted.mail import pb
        from twisted.mail import relaymanager

testCases = [AtLeastImportTestCase]
