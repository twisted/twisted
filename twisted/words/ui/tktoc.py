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

from Tkinter import Tk,mainloop
from twisted.spread.ui import tkutil
from twisted.internet import tkinternet
from twisted.words.ui import im2,tkim
from twisted.words.ui.gateways import toc 
from twisted.internet import tcp 

im2.Conversation=tkim.Conversation
im2.ContactList=tkim.ContactList
im2.GroupSession=tkim.GroupSession

def our_callback(values):
    global im
    print values
    user=values["username"]
    password=values["password"]
    server=values["server"]
    port=int(values["port"])
    c=toc.TOCGateway(im,user,password)
    tcp.Client(server,port,c)
    im.attachGateway(c)

def main():
    global im
    root=Tk()
    root.withdraw()
    tkinternet.install(root)
    im=im2.InstanceMessenger()
    im.logging=1
    tkutil.GenericLogin(our_callback,[["Username","my_screen_name"],
                                      ["Password","my_password",{"show":"*"}],
                                      ["Server","toc.oscar.aol.com"],
                                      ["Port","9898"]])
    mainloop()
    tkinternet.stop()

if __name__=="__main__":main()
