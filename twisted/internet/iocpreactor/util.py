# Twisted, the Framework of Your Internet
# Copyright (C) 2004 Matthew W. Lefkowitz
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

from twisted.python import log

class StateEventMachineType(type):
    def makeHandleGetter(klass, name):
        def helpful(self):
#            log.msg("looking up %s in state %s" % (name, self.state))
            return getattr(self, "handle_%s_%s" % (self.state, name))
        return helpful
    makeHandleGetter = classmethod(makeHandleGetter)

    def makeMethodProxy(klass, name):
        def helpful(self, *a, **kw):
            return getattr(self, "handle_%s_%s" % (self.state, name))(*a, **kw)
        return helpful
    makeMethodProxy = classmethod(makeMethodProxy)

#    def __new__(klass, name, bases, attrs):
#        for e in name.events:
#            attrs[e] = property(klass.makeHandleGetter(e))
#        return type.__new__(klass, name, bases, attrs)

    def __init__(klass, name, bases, attrs):
        type.__init__(klass, name, bases, attrs)
#        print "making a class", klass, "with events", klass.events
        for e in klass.events:
#            setattr(klass, e, property(klass.makeHandleGetter(e)))
            setattr(klass, e, klass.makeMethodProxy(e))

