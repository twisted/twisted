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

"""Gadgets to interact with the metrics data in real-time
"""


## WARNING - this is experimental code.
## DO NOT USE THIS!!!

import string
import time

from twisted.web import widgets
from twisted.python import defer


"""The metrics web application has these functional pages:
     intro   - (/)        - Show the available host machines
     status  - (/status)  - Show the status of the machine
     details - (/detail)  - show the details of a metric
  
"""
class MetricsGadget(widgets.Gadget, widgets.StreamWidget):
    title = " "
    
    def __init__(self, app, service):
        widgets.Gadget.__init__(self)
        self.app = app
        self.service = service
        self.putWidget('history',  HistoryGadget(self.app, self.service))
        self.putWidget('details', DetailsGadget(self.app, self.service))

    def display(self, request):
        """Display the list of metrics sources. This is only called if there is no URI.
        """
        l = []
        l.append( '<H3> Metrics Sources at <i>%s</i></H3>\n' % time.asctime() )
        l.append( '<table cellpadding=4 cellspacing=1 border=0 width="95%">')
        l.append( '<tr bgcolor="#ff9900">' )
        l.append( '<td COLOR="#000000" width=30%%><b> Source Name </b> </td>' )
        l.append( '<td COLOR="#000000" width=20%%><b> Group </b> </td>' )        
        l.append( '<td COLOR="#000000"><b> Active </b> </td>' )
        l.append( '<td COLOR="#000000"><b> Status </b> </td>' )                
        l.append( '</tr>\n' )
        
        for name in self.service.sources.keys():
            source = self.service.sources[name]
            l.append("<tr> <td> <a href='/details/?name=%s'>%s</a> </td> <td> %s </td>" % (name, name, source.server_group) )
            l.append("<td> %s </td> <td> %s </td> </tr>" % (source.getActiveString(), source.getStatusString()) )

        l.extend( '</table>' )
        l.extend( '<hr> <i> Twisted Metrics System </i>' )
        return l

class DetailsGadget(widgets.Gadget, widgets.StreamWidget):
    title = " "
    
    def __init__(self, app, service):
        widgets.Gadget.__init__(self)
        self.app = app
        self.service = service
        self.putWidget('history',  HistoryGadget(self.app, self.service))

    def display(self, request):
        """Display the list of metrics sources. This is only called if there is no URI.
        """
        self.name = request.args.get('name',[0])[0]                        
        l = []
        l.append( '<H3> Details for %s at <i>%s</i></H3>\n' % (self.name, time.asctime()) )
        l.append( '<table cellpadding=4 cellspacing=1 border=0 width="95%">')
        l.append( '<tr bgcolor="#ff9900">' )
        l.append( '<td COLOR="#000000" width=30%%><b> Metrics Variable </b> </td>' )
        l.append( '<td COLOR="#000000" width=20%%><b> Value </b> </td>' )        
        l.append( '<td COLOR="#000000"><b> Threshold </b> </td>' )
        l.append( '<td COLOR="#000000"><b> Collected </b> </td>' )                
        l.append( '</tr>\n' )
        
        source = self.service.sources[self.name]
        for varName in source.variables.keys():
            value = source.variables[varName]
            threshold = self.service.variables[varName]
            if value > threshold:
                l.append("<tr bgcolor=#FF0000>")
            else:
                l.append("<tr>")
            l.append("<td> <a href='/history/?sname=%s&vname=%s'>%s</a> </td> <td> %d </td> "  % (self.name, varName, varName, value) )
            l.append("<td> %d </td> <td> %s </td> </tr>\n" % (threshold, time.asctime() ) )

        l.extend( '</table>' )
        l.extend( '<hr> <i> Twisted Metrics System </i>' )
        return l


class HistoryGadget(widgets.Gadget, widgets.StreamWidget):
    """Displays the history of values for a 
    """
    
    title = " "

    def __init__(self, app, service):
        widgets.Gadget.__init__(self)
        self.app = app
        self.service = service

    def display(self, request):
        self.sname = request.args.get('sname',[0])[0]
        self.vname = request.args.get('vname',[0])[0]
        print "Getting history for variable %s on host: %s" % (self.vname, self.sname)
        return [self.service.manager.getHistory(self.sname, self.vname).addCallbacks(self.onHistoryData)]

    def onHistoryData(self, data):
        l = []
        l.extend( '<h2> History for Source #%s for Variable "%s":</h2>' % (self.sname, self.vname) )
        l.extend( '<table cellpadding=4 cellspacing=1 border=0 width="95%">')
        l.extend( '<tr bgcolor="#ff9900">' )
        l.extend( '<td COLOR="#000000"><b> Item Value </b> </td>' )
        l.extend( '<td COLOR="#000000"><b> Collected time </b> </td>' )
        l.extend( '</tr>\n' )

                
        for (value, collected) in data:
            l.extend("<tr>" )
            l.extend("<td>  %d</td>" % ( value) )
            l.extend("<td> %s </td>" % collected)
            l.extend("</tr>\n")

        l.extend( '</table><br>' )
        l.extend( '<hr> <i> Twisted Metrics </i>' )        
        return l
