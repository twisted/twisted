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

# System Imports
import string
import os
import sys

# Twisted Imports
from twisted.spread import pb
from twisted.python import delay, authenticator

# Sibling Imports
import manager
import requests

class Service(pb.Service):
    """
    This service manages users that request to interact with the database. It keeps track the registered
    database Request classes and does the loading of Requests from the directories passed in on startup.

    Request classes will be imported automatically on startup from the requestDirectories specified.
    To be imported the file name must be of the format "dbrequest*.py" and must implement a module
    level method called "loadRequests". This method should call registerRequestClass for each of the
    database Request classes in the module.

    The default configuration reads request classes from the directory "userRequests"
    """
    def __init__(self, manager, app, requestDirectories, name='twisted.enterprise.db'):
        pb.Service.__init__(self, name, app)
        self.manager = manager
        self.requestMap = {}
        self.requestDirectories = requestDirectories
        self.loadDefaultRequests()
        self.loadRequests()

    def startService(self):
        print "Starting db service"
        self.manager.connect()

    def registerRequestClass(self, requestName, requestClass):
        if self.requestMap.has_key(requestName):
            print "ERROR: Request class already exists"
            return 0
        else:
            self.requestMap[requestName] = requestClass
            print "Registered Request Class '%s'" % requestName
            return 1
        
    def loadDefaultRequests(self):
        """Loads the built-in request classes from the requests.py file. These have the wrapper "__"
        around their names as they are internal built-in classe, not user classes.
        """
        self.registerRequestClass("__generic__", requests.GenericRequest)
        self.registerRequestClass("__adduser__", requests.AddUserRequest)
        self.registerRequestClass("__password__", requests.PasswordRequest)

    def loadRequests(self):
        """Loads any database Request classes from the list of directories stored in requestDirectories.
        """
        for dir in self.requestDirectories:
            if os.path.exists(dir):
                dir = os.path.abspath(dir)
                sys.path.append(dir)
                files = os.listdir(dir)
                for file in files:
                    prefix = file[0:9]
                    suffix = file[-3:]
                    moduleName = file[0:-3]
                    print "Found file %s  '%s' '%s'" % ( file, prefix, suffix )
                    if prefix == "dbrequest" and suffix == ".py":
                        mod = __import__(moduleName)
                        mod.loadRequests(self)

    def getRequestClass(self, name):
        """Lookup a Request class by name"""
        if self.requestMap.has_key(name):
            return self.requestMap[name]
        else:
            return None

class DbUser(pb.Perspective):
    """A User that wants to interact with the database.
    """
    def perspective_simpleSQL(self, sql, args, client):
        """Basic SQL submission method. This calls simpleSQLResults or simpleSQLError on the client
        to pass results back.
        """
        print "Got SQL request:" , sql, " args: ", args
        newRequest = requests.GenericRequest(sql, args, client.simpleSQLResults, client.simpleSQLError)
        self.service.manager.addRequest(newRequest)

    def perspective_callRequest(self, requestName, args, client):
        """this method allows the client to call any registered Request. It will invoke either the method
        requestResults or requestError on the client object when the request is done.
        """
        print "got callRequest for %s" % requestName
        requestClass = self.service.getRequestClass(requestName)
        if not requestClass:
            self.status = 0
            return
        fullArgs = args + (client.requestResults, client.requestError)
        newRequest = apply(requestClass, fullArgs)
        self.service.manager.addRequest(newRequest)
