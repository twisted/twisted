# Twisted, the Framework of Your Internet
# Copyright (C) 2001-2002 Matthew W. Lefkowitz
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
from twisted.trial import unittest

from twisted.sibling.siblingserv import SiblingService, TicketAuthorizer
from twisted.sibling.motherserv import MotherService
from twisted.cred.util import challenge
from twisted.internet.app import Application
from twisted.spread.pb import AuthRoot, BrokerFactory, Perspective, connect, Service

mother_port = 87871
sibling_port = mother_port
shared_port = mother_port

shared_secret = challenge()

def pauseTheReactor(ignore):
    from twisted.internet import reactor
    reactor.crash()
    return ignore

stopTheReactor = pauseTheReactor
class MeterMaid(Perspective):
    def __init__(self, name):
        Perspective.__init__(self,name)
        self.setService(Service("bleh"))

    def perspective_whatsMyName(self):
        return self.perspectiveName

class TwistedSiblingTestCase(unittest.TestCase):
    """TODO: need to put test cases for twisted.sibling here.
    These tests require that the reactor can be started and stopped multiple times
    without interfering with itself.
    """

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def testConnect(self):
        """Test that the siblings and mother server all connect to each other
        correctly with a shared secret.
        """
        pass

    def testLocking(self):
        """Test that a resource can be locked on a sibling server.
        """
        pass

    def testLogin(self):
        """Test that a client can login to a sibling server using distributed login.
        Test that a retrieved ticket can be used to login to a sibling.
        """
        pass

    def testLogout(self):
        """ Test that a client can logout and then log back into the sibling network.
        """
        pass

    def testCallDistributed(self):
        """Test that managed objects in the sibling network can communicate with each other
        via the mother server.
        """
        pass
