Web Services Tool

Web Services Tool queries XML-RPC enabled servers via the "standard"
introspection methods and displays a summary of the API.  It is
implemented in Python using the PyObjC module.

To use the application, simply provide the connection window with an URL
to the XML-RPC handler of a web server.  If the server at least
implements the listMethods() method, the app will display a list of
available methods.

See: http://pyobjc.sourceforge.net/

Source for both the pyobjc module and the Web Services Tool are
available via the pyobjc sourceforge CVS repository.

The source of this application demonstrates
- using Python's network libraries inside a Cocoa app
- how to use multi-threading
- how to create an NSToolbar
- how to use an NSTableView

b.bum
bbum@codefab.com

This application has been modified for Twisted.  It demonstrates:
- using Twisted in a Cocoa app with the cfreactor
- how to write responsive single-threaded network applications

To run the demo:
python buildapp.py build
open build/Web\ Services\ Tool.app

bob@redivi.com
