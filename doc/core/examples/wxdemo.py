# Copyright (c) 2001-2006 Twisted Matrix Laboratories.
# See LICENSE for details.

"""Demo of wxPython integration with Twisted."""

import sys

try:
    from wx import Frame as wxFrame, DefaultPosition as wxDefaultPosition, \
         Size as wxSize, Menu as wxMenu, MenuBar as wxMenuBar, \
         EVT_MENU, MessageDialog as wxMessageDialog, App as wxApp, \
         EVT_CLOSE
except ImportError, e:
    from wxPython.wx import *

from twisted.python import log
from twisted.internet import wxreactor
wxreactor.install()

# import t.i.reactor only after installing wxreactor:
from twisted.internet import reactor, defer


ID_EXIT  = 101

class MyFrame(wxFrame):
    def __init__(self, parent, ID, title):
        wxFrame.__init__(self, parent, ID, title, wxDefaultPosition, wxSize(300, 200))
        menu = wxMenu()
        menu.Append(ID_EXIT, "E&xit", "Terminate the program")
        menuBar = wxMenuBar()
        menuBar.Append(menu, "&File")
        self.SetMenuBar(menuBar)
        EVT_MENU(self, ID_EXIT,  self.DoExit)
        
        # make sure reactor.stop() is used to stop event loop:
        EVT_CLOSE(self, lambda evt: reactor.stop())

    def DoExit(self, event):
        reactor.stop()


class MyApp(wxApp):

    def twoSecondsPassed(self):
        print "two seconds passed"

    def OnInit(self):
        frame = MyFrame(None, -1, "Hello, world")
        frame.Show(True)
        self.SetTopWindow(frame)
        # look, we can use twisted calls!
        reactor.callLater(2, self.twoSecondsPassed)
        return True


def demo():
    log.startLogging(sys.stdout)

    # register the wxApp instance with Twisted:
    app = MyApp(0)
    reactor.registerWxApp(app)

    # start the event loop:
    reactor.run()


if __name__ == '__main__':
    demo()
