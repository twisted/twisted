
from twisted.spread import pb
from twisted.python import delay, authenticator
import string
import dbserver

class DbService(pb.Service):
    """
    This service manages users that request to interact with the database.
    
    The actual user names that users supply are not database level user names, but names that
    exist in the "accounts" table in the database. For now, the accounts table is:

    create table accounts
    (
        name      char(24),
        password  char(24),
        accountid int
    );

    servertest.py adds two users to the accounts table for now. duplicates are ignored.

    This is assumed to be single threaded for now.

    """
    def __init__(self, manager, app, name='twisted.enterprise.db'):
        pb.Service.__init__(self, name, app)
        self.manager = manager


class DbUser(pb.Perspective):
    """A User that wants to interact with the database.
    """
    def perspective_request(self, sql):
        #print "Got SQL request:" , sql
        data = self.manager.executeNow(sql)
        return data[0]



class AddUserRequest(dbserver.DbRequest):
    """DbRequest to add a user to the accounts table
    """
    def __init__(self, name, password, callback):
        dbserver.DbRequest.__init__(self, callback)
        self.name = name
        self.password = password

    def execute(self, connection):
         c = connection.cursor()                
         c.execute("insert into accounts (name, password, accountid) values ('%s', '%s', 0)" % (self.name, self.password) )
         c.fetchall()
         c.execute("commit")
         c.fetchall()
         self.status = 1

class PasswordRequest(dbserver.DbRequest):
    """DbRequest to look up the password for a user in the accounts table.
    """
    def __init__(self, name, callback):
        dbserver.DbRequest.__init__(self, callback)
        self.name = name

    def execute(self, connection):
        c = connection.cursor()
        c.execute("select password from accounts where name = '%s'" % self.name)
        row = c.fetchone()
        if not row:
            # username not found.
            self.status = 0
            return None
        self.results = row[0]
        self.status = 1
        
