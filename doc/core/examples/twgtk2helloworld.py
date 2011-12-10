from twisted.internet import gtk2reactor
gtk2reactor.install()
#changes the type of reactor that is installed
#see http://twistedmatrix.com/documents/current/core/howto/choosing-reactor.html#auto11

import gtk
from twisted.internet import reactor

class HelloWorld:
	def hello(self, widge, data=None):
		print "Hello World"
	
	def destroy(self, widget, data=None):
		# stopping the reactor also stops the gtk.main() loop
		# by calling gtk.main_quit()
		reactor.stop()
	
	def delete_event(self, widget, event, data=None):
		print "delete event occurred"
		return False
	
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

if __name__ == "__main__":
	HelloWorld()
	# since we've installed the gtk2reactor
	# running our reactor will also start the gtk.main() loop
	reactor.run()