""" Database server interface service for Twisted.

This service provides a way to interact with a relational database.
This interface is database vendor neutral.
"""

import threading
import time

from twisted.internet import task

class DbManager:
    """Manager that handles connections and requests. A DbManager handles connections
    to a particular database. It chooses the apropriate database driver (for a vendor)
    based on the "service" string passed in.

    Currently, all connections log into the database using the same database login. The login
    gets specified in the "servertest.py" script currently as a server called 'max', a database
    called 'twisted', and a user 'twisted' with a password 'matrix'.

    The DbManager knows nothing of application level usernames or passwords.
    
    requests processing sequence is:
        main thread - request is added to the requests queue
        connection thread gets the request
        connection thread processes the request
        connection thread adds the request to the results queue
        main thread - in update, the callback for the request is run
        main thread - the request is deleted.
    
    """
    def __init__(self, service, server, database, username, password, numConnections = 1):
        self.server = server
        self.database = database
        self.username = username
        self.password = password
        self.service = service
        self.numConnections = numConnections
        self.connections = []
        self.requests = DbRequestQueue()
        self.results = DbRequestQueue()
        self.connected = 0
        self.driver = None

        ## Load the correct driver. Currently supported drivers are "sybase" and "postgres"
        if service == "sybase":
            import Sybase
            self.driver = Sybase
        elif service == "postgres":
	    import PoPy
	    self.driver = PoPy
        else:
            print "ERROR: Uknown database service"
   
    def connect(self):
        """Connect all the correct number of connections to the database/server specified.
        NOTE: auto_commit is false by default for sybase...
        """
        count = 0
	print "Connection %d times:" % self.numConnections
        for i in range(0,self.numConnections):
	    print "trying..."
            newConnection = DbConnection(self)
            if newConnection.connect():
                newConnection.start()
                self.connections.append(newConnection)
                count = count + 1
        if count == self.numConnections:
            self.connected = 1
            return 1
        else:
            print "Error in connection to database."
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

    def getRequest(self):
        """This is run in DbConnection threads NOT the main thread. it retrieves
        a request from the queue, but blocks if there are not requests until one arrives.
        """
        request = self.requests.waitForRequest()
        return request

    def addResult(self, request):
        """This is run from the DbConnection threads NOT the main thread. it posts the
        results of a request to the results queue to be run by the main thread in it's
        update loop.
        """
        self.results.addRequest(request)
        
class DbConnection(threading.Thread):
    """A thread that handles a database connection. The 'execute' method of DbRequests
    is run in this thread.
    """
    connectionID = 0
    
    def __init__(self, manager):
        threading.Thread.__init__(self)
        self.manager = manager
        self.id = DbConnection.connectionID
        DbConnection.connectionID = DbConnection.connectionID + 1

    def connect(self):
        """Connection details vary by the database driver being used.
	"""
	if self.manager.service == "sybase":
	    return self.connectSybase()
        elif self.manager.service == "postgres":
            return self.connectPostgres()
        else:
	    return 0

    def connectSybase(self):
        try:
            self.connection = self.manager.driver.connect(
		self.manager.server, 
		self.manager.username, 
		self.manager.password, 
		database=self.manager.database
		)
        except self.manager.driver.InternalError, e:
            print "unable to connect to database: %s" % repr(e)
            return 0
	self.running = 1
	return 1

    def connectPostgres(self):
        try:
            self.connection = self.manager.driver.connect( 'user=twisted dbname=twisted' )
	except self.manager.driver.DatabaseError, e:
            print "unable to connect to database: %s" % repr(e)
	    return 0
        self.running = 1
	print "Connected to postgres!!!"
        return 1
        
    def run(self):
        while self.running:
            # block for a request
            request = self.manager.getRequest()
            if not request:
                # empty request means time to go
                break

            # process the request
            result = 0
            try:
                result = request.execute(self.connection)
            except self.manager.driver.InternalError, e:
                text = "SQL ERROR:\n"
                self.error = e[0][1]
                
                for k in self.error.keys():
                    text = text +  "    %s: %s\n" % (k, self.error[k])
                request.status = 0
                print text
	    except self.manager.driver.DatabaseError, e:
                print "SQL ERROR: %s" % e
		self.error = e
		request.status = 0

            newTask = task.Task()
	    newTask.addWork(request.callback, request.results)

	    task.schedule(newTask)

    def close(self):
        #print "Thread (%d): Closing" % ( self.id)
        self.running = 0
        self.connection.close()

class DbRequestQueue:
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
            
class DbRequest:
    """base class for database requests to be executed in dbconnection threads.
    the method 'execute' will be run. 'self.callback' will be executed after the request
    has been processed (in the main thread) with the data in 'self.results'
    """
    lastId = 0
    
    def __init__(self, callback):
        self.status = 0
        self.error = None
        self.results = None
        self.callback = callback        
        self.id = DbRequest.lastId
        DbRequest.lastId = DbRequest.lastId + 1
        
    def execute(self, connection):
        """Method to be implemented by derived classes. this is run when the
        request is processed. This will be run within a try/except block that
        catched database exceptions.  The results of the query should be stored in
        the member variable 'results'. set self.status to 1 for successful execution.
        """
        print "WARNING: empty DBRequest being run"
        self.status = 1
