
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

import dbserver
import dbservice
import unittest
import time

from twisted.internet import task

class DbManagerTestCase(unittest.TestCase):
    def setUp(self):
        self.manager = dbserver.DbManager(
            service =  "postgres",
            server =   "max",
            database = "twisted",
            username = "twisted",
            password = "matrix",
            numConnections = 2 )

    def tearDown(self):
        self.manager.disconnect()
        self.manager = None

    def testConnect(self):
        self.manager.connect()
        assert self.manager.connected == 1, 'not connected'
        assert len(self.manager.connections) == 2, 'wrong number of connections'


class DbServiceTestCase(unittest.TestCase):
    def setUp(self):
        self.manager = dbserver.DbManager(
            service =  "postgres",
            server =   "max",
            database = "twisted",
            username = "twisted",
            password = "matrix",
            numConnections = 1 )
        self.data = "DEFAULT"
        if not self.manager.connect():
            assert 0, 'failed to connect'

    def gotData(self, data):
        self.data = data

    def testAddUser(self):
        request = dbservice.AddUserRequest('testuser','testpass', self.gotData)
        self.manager.addRequest(request)
        self.manager.results.waitForSize(1)
        task.doAllTasks()
        assert self.data == None, 'no response for addUser result'

    def testPassword(self):
        request = dbservice.PasswordRequest('testuser', self.gotData)
        self.manager.addRequest(request)
        self.manager.results.waitForSize(1)
        task.doAllTasks()
        assert self.data == 'testpass', 'password retrieved is incorrect <%s>' % self.data

    def testBulk(self):
        NUMREQUESTS = 100
        for i in range(0,NUMREQUESTS):
            request = dbservice.PasswordRequest('testuser', self.gotData)
            self.manager.addRequest(request)
        self.manager.results.waitForSize(NUMREQUESTS)
        task.doAllTasks()
        assert self.manager.requests.getSize() == 0, 'bulk failed.'

    def tearDown(self):
        self.manager.disconnect()
        self.manager = None


suite1 = unittest.makeSuite(DbManagerTestCase, 'test')
suite2 = unittest.makeSuite(DbServiceTestCase, 'test')

if __name__ == "__main__":
    unittest.main()

