
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

from twisted.spread import pb
from twisted.python import defer
from twisted.web import widgets
class EchoDisplay(widgets.Presentation):
    template = """<H1>Welcome to my widget, displaying %%%%echotext%%%%.</h1>
    <p>Here it is: %%%%getEchoPerspective()%%%%</p>"""
    echotext = 'hello web!'
    def getEchoPerspective(self):
        d = defer.Deferred()
        pb.connect(d.callback, d.errback, "localhost", pb.portno,
                   "guest", "guest",      "pbecho", "guest", 1)
        d.addCallbacks(self.makeListOf, self.formatTraceback)
        return ['<b>',d,'</b>']
    def makeListOf(self, echoer):
        d = defer.Deferred()
        echoer.echo(self.echotext, pbcallback=d.callback, pberrback=d.errback)
        d.addCallbacks(widgets.listify, self.formatTraceback)
        return [d]
if __name__ == "__main__":
    from twisted.web import server
    from twisted.internet import app
    a = app.Application("pbweb")
    gdgt = widgets.Gadget()
    gdgt.widgets['index'] = EchoDisplay()
    a.listenTCP(8080, server.Site(gdgt))
    a.run()
