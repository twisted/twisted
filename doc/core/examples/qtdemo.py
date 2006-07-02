# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""Qt demo.

Fetch a URL's contents.
"""

import sys, urlparse
from qt import *

from twisted.internet import qtreactor, protocol
app = QApplication([])
qtreactor.install(app)

from twisted.web import http


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
        from twisted.internet import reactor
        protocol.ClientCreator(reactor, TwistzillaClient, self.edit, (host, port, file)).connectTCP(host, port)


def main():
    """Run application."""
    # hook up Qt application to Twisted
    from twisted.internet import reactor
    
    win = TwistzillaWindow()
    win.show()

    # make sure stopping twisted event also shuts down QT
    reactor.addSystemEventTrigger('after', 'shutdown', app.quit )

    # shutdown twisted when window is closed
    app.connect(app, SIGNAL("lastWindowClosed()"), reactor.stop)

    reactor.run()


if __name__ == '__main__':
    main()
