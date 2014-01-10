#!/usr/bin/env python

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


"""
An example of using Twisted with Tkinter.
Displays a frame with buttons that responds to mouse clicks.

Run this example by typing in:
 python tkinterdemo.py
"""


from Tkinter import Tk, Frame, Button, LEFT
from twisted.internet import reactor, tksupport


class App(object):

    def onQuit(self):
        print "Quit!"
        reactor.stop()

    def onButton(self):
        print "Hello!"

    def __init__(self, master):
        frame = Frame(master)
        frame.pack()

        q = Button(frame, text="Quit!", command=self.onQuit)
        b = Button(frame, text="Hello!", command=self.onButton)

        q.pack(side=LEFT)
        b.pack(side=LEFT)


if __name__ == '__main__':
    root = Tk()
    tksupport.install(root)
    app = App(root)
    reactor.run()
