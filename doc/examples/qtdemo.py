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

"""Qt demo.

Fetch a URL's contents.
"""

import sys, urlparse
from qt import *

from twisted.internet  import qternet, tcp
from twisted.protocols import http


class TwistzillaClient(http.HTTPClient):
    def __init__(self, edit, urls):
        self.urls  = urls
        self.edit  = edit

    def connectionMade(self):
        print 'Connected.'

        self.sendCommand('GET', self.urls[2])
        self.sendHeader('Host', '%s:%d' % (self.urls[0], self.urls[1]) )
        self.sendHeader('User-Agent', 'Twistzilla')
        self.endHeaders()

    def handleResponse(self, data):
        print 'Got response.'
        self.edit.setText(data)



class TwistzillaWindow(QMainWindow):
    def __init__(self, *args):
        QMainWindow.__init__(self, *args)

        self.setCaption("Twistzilla")

        vbox = QVBox(self)
        vbox.setMargin(2)
        vbox.setSpacing(3)

        hbox = QHBox(vbox)
        label = QLabel("Address: ", hbox)

        self.line  = QLineEdit("http://www.twistedmatrix.com/", hbox)
        self.connect(self.line, SIGNAL('returnPressed()'), self.fetchURL)

        self.edit = QMultiLineEdit(vbox)
        self.edit.setEdited(0)

        self.setCentralWidget(vbox)

    def fetchURL(self):
        u = urlparse.urlparse(str(self.line.text()))

        pos = u[1].find(':')

        if pos == -1:
            host, port = u[1], 80
        else:
            host, port = u[1][:pos], int(u[1][pos+1:])

        if u[2] == '':
            file = '/'
        else:
            file = u[2]

        print 'Connecting to.'
        client = TwistzillaClient(self.edit, (host, port, file))
        tcp.Client(host, port, client)
 
def main(args):
    reactor = qternet.install()
    app = reactor.qApp

    win = TwistzillaWindow()
    win.show()

    app.connect(app, SIGNAL("lastWindowClosed()"), app, SLOT("quit()"))
  
    reactor.run()

if __name__ == '__main__':
    main(sys.argv)
