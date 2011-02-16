# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Acceptance tests for wxreactor.

Please test on Linux, Win32 and OS X:
1. Startup event is called at startup.
2. Scheduled event is called after 2 seconds.
3. Shutdown takes 3 seconds, both when quiting from menu and when closing
   window (e.g. Alt-F4 in metacity). This tests reactor.stop() and
   wxApp.ExitEventLoop().
4. 'hello, world' continues to be printed even when modal dialog is open
   (use dialog menu item), when menus are held down, when window is being
   dragged.
"""

import sys, time

try:
    from wx import Frame as wxFrame, DefaultPosition as wxDefaultPosition, \
         Size as wxSize, Menu as wxMenu, MenuBar as wxMenuBar, \
         EVT_MENU, MessageDialog as wxMessageDialog, App as wxApp
except ImportError, e:
    from wxPython.wx import *

from twisted.python import log
from twisted.internet import wxreactor
wxreactor.install()
from twisted.internet import reactor, defer


# set up so that "hello, world" is printed continously
dc = None
def helloWorld():
    global dc
    print "hello, world", time.time()
    dc = reactor.callLater(0.1, helloWorld)
dc = reactor.callLater(0.1, helloWorld)

def twoSecondsPassed():
    print "two seconds passed"

def printer(s):
    print s

def shutdown():
    print "shutting down in 3 seconds"
    if dc.active():
        dc.cancel()
    reactor.callLater(1, printer, "2...")
    reactor.callLater(2, printer, "1...")
    reactor.callLater(3, printer, "0...")
    d = defer.Deferred()
    reactor.callLater(3, d.callback, 1)
    return d

def startup():
    print "Start up event!"

reactor.callLater(2, twoSecondsPassed)
reactor.addSystemEventTrigger("after", "startup", startup)
reactor.addSystemEventTrigger("before", "shutdown", shutdown)


ID_EXIT  = 101
ID_DIALOG = 102

class MyFrame(wxFrame):
    def __init__(self, parent, ID, title):
        wxFrame.__init__(self, parent, ID, title, wxDefaultPosition, wxSize(300, 200))
        menu = wxMenu()
        menu.Append(ID_DIALOG, "D&ialog", "Show dialog")
        menu.Append(ID_EXIT, "E&xit", "Terminate the program")
        menuBar = wxMenuBar()
        menuBar.Append(menu, "&File")
        self.SetMenuBar(menuBar)
        EVT_MENU(self, ID_EXIT,  self.DoExit)
        EVT_MENU(self, ID_DIALOG,  self.DoDialog)
        # you really ought to do this instead of reactor.stop() in
        # DoExit, but for the sake of testing we'll let closing the
        # window shutdown wx without reactor.stop(), to make sure that
        # still does the right thing.
        #EVT_CLOSE(self, lambda evt: reactor.stop())

    def DoDialog(self, event):
        dl = wxMessageDialog(self, "Check terminal to see if messages are still being "
                             "printed by Twisted.")
        dl.ShowModal()
        dl.Destroy()

    def DoExit(self, event):
        reactor.stop()


class MyApp(wxApp):

    def OnInit(self):
        frame = MyFrame(None, -1, "Hello, world")
        frame.Show(True)
        self.SetTopWindow(frame)
        return True


def demo():
    log.startLogging(sys.stdout)
    app = MyApp(0)
    reactor.registerWxApp(app)
    reactor.run()


if __name__ == '__main__':
    demo()
