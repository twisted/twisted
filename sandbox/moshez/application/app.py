from twisted.python import components, runtime, log
from twisted.application import service, persist
import os

class Application(service.MultiService, components.Componentized):

    processName = None

    def __init__(self, name, uid=None, gid=None):
        service.MultiService.__init__(self)
        components.Componentized.__init__(self)
        self.setName(name)
        self.setComponent(persist.IPersistable,
                          persist.Persistant(self, self.name))
        if runtime.platformType == "posix":
            if uid is None:
                uid = os.getuid()
            self.uid = uid
            if gid is None:
                gid = os.getgid()
            self.gid = gid

    def __repr__(self):
        return "<%s app>" % repr(self.name)

    def setEUID(self):
        try:
            os.setegid(self.gid)
            os.seteuid(self.uid)
        except (AttributeError, OSError):
            pass
        else:
            log.msg('set euid/egid %s/%s' % (self.uid, self.gid))

    def setUID(self):
        try:
            os.setgid(self.gid)
            os.setuid(self.uid)
        except (AttributeError, OSError):
            pass
        else:
            log.msg('set uid/gid %s/%s' % (self.uid, self.gid))

    def scheduleSave(self):
        from twisted.internet import reactor
        p = self.getComponent(persist.IPersistable)
        reactor.addSystemEventTrigger('after', 'shutdown', p.save, 'shutdown')
