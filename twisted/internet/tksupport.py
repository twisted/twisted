
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

"""This module integrates Tkinter with twisted.internet's mainloop.

API Stability: semi-stable

Maintainer: U{Itamar Shtull-Trauring<mailto:twisted@itamarst.org>}
"""

# Sibling Imports
# XXX TODO: actually watch file descriptors on UNIX, using IO timeouts...

def _doReactorIter(delay, reactor, widget):
    reactor.iterate()
    widget.after(delay, _doReactorIter, delay, reactor, widget)

def install(widget, delay = 6):
    from twisted.internet import reactor
    reactor.startRunning() # I only support PosixReactorBase subclasses anyway
    widget.after(delay, _doReactorIter, delay, reactor, widget)


__all__ = ["install"]
