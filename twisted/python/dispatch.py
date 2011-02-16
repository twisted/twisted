# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

import warnings
warnings.warn(
    "Create your own event dispatching mechanism, "
    "twisted.python.dispatch will soon be no more.",
    DeprecationWarning, 2)


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
