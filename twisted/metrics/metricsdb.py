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
# Metrics System database interface
#
# WARNING: experimental database code!


from twisted.python import defer
from twisted.enterprise import adbapi


class MetricsDB(adbapi.Augmentation):
    """Class to provide an interface to the metrics database. Use cases:
          - get info for a source 
          - insert a metrics item
          - insert a metrics event
    """

    schema = """
    CREATE TABLE metrics_sources
    (
    source_id    int,
    source_name  varchar(32),
    hostname     varchar(32),
    server_type  int,
    shard        varchar(32)
    );
    
    CREATE TABLE metrics_items
    (
    source_id	int,
    item_name  varchar(32),
    item_value int,
    collected  timestamp
    );
    
    CREATE TABLE metrics_events
    (
    source_id   int,
    event_name  varchar(32),
    event_time  timestamp
    );
    """

    def getAllSources(self, callbackIn, errbackIn):
        """Loads all the known metrics sources.
        """        
        sql = "SELECT source_id, source_name, hostname, server_type, shard from metrics_sources"
        return self.runQuery(sql, callbackIn, errbackIn)
        
    def getSourceInfo(self, source_name, callbackIn, errbackIn):
        """This gets the information for a metrics source by it's name. The info will be used
        to verify the connecting source.
        """

        sql = """SELECT source_id, source_name, hostname, server_type, shard
               from metrics_sources
               WHERE source_name = '%s'""" % (source_name)
        return self.runQuery(sql, callbackIn, errbackIn)

    def insertMetricsItem(self, source_id, item_name, item_value):
        """Inserts a value for metrics item into the database.
        """

        sql = "INSERT INTO metrics_items\
               (source_id, item_name, item_value, collected)\
               VALUES\
               (%d, '%s', %d, now())" % (source_id, item_name, item_value)

        return self.runOperation(sql)

    def insertMetricsEvent(self, source_id, event_name):
        """Inserts a metrics event into the database.
        """

        sql = "INSERT INTO metrics_events\
               (source_id, event_name, event_time)\
               VALUES\
               (%d, '%s', now())" % (source_id, event_name)

        return self.runOperation(sql)

    def getHistory(self, source_id, name, callbackIn, errbackIn):
        """Get the history of values for this item from this source
        """        
        sql = "SELECT item_value, collected\
               FROM metrics_items\
               WHERE source_id = %d\
               AND item_name = '%s'" % (source_id, name)
        
        # use a defered
        return self.runQuery(sql, callbackIn, errbackIn)

