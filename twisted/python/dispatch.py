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


## The following comment is from dispatch.py's original home, Original Gamer.
## http://sf.net/projects/originalgamer

## Justification for following evilness::
#
# At first I simply had the EventDispatcher class implement a bunch of callback
# methods that explicitly called the object that the event needed to get to,
# but this was still a lot of needless code. (wrapper methods are teh sux0r)
#
# So I tried to just do a lot of `self.foo = obj.bar' in `setWhateverObject'
# methods of EventDispatcher that WhateverObjects (i.e., ClientFrame,
# NetworkText) would call on initialization, but this had problems with
# objects trying to grab references to a callback method before the callback
# had been bound to the EventDispatcher.
#
# Thus, the next logical step is to create Handler, The Method That Wasn't.
# Now WhateverObjects simply call registerMethod on the dispatcher object,
# with an event-name to respond to and their callback method. Allowing
# disparate objects to talk to each other through a well-defined interface
# shouldn't be such a PITA any more.
#
# -- radix, feeling guilty for writing __getattr__/__call__ hacks


class Handler:
    """
    I'm a method that doesn't exist yet.
    """
    def __init__(self, name, method=None):
        self.name = name

    def __call__(self, *args, **kwargs):
        raise RuntimeError("Eep! A method hasn't been registered for the "
                           "%s event yet." % self.name)



class EventDispatcher:
    """
    A global event dispatcher for events in OGC.
    I'm used for any events that need to span disparate objects in the client.

    I should only be used when one object needs to signal an object that it's
    not got a direct reference to (unless you really want to pass it through
    here, in which case I won't mind).
    """


    def __init__(self):
        self.notRegisteredYet = {}


    def registerHandler(self, name, meth):
        # If we've given out any Handlers yet, we need to tell them
        # about the new method.
        if hasattr(self, name):
            import warnings
            warnings.warn("Honk! Already registered method %s for event %s, "
                          "but continuing to replace it with %s" %
                          (getattr(self, name), name, meth))
        if self.notRegisteredYet.has_key(name):
            for x in self.notRegisteredYet[name]:
                x.__call__ = meth
            del self.notRegisteredYet[name]

        setattr(self, name, meth)

    def autoRegister(self, obj):
        from twisted.python import reflect
        d = {}
        reflect.accumulateMethods(obj, d, 'event_')
        for k,v in d.items():
            self.registerHandler(k, v)


    def __getattr__(self, name):
        # if no one's registered a callback for this name, we'll give out
        # a Handler and make sure to remember it so registerHandler
        # can update it later.
        h = Handler(name)
        self.notRegisteredYet.setdefault(name, []).append(h)
        return h
