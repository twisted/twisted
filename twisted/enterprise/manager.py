
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
from twisted.enterprise import drivers
    
                    
class ManagerSingle:
    """Single threaded database request handler. This processes requests immediately and
    blocks on the database server returning results. This the base implementation of
    the database interface.

    Knows nothing of application level usernames or passwords.    

    """
    def __init__(self, service, server, database, username, password, host, port):
        self.service = service
        self.server = server
        self.database = database
        self.username = username
        self.password = password
        self.host = host
        self.port = port
        self.driver = None
        self.connected = 0
        self.total = 0
        self.driver = drivers.getDriver(service)
        if not self.driver:
            print "ERROR: Database driver not known"

    def connect(self):
        """Connection details vary by the database driver being used. This class
        makes a single database connection.
        """
        self.total = 0
        self.connection = self.driver.connect(self.server, self.database, self.username, self.password, self.host, self.port)
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
        else:
            request.errback(request.error)

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
    def __init__(self, service, server, database, username, password, host, port, numConnections = 1):
        ManagerSingle.__init__(self, service, server, database, username, password, host, port)
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

