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

"""Service for the metrics manager.

This accepts pb connections for metrics clients which will submit metrics items
to the server to be written to the database.

This caches the last value reported for each metric for each machine. (This information
can be viewed by a web interface...?) 

"""
import time
import copy

from twisted.internet import passport
from twisted.spread import pb
from twisted.enterprise import adbapi
from twisted.python import defer, log

import metricsdb

class MetricsManagerService(pb.Service):
    """On initialization, load the set of metrics sources and the set of
    metrics variables from the database.
    """
    def __init__(self, name, app, dbpool):
        pb.Service.__init__(self, name, app)
        self.dbpool = dbpool
        self.sources = {}       # map of known sources by name
        self.variables = {}     # map of known variables by name

        self.manager = metricsdb.MetricsDB(dbpool)

    def delayedInit(self):
        self.loadVariables()

    def loadVariables(self):
        """Load all the metrics variables from the db.
        """
        return self.manager.getAllVariables().addCallback(self.gotVariables)

    def loadSources(self):
        """Load all the metrics sources from the db.
        """
        log.msg("Loading metrics sources:")
        return self.manager.getAllSources().addCallback(self.gotSources)

    def gotVariables(self, data):
        for (name, threshold) in data:
            print "Loaded variables: (%s) threashold = %d"  % (name, threshold)
            self.variables[name] = threshold
        self.loadSources()

    def gotSources(self, data):
        for (name, host, server_group, server_type) in data:
            print "Loaded source: (%s) %s %s" % (name, host, server_group)
            self.sources[name] = MetricsSource(name, host, server_group, server_type, self.variables, self)
        print "Loaded all metrics sources"
            
    def createPerspective(self, name):
        """Create a perspective from self.perspectiveClass and add it to this service.
        """
        p = MetricsClient(name)
        self.perspectives[name] = p
        p.setService(self)
        return p

    def insertMetricsItem(self, sourceName, name, value):
        # make a local copy
        source = self.sources[sourceName]
        source.cache(name, value, time.asctime())
        # push to the database
        self.manager.insertMetricsItem(sourceName, name, value)

    def setActive(self, perspectiveName, value):
        self.sources[perspectiveName].setActive(value)

class MetricsClient(pb.Perspective):

    def perspective_submitItems(self, metricsItems):
        for (name, value, when) in metricsItems:
            self.service.insertMetricsItem(self.perspectiveName, name, value)

    def perspective_submitEvent(self, name, when):
        self.service.manager.insertMetricsEvent(self.perspectiveName, name, when)

    def attached(self, reference, identity):
        self.service.setActive(self.perspectiveName, 1)
        return pb.Perspective.attached(self, reference, identity)

    def detached(self, reference, identity):
        self.service.setActive(self.perspectiveName, 0)        
        return pb.Perspective.detached(self, reference, identity)
    
class MetricsSource:
    def __init__(self, name, hostname, server_group, server_type, variables, service):
        self.name = name
        self.hostname = hostname
        self.server_group = server_group
        self.server_type = server_type
        self.service = service
        
        self.active = 0
        self.alert = 0
        self.alertString = ""

        self.variables = {}
        for k in self.service.variables.keys():
            self.variables[k] = 0
        

    def setActive(self, value):
        print "Setting %s to %d"  %( self.name, value)
        self.active = value
        if value == 0:
            self.alert = 0

    def getActiveString(self):
        if self.active:
            return "Active"
        else:
            return "--"

    def getStatusString(self):
        if self.alert:
            return "<b>ALERT: %s</b>" % self.alertString
        else:
            return "--"

    def cache(self, name, value, when):
        self.variables[name] = value
        self.checkAlertStatus()

    def checkAlertStatus(self):
        self.alert = 0
        self.alertString = ""
        for name in self.variables.keys():
            value = self.variables[name]
            if value > self.service.variables[name]:
                self.alert = 1
                self.alertString = "%s is at %s (%s)" %  (name, value, self.service.variables[name])

