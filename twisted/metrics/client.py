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
# system includes

# library includes
from twisted.spread import pb
from twisted.internet import tcp

import time

class MetricsClientComponent:
    """This is a component which manages metrics variables and communicates
    with the MetricsManager Server.
    """
    
    def __init__(self, reportFrequency, hostname, port):
        self.hostname = hostname
        self.port = port
        self.reportFrequency = reportFrequency # frequency to report to the manager server
        self.counterVariables = {}             # map to a tuple of (value, frequency, last)
        self.stateVariables = {}               # map to a tuple of (callback, frequency, last)
        self.metricsItems = []                 # items recorded ready to be sent. tuples of (name, value, when)
        self.lastReport = time.time()
        
    def doLogin(self, user, pasw):
        print "Connecting to %s on %d as %s" % (self.hostname, self.port, user)
        self.username = user
        self.pasw = pasw
        pb.getObjectAt(self.hostname, self.port, self.gotAuthRoot, self.failedLogin)

    def gotAuthRoot(self, authroot):
        print "gotAuthRoot", authroot
        name = self.username
        pb.AuthClient(authroot, None, "metrics", self.username,
                      self.pasw, self.connected, self.failedLogin, name)
    
    def failedLogin(self, data):
        """This is called on a failed connect."""
        print "Failed:", data

    def connected(self, client):
        """This is called when a connection is established"""
        print "connected!"
        self.client = client

    def createCounterVariable(self, name, frequency):
        if self.counterVariables.has_key(name):
            print "ERROR: counter %s already exists" % name
            return
        self.counterVariables[name] = (0, frequency, time.time())

    def createStateVariable(self, name, callback, frequency):
        if self.stateVariables.has_key(name):
            print "ERROR: counter %s already exists" % name
            return
        self.stateVariables[name] = (callback, frequency, time.time())

    def incrementCounterVariable(self, name):
        if  self.counterVariables.has_key(name):
            (value, frequency, last) = self.counterVariables[name]
            self.counterVariables[name] = (value+1, frequency, last)
        else:
            print "ERROR: no counter %s" % name

    def recordMetricsItem(self, name, value, when):
        print "recorded %s value %d" % (name, value)
        self.metricsItems.append( (name, value, when) )
        
    def update(self):
        now = time.time()

        # update counter variables
        for k in self.counterVariables.keys():
            (value, frequency, last) = self.counterVariables[k]
            if now - last > frequency:
                self.recordMetricsItem(k, value, now)
                self.counterVariables[k] = (0, frequency, now)

        # update state variables
        for k in self.stateVariables.keys():
            (callback, frequency, last) = self.stateVariables[k]
            if now - last > frequency:
                self.recordMetricsItem(k, callback(), now)
                self.stateVariables[k] = (callback, frequency, now)

        # check for reporting to manager server
        if now - self.lastReport > self.reportFrequency:
            print "sending %d metrics items" % len(self.metricsItems)            
            self.lastReport = now
            self.client.submitItems(self.metricsItems)
            self.metricsItems = []

            


