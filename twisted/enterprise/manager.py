
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

""" Database server connection manager interface service for Twisted.

This service provides a way to interact with a relational database.
This interface is database vendor neutral.
"""

import threading
import time

from twisted.internet import threadtask

    
                    
class ManagerSingle:
    """Single threaded database request handler. This processes requests immediately and
    blocks on the database server returning results. This the base implementation of
    the database interface.

    Knows nothing of application level usernames or passwords.    

    """
    def __init__(self, service, server, database, username, password):
        self.service = service
        self.server = server
        self.database = database
        self.username = username
        self.password = password
        self.driver = None
        self.connected = 0
        self.total = 0
        if databaseDrivers.has_key(service):
            self.driver = databaseDrivers[service]()
        else:
            print "ERROR: Database driver not known"

    def connect(self):
        """Connection details vary by the database driver being used. This class
        makes a single database connection.
        """
        self.total = 0
        self.connection = self.driver.connect(self.server, self.database, self.username, self.password)
        if self.connection:
            self.connected = 1
            return 1
        else:
            return 0

    def disconnect(self):
        if self.connected == 0:
            return
        self.connection.close()

    def addRequest(self, request):
        """This runs the request now!
        """
        result = self.driver.execute(self.connection, request)
        
        if request.status == 1:
            if request.results:
                apply(request.callback, request.results)
            else:
                request.callback()

        self.total = self.total + 1
        return request.status
        
class ManagerThreadPool(ManagerSingle):
    """Manager that handles multiple connections/thread and requests. 

    requests processing sequence is:
        main thread - request is added to the requests queue
        connection thread gets the request
        connection thread processes the request
        connection thread schedules callback to be run
        main thread - the schedules callback for the request is run

    """
    def __init__(self, service, server, database, username, password, numConnections = 1):
        ManagerSingle.__init__(self, service, server, database, username, password)
        self.numConnections = numConnections
        self.connections = []
        self.requests = RequestQueue()
        self.connected = 0
        self.total = 0
   
    def connect(self):
        """Connect all the correct number of connections to the database/server specified.
        NOTE: auto_commit is false by default for sybase...
        """
        self.total = 0        
        count = 0
        print "Creating %d database connections:" % self.numConnections
        for i in range(0,self.numConnections):
            #print "trying to connect..."
            newConnection = ConnectionThread(self)
            if newConnection.connect():
                newConnection.start()
                self.connections.append(newConnection)
                count = count + 1
                #print "connected."
            else:
                pass
                #print "failed to connect"
        if count == self.numConnections:
            self.connected = 1
            return 1
        else:
            print "Error in connection to database. requested %d got %d" % (self.numConnections, count)
            return 0


    def disconnect(self):
        #print "Disconnecting from db"
        for con in self.connections:
            con.close()
        for con in self.connections:
            self.requests.incrementForClose(self.numConnections)
        for con in self.connections:
            con.join()
        self.connections = []
        self.connected = 0
            
    def addRequest(self, request):
        """Add a request to the queue of requests to be processed
        """
        self.requests.addRequest(request)
        self.total= self.total +1

    def getRequest(self):
        """This is run in ConnectionThread threads NOT the main thread. it retrieves
        a request from the queue, but blocks if there are not requests until one arrives.
        """
        request = self.requests.waitForRequest()
        return request
        
class ConnectionThread(threading.Thread):
    """A thread that handles a database connection. The 'execute' method of Requests
    is run in this thread.
    """
    connectionID = 0
    
    def __init__(self, manager):
        threading.Thread.__init__(self)
        self.manager = manager
        self.id = ConnectionThread.connectionID
        ConnectionThread.connectionID = ConnectionThread.connectionID + 1

    def connect(self):
        """Connection details vary by the database driver being used.
        """
        self.connection = self.manager.driver.connect(self.server, self.database, self.username, self.password)
        if self.connection:
            self.running = 1
            return 1
        return 0
        
    def run(self):
        while self.running:
            # block for a request
            request = self.manager.getRequest()
            if not request:
                # empty request means time to go
                break

            # process the request
            result = self.driver.execute(self.connection, request)

            threadtask.schedule(request.callback, args=request.results)

    def close(self):
        #print "Thread (%d): Closing" % ( self.id)
        self.running = 0
        self.connection.close()

class RequestQueue:
    """A thread safe FIFO queue of requests. waitForRequest is intended to be run in
    a thread that blocks until there is a request to process available. getRequest
    doesn't block but returns with None if there are not requests.
    """
    def __init__(self):
        self.lock = threading.Lock()
        self.sem = threading.Semaphore(0)
        self.queue = []

    def __getstate__(self):
        return None

    def __setstate__(self, state):
        self.__init__()

    def addRequest(self, request):
        self.lock.acquire()            # acquire exclusive access to queue
        self.queue.append(request)     # add request to queue
        self.sem.release()             # increment semaphore
        self.lock.release()            # release access to queue

    def waitForRequest(self):
        self.sem.acquire()             # block on semaphore to get a request
        self.lock.acquire()
        if len(self.queue) > 0:
            request = self.queue.pop(0)
            self.lock.release()
            return request
        else:
            self.lock.release()
            return None

    def getRequest(self):
        self.lock.acquire()
        if len(self.queue) > 0:
            request = self.queue.pop(0)
            self.lock.release()
            return request
        else:
            self.lock.release()
            return None

    def incrementForClose(self, num):
        """special method to increment the semaphore so that every thread wakes up.
        used to shutdown the threads waiting for requests in a blocked state.
        """
        self.lock.acquire()
        for i in range(0,num):
            self.sem.release()
        self.lock.release()

    def getSize(self):
        self.lock.acquire()
        s = len(self.queue)
        self.lock.release()
        return s

    def waitForSize(self, size):
        """WARNING: NASTY SPIN LOOP
        if the queue is not at the specified size, poll it at intervals until it is.
        This is equivelant to blocking, but uses CPU. bad.
        """
        self.lock.acquire()
        s = len(self.queue)
        self.lock.release()
        if s == size:
            return

        while s != size:
            self.lock.acquire()
            s = len(self.queue)
            self.lock.release()
            time.sleep(0.11)

class Request:
    """base class for database requests to be executed in dbconnection threads.
    the method 'execute' will be run. 'self.callback' will be executed after the request
    has been processed (in the main thread) with the data in 'self.results' and
    an error code in 'self.status'. These two member variables (results and status)
    should be set by the user code in teh execute method.
    """
    lastId = 0

    def __init__(self, callback):
        self.status = 0
        self.error = None
        self.results = None
        self.callback = callback
        self.id = Request.lastId
        Request.lastId = Request.lastId + 1

    def execute(self, connection):
        """Method to be implemented by derived classes. this is run when the
        request is processed. This will be run within a try/except block that
        catched database exceptions.  The results of the query should be stored in
        the member variable 'results'. set self.status to 1 for successful execution.
        """
        print "WARNING: empty DBRequest being run"
        self.status = 0


class Driver:
    """abstract base class for database drivers. This isolated database specific code
    (even through there shouldn't be any) that the python DBAPI 2.0 implementations
    expose.
    """
    def connect(self, server, database, username, password):
        """maps args into the correct connect format. Should return
        a connection object.
        """
        print "NOT IMPLEMENTED"

    def execute(self, connection, request):
        """uses the right exceptions for the driver.
        Should return 0 or 1"""
        print "NOT IMPLEMENTED"



class DriverSybase:
    """Driver for the Sybase database interface. This driver doesn't seem to scale well
    with multiple threads or connections. Available from:
    
        http://object-craft.com.au/projects/sybase/sybase/sybase.html
        
    """
    def __init__(self):
        print "Creating Sybase database driver"
        import Sybase
        self.driver = Sybase
        
    def connect(self, server, database, username, password):
        """Connect to a Sybase database server
        """
        connection = None
        try:
            connection = self.driver.connect(
                server, 
                username, 
                password, 
                database=database
                )
        except self.driver.InternalError, e:
            print "unable to connect to database: %s" % repr(e)
        return connection

    def execute(self, connection, request):
        """Execute a request
        """
        try:
            result = request.execute(connection)
            return 1
        except self.driver.InternalError, e:
            text = "SQL ERROR:\n"
            self.error = e[0][1]
            for k in self.error.keys():
                text = text +  "    %s: %s\n" % (k, self.error[k])
            print text
            return 0


class DriverInterbase:
    """Driver for the Interbase gvib database interface. This driver
    is only able to connect to local Interbase database instances -
    it actually takes the full path to a _file_ as the database
    argument. Available from:

        http://clientes.netvisao.pt/luiforra/ib/index.html

    """
    def __init__(self):
        print "Creating Interbase gvib Database driver"        
        import gvib
        from gvib import gvibExceptions                    
        self.driver = gvib
        self.exceptions = gvibExceptions
        
    def connect(self, server, database, username, password):
        """Connect to an Interbase database server
        """

        connection = None
        try:
            connection = self.driver.connect( database, username, password )
            print "Connected to Interbase"
        except self.exceptions.StandardError, e:
            print "Interbase error: %s" % e
        return connection
 
    def execute(self, connection, request):
        """Execute a request
        """
        try:
            result = request.execute(connection)
            return 1
        except gvibExceptions.StandardError, e:
            print "Interbase error: %s" % e.args
            return 0
 

class DriverPostgres:
    """PoPy driver for the Postres database interface. Available from:

        http://popy.sourceforge.net/
        
    """
    def __init__(self):
        print "Creating Postgres PoPy Database driver"
        import Popy
        self.driver = PoPy
        
    def connect(self, server, database, username, password):
        """Connect to a Postgres database server
        """
        connection = None
        try:
            connection = self.driver.connect( "user=%s dbname=%s" % (username, database) )
        except self.driver.DatabaseError, e:
            print "unable to connect to database: %s" % repr(e)
        return connection

    def execute(self, connection, request):
        """Execute a request
        """
        try:
            result = request.execute(connection)
            return 1
        except self.driver.DatabaseError, e:
            print "SQL ERROR: %s" % e
            return 0


databaseDrivers = {
    "sybase":DriverSybase,
    "interbase":DriverInterbase,
    "postres":DriverPostgres
    }
