# Twisted, the Framework of Your Internet
# Copyright (C) 2001-2002 Matthew W. Lefkowitz
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


class EventDispatcher:
    """
    A global event dispatcher for events.
    I'm used for any events that need to span disparate objects in the client.

    I should only be used when one object needs to signal an object that it's
    not got a direct reference to (unless you really want to pass it through
    here, in which case I won't mind).

    I'm mainly useful for complex GUIs.
    """

    def __init__(self, prefix="event_"):
        self.prefix = prefix
        self.callbacks = {}


    def registerHandler(self, name, meth):
        self.callbacks.setdefault(name, []).append(meth)


    def autoRegister(self, obj):
        from twisted.python import reflect
        d = {}
        reflect.accumulateMethods(obj, d, self.prefix)
        for k,v in d.items():
            self.registerHandler(k, v)


    def publishEvent(self, name, *args, **kwargs):
        for cb in self.callbacks[name]:
            cb(*args, **kwargs)
