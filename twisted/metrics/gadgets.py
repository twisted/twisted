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

from sim.server import engine, player

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
        #self.putWidget('details', DetailsGadget(self.app, self.service))

    def display(self, request):
        """Display the list of metrics sources. This is only called if there is no URI.
        """
        l = []
        l.append('''<H3> Active Metrics Sources at <i>%s</i></H3>
                 <table cellpadding=4 cellspacing=1 border=0 width="95%%">
                 <tr bgcolor="#ff9900">
                 <td COLOR="#000000"><b> Metrics Item Name </b> </td>
                 <td COLOR="#000000"><b> Value </b> </td>
                 <td COLOR="#000000"><b> Last Collected </b> </td>
                 </tr>
                 ''' % time.asctime())
        
        for id in self.service.sourcesCache.keys():
            source = self.service.sourcesCache[id]
            l.extend( 'Source: #%d <br>\n' % id)
            for vname in source.keys():
                (value, collected) = source[vname]
                l.append( '<tr> <td><a href="/history/?source_id=%d&amp;vname=%s"> %s </a> </td><td> %d </td><td>%s</d></tr>\n' % (id, vname, vname, value, collected) )

        l.append('</table>'
                 '<hr> <i> Twisted Metrics System </i>' )
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
        self.source_id = int(request.args.get('source_id',[0])[0])
        self.vname = request.args.get('vname',[0])[0]
        
        print "Getting history for variable %s on host: %d" % (self.vname, self.source_id)
        d = self.service.manager.getHistory(self.source_id, self.vname, self.onHistoryData, self.onHistoryError)
        return [d]

    def onHistoryData(self, data):
        l = []
        l.extend( '<h2> History for Source #%d for Metrics Item "%s":</h2>' % (self.source_id, self.vname) )
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

    def onHistoryError(self, error):
        print error
        return "ERROR: " + repr(error)

