#!/usr/bin/env python

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Displays a frame with two buttons and a background image, using pyui library.

Run this example by typing in:
  python pyuidemo.py

Select "Quit" button to exit demo.
"""
from __future__ import print_function

import pyui
from twisted.internet import reactor, pyuisupport

def onButton(self):
    print("got a button")

def onQuit(self):
    reactor.stop()

def main():
    pyuisupport.install(args=(640, 480), kw={'renderer': '2d'})

    w = pyui.widgets.Frame(50, 50, 400, 400, "clipme")
    b = pyui.widgets.Button("A button is here", onButton)
    q = pyui.widgets.Button("Quit!", onQuit)
    
    w.addChild(b)
    w.addChild(q)
    w.pack()

    w.setBackImage("pyui_bg.png")
    reactor.run()

if __name__ == '__main__':
    main()
