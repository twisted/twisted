
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
from twisted.internet import app
class SimplePerspective(pb.Perspective):
    def perspective_echo(self, text):
        print 'echoing',text
        return text
class SimpleService(pb.Service):
    def getPerspectiveNamed(self, name):
        p = SimplePerspective(name)
        p.setService(self)
        return p
if __name__ == '__main__':
    import pbecho
    appl = app.Application("pbecho")
    pbecho.SimpleService("pbecho",appl).getPerspectiveNamed("guest").makeIdentity("guest")
    appl.listenTCP(pb.portno, pb.BrokerFactory(pb.AuthRoot(appl)))
    appl.save("start")
