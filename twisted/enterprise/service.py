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

from twisted.spread import pb
from twisted.python import delay, authenticator
import string
from twisted.enterprise import manager

class Service(pb.Service):
    """
    This service manages users that request to interact with the database.

    The actual user names that users supply are not database level user names, but names that
    exist in the "accounts" table in the database. For now, the accounts table is:

    create table accounts
    (
        name      char(24),
        passwd    char(24),
        accountid int
    );

    servertest.py adds two users to the accounts table for now. duplicates are ignored.

    This is assumed to be single threaded for now.

    """
    def __init__(self, manager, app, name='twisted.enterprise.db'):
        pb.Service.__init__(self, name, app)
        self.manager = manager

    def startService(self):
        print "Starting db service"
        self.manager.connect()


class DbUser(pb.Perspective):
    """A User that wants to interact with the database.
    """
    def perspective_request(self, sql, clientCollector):
        print "Got SQL request:" , sql
        newRequest = GenericRequest(sql, clientCollector.gotData)
        self.service.manager.addRequest(newRequest)


class GenericRequest(manager.Request):
    """Generic sql execution request.
    """
    def __init__(self, sql, callback):
        manager.Request.__init__(self, callback)
        self.sql = sql

    def execute(self, connection):
        c = connection.cursor()
        c.execute(self.sql)
        self.results = c.fetchall()
        c.close()
        #print "Fetchall :", c.fetchall()
        self.status = 1

class AddUserRequest(manager.Request):
    """DbRequest to add a user to the accounts table
    """
    def __init__(self, name, password, callback):
        manager.Request.__init__(self, callback)
        self.name = name
        self.password = password

    def execute(self, connection):
         c = connection.cursor()
         c.execute("insert into accounts (name, passwd, accountid) values ('%s', '%s', 0)" % (self.name, self.password) )
         c.fetchall()
         c.close()
         connection.commit()
         self.status = 1

class PasswordRequest(manager.Request):
    """DbRequest to look up the password for a user in the accounts table.
    """
    def __init__(self, name, callback):
        manager.Request.__init__(self, callback)
        self.name = name

    def execute(self, connection):
        c = connection.cursor()
        c.execute("select passwd from accounts where name = '%s'" % self.name)
        row = c.fetchall()
        if not row:
            # username not found.
            self.status = 0
            return None
        self.results = row[0]
        c.close()
        self.status = 1

