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

from twisted.internet import tcp, main
from twisted.spread import pb
import time
import sys


class DbClient(pb.Referenceable):

    def __init__(self, host, name, password):
        self.host = host
        self.name = name
        self.password = password
        self.dbUser = None
        self.count = 0
        self.start = time.time()

    def doLogin(self):
        """This begins the login process"""
        pb.connect(self.gotConnection, self.coulntConnect,
                   self.host, pb.portno,
                   "twisted", "matrix",
                   "twisted.enterprise.db", "twisted")

    def couldntConnect(self, err):
        """Called when an error occurs"""
        print "Could not connect.", err

    def gotConnection(self, dbUser):
        print 'connected:', dbUser
        self.dbUser = dbUser

        args = ("select * from accounts where name = ?", ["testuser"])
        self.dbUser.callRequest("test", args, self)

    def remote_simpleSQLResults(self, *data):
        print "Got some data:" , self.count, data
        self.dbUser.simpleSQL("select * from accounts where name = ?", ("testuser",), self)
        self.count = self.count + 1
        if self.count == 400:
            now = time.time()
            print "Started at %f finished at %f took %f" % ( self.start, now, now - self.start)
            main.shutDown()

    def remote_simpleSQLError(self, *error):
        print "Error!", error

    def remote_requestResults(self, *data):
        print "Got request data:", data
        self.dbUser.simpleSQL("select * from accounts where name = ?", ("testuser",), self)        

    def remote_requestError(self, *error):
        print "Got request error:", error


def run():
    c = DbClient("localhost", "twisted", "matrix")
    c.doLogin()
    main.run()


if __name__ == '__main__':
    run()


