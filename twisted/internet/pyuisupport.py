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

"""This module integrates PyUI with twisted.internet's mainloop.

API Stability: unstable

Maintainer: U{Jp Calderone<mailto:exarkun@twistedmatrix.com>}

See doc/examples/pyuidemo.py for example usage.
"""

# System imports
import pyui

def _guiUpdate(reactor, delay):
    pyui.draw()
    if pyui.update() == 0:
        pyui.quit()
        reactor.stop()
    else:
        reactor.callLater(delay, _guiUpdate, reactor, delay)


def install(ms=10, reactor=None, args=(), kw={}):
    """
    Schedule PyUI's display to be updated approximately every C{ms}
    milliseconds, and initialize PyUI with the specified arguments.
    """
    d = pyui.init(*args, **kw)

    if reactor is None:
        from twisted.internet import reactor
    _guiUpdate(reactor, ms / 1000.0)
    return d

__all__ = ["install"]
