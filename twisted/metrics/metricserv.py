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

from twisted.internet import passport
from twisted.spread import pb
from twisted.enterprise import adbapi
from twisted.python import defer

import metricsdb

class MetricsManagerService(pb.Service):

    def __init__(self, name, app, dbpool):
        pb.Service.__init__(self, name, app)
        self.dbpool = dbpool
        self.sourcesCache = {}  # holds the last value of each metrics item for each source.
                                # this is a hash of source_ids.
                                # each map item is a map of name to value.
                                
        self.sources = {}       # map of sources by source_id

        self.manager = metricsdb.MetricsDB(dbpool)
        #self.loadSources()

    def loadSources(self):
        #NOTE: THIS DOES NOT EVER WORK!!!
        print "Loading metrics sources:"        
        return self.manager.getAllSources(self.gotSources, self.sourceError)
        
        
    def gotSources(self, data):
        print "gotSources:"
        for (source_id, name, host, server_type, shard) in data:
            print "Loaded source: (%d) %s %s" % (source_id, host, shard)
            self.sources[source_id] = (name, host, server_type, shard)
        print "Loaded all metrics sources"

    def sourceError(self, error):
        print "ERROR loading sources", repr(error)

    def createPerspective(self, name):
        """Create a perspective from self.perspectiveClass and add it to this service.
        """
        p = MetricsClient(name)
        self.perspectives[name] = p
        p.setService(self)
        return p

    def insertMetricsItem(self, source_id, name, value):
        # make a local copy
        if self.sourcesCache.has_key(source_id):
            source = self.sourcesCache[source_id]
            source[name] = (value, time.asctime())
        else:
            source = {}
            source[name] = (value, time.asctime())
            self.sourcesCache[source_id] = source
        # push to the database
        self.manager.insertMetricsItem(source_id, name, value)
        
class MetricsClient(pb.Perspective):

    def perspective_submitItems(self, metricsItems):
        self.source_id = 1 #TODO: make this real
        for (name, value, when) in metricsItems:
            self.service.insertMetricsItem(self.source_id, name, value)

    def perspective_submitEvent(self, name, when):
        self.source_id = 1 #TODO: make this real
        self.service.manager.insertMetricsEvent(self.source_id, name, when)
        
