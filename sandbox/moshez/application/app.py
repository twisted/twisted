# Twisted, the Framework of Your Internet
# Copyright (C) 2001-2003 Matthew W. Lefkowitz
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
#
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

    def scheduleSave(self):
        from twisted.internet import reactor
        p = persist.IPersistable(self)
        reactor.addSystemEventTrigger('after', 'shutdown', p.save, 'shutdown')
