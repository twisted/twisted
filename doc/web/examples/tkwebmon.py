# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

#
from __future__ import nested_scopes

import Tkinter as Tk
from twisted.web import monitor
from twisted.python import usage
import time, urlparse

ACK, NOACK = range(2)

class ChangeNotified(monitor.BaseChangeNotified):

    def __init__(self, url, frame):
        self.button = Tk.Button(frame, text=url, command=self.ackChange,
                                background='red')
        self.button.pack(anchor=Tk.W)
        self.state = ACK

    def ackChange(self):
        if self.state == NOACK:
            self.state = ACK
            self.button.configure(background='green')

    def reportChange(self, old, new):
        self.state = ACK
        if new == None:
            self.button.configure(background='red')
        elif old == None:
            self.button.configure(background='green')
        else:
            self.state = NOACK
            self.button.configure(background='orange')


class AddChecker(Tk.Frame):

    def __init__(self, whereTo, makeChecker, *args, **kw):
        Tk.Frame.__init__(self, *args, **kw)
        self.whereTo = whereTo
        self.makeChecker = makeChecker
        self.entry = Tk.Entry(self)
        self.entry.pack(side=Tk.LEFT)
        button = Tk.Button(self, text="Add", command=self.addChecker)
        button.pack(side=Tk.RIGHT)

    def addChecker(self):
        url = self.entry.get()
        notified = ChangeNotified(url, self.whereTo)
        checker = self.makeChecker(url, notified)
        checker.start()
        self.entry.delete(0, Tk.END)

def webmonFrame(master, makeChecker, urls):            
    frame = Tk.Frame(master)
    buttons = Tk.Frame(frame)
    for url in urls:
        notified = ChangeNotified(url, buttons)
        checker = makeChecker(url, notified)
        checker.start()
    buttons.pack()
    add = AddChecker(buttons, makeChecker, frame)
    add.pack()
    return frame


class Options(usage.Options):

    urls = ()

    optParameters = [['delay', 'd', '30', 'delay between connection attempts'],
                    ['proxy', 'p', None, 'use given proxy']]

    def parseArgs(self, *args):
        self.urls = args

def run():
    import sys
    opt = Options()
    opt.parseOptions(sys.argv[1:])
    delay = int(opt['delay'])
    if opt['proxy']:
        host = urlparse.urlparse(opt['proxy'])[1]
        if ':' in host:
            host, port = host.split(':', 1)
            port = int(port)
        else:
            port = 80
        makeChecker = lambda url, notified: monitor.ProxyChangeChecker(
                       host, port, notified, url, delay)
    else:
        makeChecker = lambda url, notified: monitor.ChangeChecker(notified, url,
                                                                  delay)
    from twisted.internet import reactor, tksupport
    root = Tk.Tk()
    root.protocol("WM_DELETE_WINDOW", reactor.stop)
    root.title("Web Monitor")
    tksupport.install(root)
    frame = webmonFrame(root, makeChecker, opt.urls)
    frame.pack()
    reactor.run()


if __name__ == '__main__':
    run()
