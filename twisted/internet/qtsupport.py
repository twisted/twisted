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

"""
This module provides experimental support for the PyQt mainloop.

This may go away in the future - the recommended way of using Qt is
the Qt reactor support (qtreactor.py).

In order to use this support, simply do the following::

    |  # given a QApplication instance qtApp:
    |  from twisted.internet import qtsupport
    |  qtsupport.install(qtApp)

Then use twisted.internet APIs as usual.  The other methods here are not
intended to be called directly.
"""

__all__ = ['install']

# System Imports
from qt import QApplication

# Sibling Imports
import reactor


class QTSupport:
    """Qt based reactor."""

    def __init__(self, app):
        self.app = app
    
    def run(self):
        self.app.processEvents(0.0)
        reactor.callLater(0.02, self.run)


def install(app):
    """Connect a QApplication to the twisted mainloop.
    """
    qsupport = QTSupport(app)
    reactor.callLater(0.0, qsupport.run)

