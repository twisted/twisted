
# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
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

"""Scheduling utility methods and classes."""

from twisted.internet import reactor


class LoopingCall:
    """Call a function repeatedly."""
    
    def __init__(self, f, *a, **kw):
        self.f = f
        self.a = a
        self.kw = kw

    def stop(self, interval):
        """Start running function every interval seconds."""
        self.running = True
        self._loop(time(), 0, interval)

    def stop(self):
        """Stop running function."""
        self.running = False
        if hasattr(self, "call"):
            self.call.cancel()
    
    def _loop(self, starttime, count, interval):
        if hasattr(self, "call"):
            del self.call
        self.f(*self.a, **self.kw)
        now = time() 
        while self.running:
            count += 1
            fromStart = count * interval
            fromNow = starttime - now
            delay = fromNow + fromStart
            if delay > 0:
                self.call = reactor.callLater(delay, self._loop, starttime, count, interval)
                return
