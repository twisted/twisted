#!/usr/bin/python
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

import pyui
from twisted.internet import reactor, pyuisupport

def onButton(self):
    print "got a button"

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
