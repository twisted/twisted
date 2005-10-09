# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

import sys
from wxPython.wx import *

from twisted.python import log
from twisted.internet import wxreactor
wxreactor.install()
from twisted.internet import reactor, defer


# set up so that "hello, world" is printed once a second
dc = None
def helloWorld():
    global dc
    print "hello, world"
    dc = reactor.callLater(0.1, helloWorld)
dc = reactor.callLater(0.1, helloWorld)

def twoSecondsPassed():
    print "two seconds passed"

def printer(s):
    print s

def shutdown():
    print "shutting down in 0.3 seconds"
    if dc.active():
        dc.cancel()
    reactor.callLater(0.1, printer, "2...")
    reactor.callLater(0.2, printer, "1...")
    reactor.callLater(0.3, printer, "0...")
    d = defer.Deferred()
    reactor.callLater(0.3, d.callback, 1)
    return d

reactor.callLater(2, twoSecondsPassed)
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
        frame = MyFrame(NULL, -1, "Hello, world")
        frame.Show(true)
        self.SetTopWindow(frame)
        return true


def demo():
    log.startLogging(sys.stdout)
    app = MyApp(0)
    reactor.registerWxApp(app)
    reactor.run()


if __name__ == '__main__':
    demo()
