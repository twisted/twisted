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
from twisted.application import service

class TimerService(service.Service):

    def __init__(self, step, callable, *args, **kwargs):
        self.step = step
        self.callable = callable
        self.args = args
        self.kwargs = kwargs

    def __getstate__(self):
        d = service.Service.__getstate__(self)
        if d.has_key('_call'):
            del d['_call']
        return d

    def startService(self):
        service.Service.startService(self)
        self._call = reactor.callLater(self.step, self._setupCall)

    def _setupCall(self):
        self.callable(*self.args, **self.kwargs)
        self._call = reactor.callLater(self.step, self._setupCall)

    def stopService(self):
        service.Service.stopService(self)
        self._call.cancel()
