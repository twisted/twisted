class StateEventMachineType(type):
    def makeHandleGetter(klass, name):
        def helpful(self):
            return getattr(self, "handle_%s_%s" % (self.state, name))
        return helpful
    makeHandleGetter = classmethod(makeHandleGetter)

    def __new__(klass, name, bases, attrs):
        for e in attrs.events:
            attrs[e] = property(klass.makeHandleGetter(e))
        return type.__new__(klass, name, bases, attrs)

