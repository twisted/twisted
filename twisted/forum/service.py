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
"""Posting board that uses a relation database to store msgs.
"""

from twisted.spread import pb
from twisted.enterprise import adbapi

from pyPgSQL import PgSQL

import gadgets
import manager

class ForumUser(pb.Perspective):
    def __init__(self, identity_name, user_name, sig):
        pb.Perspective.__init__(self, identity_name, user_name)
        self.signature = sig
        global theService
        self.service = theService

    def attached(self, reference, identity):
        self.service.addUser()
        return pb.Perspective.attached(self, reference, identity)

    def detached(self, reference, identity):
        self.service.removeUser()
        return pb.Perspective.detached(self, reference, identity)

class ForumService(pb.Service):

    def __init__(self, name, app, dbpool, desc ):
        pb.Service.__init__(self, name, app)
        self.dbpool = dbpool
        self.manager = manager.ForumDB(dbpool)
        self.desc = desc
        self.usersOnline = 0
        global theService
        theService = self

    def loadPerspective(self, name):
        return self.manager.loadPerspective(name)

    def addUser(self):
        self.usersOnline += 1

    def removeUser(self):
        self.usersOnline -= 1


theService = None
