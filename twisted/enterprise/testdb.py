
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



import unittest
import time

from twisted.enterprise import manager
from twisted.enterprise import service

def getDebug():
    return 0

class ManagerTestCase(unittest.TestCase):
    def setUp(self):
        self.manager = manager.ManagerSingle(
            service =  "sybase",
            server =   "max",
            database = "twisted",
            username = "twisted",
            password = "matrix")

    def tearDown(self):
        self.manager.disconnect()
        self.manager = None

    def testConnect(self):
        if getDebug(): print "starting connect"        
        self.manager.connect()
        assert self.manager.connected == 1, 'not connected'
        if getDebug(): print "test Connect successful"

class ServiceTestCase(unittest.TestCase):
    def setUp(self):
        self.manager = manager.ManagerSingle(
            service =  "sybase",
            server =   "max",
            database = "twisted",
            username = "twisted",
            password = "matrix")
        self.data = "DEFAULT"
        if not self.manager.connect():
            assert 0, 'failed to connect'
        if getDebug(): print "connected to database"
            

    def gotData(self, *data):
        self.data = data
        if getDebug(): print "got data:", data

    def testGeneric(self):
        if getDebug(): print "starting Generic"
        request = service.GenericRequest("select * from sysusers", self.gotData)
        self.manager.addRequest(request)
        assert self.data != "DEFAULT", 'no response for generic result'
        if getDebug(): print "test Generic  successful"
        
    def testAddUser(self):
        if getDebug(): print "starting AddUser"
        request = service.AddUserRequest('testuser','testpass', self.gotData)
        self.manager.addRequest(request)
        assert self.data != "DEFAULT", 'no response for addUser result'
        if getDebug(): print "test AddUser successful"

    def testPassword(self):
        if getDebug(): print "starting Password"
        request = service.PasswordRequest('testuser', self.gotData)
        self.manager.addRequest(request)
        #print "password is <%s>" % self.data
        assert self.data != "DEFAULT", 'password retrieved is incorrect'
        if getDebug(): print "test password successful"

    def testBulk(self):
        if getDebug(): print "starting Bulk"
        NUMREQUESTS = 100
        for i in range(0,NUMREQUESTS):
            request = service.PasswordRequest('testuser', self.gotData)
            self.manager.addRequest(request)
        assert self.data != "DEFULT", 'bulk failed.'
        if getDebug(): print "test Bulk successful"
        

    def tearDown(self):
        self.manager.disconnect()
        self.manager = None


suite1 = unittest.makeSuite(ManagerTestCase, 'test')
suite2 = unittest.makeSuite(ServiceTestCase, 'test')

if __name__ == "__main__":
    unittest.main()

