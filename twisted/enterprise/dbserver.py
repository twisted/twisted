""" Database server interface service for Twisted.

This service provides a way to interact with a relational database.
This interface is database vendor neutral.
"""

import md5
from twisted.spread import pb

    
class dbManager(pb.Service):
    """Manager that handles connections and requests. A dbManager handles connections
    to a particular database. It chooses the apropriate database driver (for a vendor)
    based on the "service" string passed in.

    Currently, all connections log into the database using the same database login. The login
    gets specified in the "servertest.py" script currently as a server called 'max', a database
    called 'twisted', and a user 'twisted' with a password 'matrix'.

    The actual user names that users supply are not database level user names, but names that
    exist in the "accounts" table in the database. For now, the accounts table is:

    create table accounts
    (
        name      char(24),
        password  char(24),
        accountid int
    );

    servertest.py adds two users to the accounts table for now. duplicates are ignored.
    
    """
    def __init__(self, service, server, database, username, password, numConnections = 1):
        self.server = server
        self.database = database
        self.username = username
        self.password = password
        self.service = service
        self.numConnections = numConnections
        self.connections = []
        self.requests = []
        self.busy = []
        self.users = {}
        self.connected = 0
        self.driver = None
        self.value = None  #utility variable to handle asynchronous data callbacks.

        ## Load the correct driver
        if service == "sybase":
            import Sybase
            self.driver = Sybase
        elif service == "postgres":
            print "Postgres not implemented yet...."
        else:
            print "ERROR: Uknown database service"

    def executeNow(self, sql):
        """Utility method to get the results of a sql request.
        NOT THREAD SAFE!!!
        """
        self.value = None
        newRequest = dbRequest(sql, self.gotValue)
        self.addRequest(newRequest)
        self.update() # arg this blocks for now!        
        return self.value

    def gotValue(self, value):
        """helper method for executeNow"""
        self.value = value

    def addUser(self, name, password):
        """Creates the user in the accounts table in the database.
        TODO: return the account ID of the new account.
        """
        print "Adding new user to database '%s' '%s'"%(name,password)        
        result = self.executeNow("insert into accounts ( name, password, accountid ) values ('%s', '%s', 0)" % (name, password) )
        result = self.executeNow("commit")

    def getPassword(self, name):
        """Gets the password for a user in the accounts table in the database.
        Also does the md5 encoding of it. 
        """
        #print "Getting password for %s"%(name)
        data = self.executeNow("select password from accounts where name = '%s'"%name)
        if len(data) == 0:
            return None
        password = data[0][0]
        newPassword =  md5.md5(password).digest()        
        return newPassword

    def loginUser(self, name):
        """User has been authenticated. Log the user in to the system and return a perspective.
        """
        newUser = dbUser(name, self)
        self.users[name] = newUser
        return newUser
    
    def connect(self):
        """Connect all the correct number of connections to the database/server specified.
        NOTE: auto_commit is false by default for sybase...
        """
        for i in range(0,self.numConnections):
            newConnection = self.driver.connect(self.server, self.username, self.password, database=self.database)
            newConnection.request = None
            self.connections.append(newConnection) 
            print "%d. Connected to %s" % (i, self.database)
        self.connected = 1

    def disconnect(self):
        print "Disconnecting from db"
        for con in self.connections:
            con.close()
        self.connections = []
        self.connected = 0
            
    def addRequest(self, request):
        # TODO: lock the requets Q
        self.requests.append(request)

    def update(self):
        """This is called periodically by the server framework to do processing of database requests.
        Currently it blocks on db requests - they are processed synchronously. It should be easy
        to add threads and multiple connections here eventually so requests can be handled simulateously
        """
        if self.connected == 0:
            self.connect()

        if len(self.requests) > 0 and len(self.connections) > 0:
            print "%d requests %d connections" %(len(self.requests), len(self.connections))                        
            connection = self.connections[0]
            connection.request = self.requests.pop()
            c = connection.cursor()
            print "Executing: %s" % connection.request.sql
            try:
                c.execute(connection.request.sql)
                connection.request.status = 1
                connection.request.callback( c.fetchall() )
            except self.driver.InternalError, e:
                print "ERROR: ", e
                connection.request.status = 0
                connection.request.callback( None )
        else:
            print "nothing to do."
            pass
                
class dbRequest:
    """A database request that includes the SQL to be executed, and the callback
    to pass the results to.
    """
    def __init__(self, sql, callback):
        self.sql = sql
        self.callback = callback

class dbUser(pb.Perspective):
    """A User that wants to interact with the database.
    """
    def __init__(self, name, manager):
        self.name = name
        self.manager = manager

    def perspective_request(self, sql):
        #print "Got SQL request:" , sql
        data = self.manager.executeNow(sql)
        return data
