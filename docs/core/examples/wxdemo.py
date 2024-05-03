# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""Demo of wxPython integration with Twisted."""


import sys

from wx import EVT_CLOSE, EVT_MENU, App, DefaultPosition, Frame, Menu, MenuBar, Size

from twisted.internet import wxreactor
from twisted.python import log

wxreactor.install()

# import t.i.reactor only after installing wxreactor:
from twisted.internet import reactor

ID_EXIT = 101


class MyFrame(Frame):
    def __init__(self, parent, ID, title):
        Frame.__init__(self, parent, ID, title, DefaultPosition, Size(300, 200))
        menu = Menu()
        menu.Append(ID_EXIT, "E&xit", "Terminate the program")
        menuBar = MenuBar()
        menuBar.Append(menu, "&File")
        self.SetMenuBar(menuBar)
        EVT_MENU(self, ID_EXIT, self.DoExit)

        # make sure reactor.stop() is used to stop event loop:
        EVT_CLOSE(self, lambda evt: reactor.stop())

    def DoExit(self, event):
        reactor.stop()


class MyApp(App):
    def twoSecondsPassed(self):
        print("two seconds passed")

    def OnInit(self):
        frame = MyFrame(None, -1, "Hello, world")
        frame.Show(True)
        self.SetTopWindow(frame)
        # look, we can use twisted calls!
        reactor.callLater(2, self.twoSecondsPassed)
        return True


def demo():
    log.startLogging(sys.stdout)

    # register the App instance with Twisted:
    app = MyApp(0)
    reactor.registerWxApp(app)

    # start the event loop:
    reactor.run()


if __name__ == "__main__":
    demo()
