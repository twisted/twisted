
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

from twisted.internet import ingtkernet
from twisted.spread.ui import gtkutil
import gtk
ingtkernet.install()
class EchoClient:
    def __init__(self, echoer):
        l.hide()
        self.echoer = echoer
        w = gtk.GtkWindow(gtk.WINDOW_TOPLEVEL)
        vb = gtk.GtkVBox(); b = gtk.GtkButton("Echo:")
        self.entry = gtk.GtkEntry(); self.outry = gtk.GtkEntry()
        w.add(vb)
        map(vb.add, [b, self.entry, self.outry])
        b.connect('clicked', self.clicked)
        w.connect('destroy', gtk.mainquit)
        w.show_all()
    def clicked(self, b):
        txt = self.entry.get_text()
        self.entry.set_text("")
        self.echoer.echo(txt, pbcallback=self.outry.set_text)
l = gtkutil.Login(EchoClient, None, initialService="pbecho")
l.show_all()
gtk.mainloop()
