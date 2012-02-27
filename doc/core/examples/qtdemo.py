# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Qt demo.

Fetch a URL's contents and display it in a Webkit window.
"""


import sys, urlparse

from PySide import QtGui, QtCore
from PySide.QtWebKit import QWebView

from twisted.internet import protocol

app = QtGui.QApplication(sys.argv)
from twisted.internet import qtreactor
qtreactor.install()

# The reactor must be installed before this import
from twisted.web import http


class TwistzillaClient(http.HTTPClient):
    def __init__(self, web, urls):
        self.urls = urls
        self.web = web

    def connectionMade(self):
        self.sendCommand('GET', self.urls[2])
        self.sendHeader('Host', '%s:%d' % (self.urls[0], self.urls[1]))
        self.sendHeader('User-Agent', 'Twistzilla')
        self.endHeaders()

    def handleResponse(self, data):
        self.web.setHtml(data)


class TwistzillaWindow(QtGui.QMainWindow):
    """
    WebKit window that displays twistedmatrix.com.
    """
    def __init__(self, *args):
        QtGui.QMainWindow.__init__(self, *args)

        self.centralwidget = QtGui.QWidget(self)
        vbox = QtGui.QVBoxLayout(self.centralwidget)
        hbox = QtGui.QHBoxLayout()
        label = QtGui.QLabel("Address: ")

        self.line  = QtGui.QLineEdit("http://www.twistedmatrix.com/")
        self.connect(self.line, QtCore.SIGNAL('returnPressed()'), self.fetchURL)
        hbox.addWidget(label)
        hbox.addWidget(self.line)

        self.web = QWebView()

        vbox.addLayout(hbox)
        vbox.addWidget(self.web)
        vbox.setMargin(2)
        vbox.setSpacing(3)

        self.setCentralWidget(self.centralwidget)
        self.fetchURL()

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

        from twisted.internet import reactor
        protocol.ClientCreator(reactor, TwistzillaClient, self.web,
            (host, port, file)).connectTCP(host, port)

    def closeEvent(self, event=None):
        from twisted.internet import reactor
        reactor.stop()


def main():
    win = TwistzillaWindow()
    win.show()

    from twisted.internet import reactor
    sys.exit(reactor.run())

if __name__ == '__main__':
    main()
