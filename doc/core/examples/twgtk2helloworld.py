# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

from twisted.internet import gtk2reactor
gtk2reactor.install()

import gtk
from twisted.internet import reactor

class HelloWorld(object):
    def __init__(self):
        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window.connect("delete_event", self.delete_event)
        self.window.connect("destroy", self.destroy)
        self.window.set_border_width(10)
        self.button = gtk.Button("Hello World")
        self.button.connect("clicked", self.hello, None)
        self.button.connect_object("clicked", gtk.Widget.destroy, self.window)
        self.window.add(self.button)
        self.button.show()
        self.window.show()
        self.counter = 10
        self.countdown()

    def hello(self, widget, data=None):
        print "Hello World"

    def countdown(self):
        if self.counter > 0:
            print "Countdown", self.counter
            self.counter -= 1
            reactor.callLater(.5, self.countdown)
        else:
            print "Boom!"
            self.window.destroy()

    def destroy(self, widget, data=None):
        # Stopping the reactor also stops the gtk.main() loop by calling
        # gtk.main_quit().
        reactor.stop()

    def delete_event(self, widget, event, data=None):
        print "delete event occurred"
        return False

if __name__ == "__main__":
    HelloWorld()
    # Since we've installed the gtk2reactor, running our reactor will also start
    # the gtk.main() loop.
    reactor.run()
