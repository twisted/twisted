
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

"""An integrated wxPython/twisted event loop.

Make a wxApp that inherits from wxinternet.twixApp, and then
call wxinternet.install with an instance of the class.
"""

# wxPython imports
from wxPython.wx import wxApp

# sibling imports
import main

# twisted import
from twisted.python import delay


class GuiDelayed:
    """Delayed that assures GUI events are handled."""

    __implements__ = delay.IDelayed
    
    def __init__(self, app):
        self.app = app
    
    def timeout(self):
        return 0.006 # will this use up too much CPU on slow machines?
    
    def runUntilCurrent(self):
        # run wx events
        while self.app.Pending():
            self.app.Dispatch()
        
        # run wx idle events
        self.app.ProcessIdle()

# get the run() function before it is redefined in install()
realRun = main.run

class twixApp(wxApp):
    """A wxApp with a custom twisted event loop.
    
    All twisted wxApp instances should inherit from this class, instead
    of using wxApp.
    """
    
    def MainLoop(self):
        """The combined wx and twisted event loop."""
        main.addDelayed(GuiDelayed(self))
        realRun()


def install(app):
    """Install the wxPython event loop, given a twixApp instance."""
    assert isinstance(app, twixApp)
    main.run = app.MainLoop


__all__ = ["install", "twixApp"]
