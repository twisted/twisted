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
    CREATE TABLE metrics_perspectives
    (
      identity_name  varchar(64),
      hostname       varchar(64),
      server_group   varchar(64),    
      server_type    integer
    );
    
    CREATE TABLE metrics_items
    (
      source_name    varchar(62),
      item_name      varchar(32),
      item_value     integer,
      collected      timestamp
    );
    
    CREATE TABLE metrics_events
    (
      source_name    varchar(64),
      event_name     varchar(32),
      event_time     timestamp
    );

    CREATE TABLE metrics_variables
    (
      variable_name  varchar(32),
      threshold      integer
    );
    
    """

    def getAllSources(self, callbackIn, errbackIn):
        """Loads all the known metrics sources.
        """
        sql = """SELECT identity_name, hostname, server_group, server_type
                 FROM metrics_perspectives"""
        return self.runQuery(sql, callbackIn, errbackIn)

    def getAllVariables(self, callbackIn, errbackIn):
        """Loads all metrics variables.
        """
        sql = """SELECT variable_name, threshold FROM metrics_variables"""
        return self.runQuery(sql, callbackIn, errbackIn)
        
    def getSourceInfo(self, source_name, callbackIn, errbackIn):
        """This gets the information for a metrics source by it's name. The info will be used
        to verify the connecting source.
        """
        sql = """SELECT source_name, source_name, hostname, server_type, shard
               from metrics_sources
               WHERE source_name = '%s'""" % (adbapi.safe(source_name) )
        return self.runQuery(sql, callbackIn, errbackIn)

    def insertMetricsItem(self, source_name, item_name, item_value):
        """Inserts a value for metrics item into the database.
        """
        sql = "INSERT INTO metrics_items\
               (source_name, item_name, item_value, collected)\
               VALUES\
               ('%s', '%s', %d, now())" % (adbapi.safe(source_name), adbapi.safe(item_name), item_value)

        return self.runOperation(sql)

    def insertMetricsEvent(self, source_name, event_name):
        """Inserts a metrics event into the database.
        """
        sql = "INSERT INTO metrics_events\
               (source_name, event_name, event_time)\
               VALUES\
               ('%s', '%s', now())" % (adbapi.safe(source_name), adbapi.safe(event_name) )

        return self.runOperation(sql)

    def getHistory(self, source_name, name, callbackIn, errbackIn):
        """Get the history of values for this item from this source
        """        
        sql = "SELECT item_value, collected\
               FROM metrics_items\
               WHERE source_name = '%s'\
               AND item_name = '%s'" % (adbapi.safe(source_name), adbapi.safe(name) )
        
        # use a defered
        return self.runQuery(sql, callbackIn, errbackIn)

