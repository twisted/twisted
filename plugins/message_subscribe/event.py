
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
from twisted.internet import passport
from twisted.python import reflect

class EventPublishPerspective(pb.Perspective):
    def perspective_subscribe(self, event, subscriber):
        self.service.subscribe(event, subscriber)

    def perspective_notifyEvent(self, event, *args, **kw):
        self.service.notifyEvent(event, args, kw)

class EventPublishService(pb.Service):

    def __init__(self, *args, **kw):
        apply(pb.Service.__init__, (self,)+args, kw)
        self.eventSubscribers = {}

    def subscribe(self, event, subscriber):
        if not self.eventSubscribers.has_key(event):
            self.eventSubscribers[event] = []
        self.eventSubscribers[event].append(subscriber)

    def notifyEvent(self, event, args, kw):
        for subscriber in self.eventSubscribers.get(event, ()):
            try:
                apply(subscriber.notifyEvent, (event,)+args, kw)
            except pb.ProtocolError:
                pass

    def getPerspectiveNamed(self, name):
        p = EventPublishPerspective("any")
        p.setService(self)
        return p


class EventNotifier(pb.Referenceable):

    def registerAll(self, perspective):
        dct = {}
        reflect.addMethodNamesToDict(self.__class__, dct, "event_")
        for name in dct.keys():
            perspective.subscribe(name, self)

    def remote_notifyEvent(self, event, *args, **kw):
        method = getattr(self, 'event_'+event, None)
        if method is None:
            return
        apply(method, args, kw)
