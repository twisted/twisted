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
""" module to gather operating system statistics for use in twisted.metrics.
The stats that will be gathered are:

   - CPU utilization
   - Memory Available (in Kbytes)
   - # of network connections
   - # of processes
   - System calls per second

"""

# system imports
import time

# sibling imports
import client

class MetricsCollector:
    def __init__(self):
        pass

class Win2kMetricsCollector(MetricsCollector):
    """collects stats using the PdH interaface on win2K. This module is single-threaded
    python - logging occurs in the background, but there is only a single python thread in use.
    """
    
    win32Items = [
        ("cpu"         ,"Processor(_Total)", "% Processor Time"),
        ("memory"      ,"Memory",            "Available KBytes"),    
        ("connections" ,"TCP",               "Connections Established"),
        ("processes"   ,"System",            "Processes"),
        ("syscalls"    ,"System",            "System Calls/sec")
        ]

    collectFrequency = 3 # how often to collect the values for the above items
    
    def __init__(self, reportFrequency, hostname, port):

        # create the metrics client
        self.metricsClient = client.MetricsClientComponent( reportFrequency, hostname, port)
        self.metricsClient.doLogin("test", "sss")

        # setup variables
        self.metricsClient.createStateVariable("cpu", self.getCPU,self.collectFrequency)
        self.metricsClient.createStateVariable("memory", self.getMemory, self.collectFrequency)
        self.metricsClient.createStateVariable("connections", self.getConnections, self.collectFrequency)
        self.metricsClient.createStateVariable("processes", self.getProcesses, self.collectFrequency)
        self.metricsClient.createStateVariable("syscalls", self.getSyscalls, self.collectFrequency) 

        # create holding variable
        self.holding = {}
        
        # setup PdH Interface
        import win32pdhquery
        self.collector = win32pdhquery
        self.query = self.collector.Query()
        for (key, object, instance) in self.win32Items:
            print "Adding \\%s\\%s" % ( object, instance)
            self.query.addperfcounter(object, instance)

        self.query.open()

        # throw away first sample.
        time.sleep(0.01)
        self.query.collectdata()
        self.last = time.time()

    def update(self):
        """this should be called periodically to collect stats.
        """
        now = time.time()        
        if now - self.last > self.collectFrequency:
            print "collecting data"
            (cpu, memory, connections, processes, syscalls) =  self.query.collectdata()
            self.holding["cpu"] = cpu
            self.holding["memory"] = memory
            self.holding["connections"] = connections
            self.holding["processes"] = processes
            self.holding["syscalls"] = syscalls
            self.last = now

            self.metricsClient.update()

    def __del__(self):
        self.query.close()

    def getCPU(self):
        return self.holding["cpu"]

    def getMemory(self):
        return self.holding["memory"]

    def getConnections(self):
        return self.holding["connections"]

    def getProcesses(self):
        return self.holding["processes"]

    def getSyscalls(self):
        return self.holding["syscalls"]
    
