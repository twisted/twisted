from twisted.python import log

class StateEventMachineType(type):
    def makeHandleGetter(klass, name):
        def helpful(self):
#            log.msg("looking up %s in state %s" % (name, self.state))
            return getattr(self, "handle_%s_%s" % (self.state, name))
        return helpful
    makeHandleGetter = classmethod(makeHandleGetter)

#    def __new__(klass, name, bases, attrs):
#        for e in name.events:
#            attrs[e] = property(klass.makeHandleGetter(e))
#        return type.__new__(klass, name, bases, attrs)

    def __init__(klass, name, bases, attrs):
        type.__init__(klass, name, bases, attrs)
#        print "making a class", klass, "with events", klass.events
        for e in klass.events:
            setattr(klass, e, property(klass.makeHandleGetter(e)))

