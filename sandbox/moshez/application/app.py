from twisted.python import components
from twisted.application import service, persist

class Application(MultiService, component.Componentized):

    processName = None

    def __init__(self, name, uid=None, gid=None):
        MultiService.__init__(self)
        self.setName(name)
        self.addService(self) # a turtle!
        self.setComponent(Persistable, Persistant(self, self.name))
        if platform.getType() == "posix":
            if uid is None:
                uid = os.getuid()
            self.uid = uid
            if gid is None:
                gid = os.getgid()
            self.gid = gid

    def __repr__(self):
        return "<%s app>" % repr(self.name)

    def setEUID(self):
        """Retrieve persistent uid/gid pair (if possible) and set the current
        process's euid/egid.
        """
        try:
            os.setegid(self.gid)
            os.seteuid(self.uid)
        except (AttributeError, OSError):
            pass
        else:
            log.msg('set euid/egid %s/%s' % (self.uid, self.gid))

    def setUID(self):
        """Retrieve persistent uid/gid pair (if possible) and set the current
        process's uid/gid
        """
        try:
            os.setgid(self.gid)
            os.setuid(self.uid)
        except (AttributeError, OSError):
            pass
        else:
            log.msg('set uid/gid %s/%s' % (self.uid, self.gid))

    def save(self, *args, **kwargs):
        comp = self.getComponent(IPersistable)
        if not comp:
        comp.save(*args, **kwargs)
      
    def logPrefix(self):
        """A log prefix which describes me.
        """
        return "*%s*" % self.name

    # An alias
    def bindPorts(self):
        self.preStartService()

    def run(self, save=1, installSignalHandlers=1):
        self.preStartService()
        from twisted.internet import reactor
        reactor.addSystemEventTrigger('before', 'shutdown', self.stopService)
        if save:
            reactor.addSystemEventTrigger('after', 'shutdown',
                                          self.save, 'shutdown')
        log.callWithLogger(self, reactor.run,
                           installSignalHandlers=installSignalHandlers)
