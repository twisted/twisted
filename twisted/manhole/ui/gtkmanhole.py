# -*- Python -*-
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


# TODO:
#  * send script
#  * replace method
#  * save readline history
#  * save-history-as-python
#  * save transcript
#  * identifier completion

import code, string, sys, traceback, types
import gtk

from twisted.python import rebuild, util
from twisted.spread.ui import gtkutil
from twisted.spread import pb
from twisted.manhole import explorer

True = gtk.TRUE
False = gtk.FALSE

try:
    import spelunk_gnome
except ImportError:
    _GNOME_POWER = False
else:
    _GNOME_POWER = True


## def findBeginningOfLineWithPoint(entry):
##     pos = entry.get_point()
##     while pos:
##         pos = pos - 1
##         c = entry.get_chars(pos, pos+1)
##         if c == '\n':
##             return pos+1
##     return 0

import pywidgets

class Interaction(pywidgets.Interaction, pb.Referenceable):
    loginWindow = None

    capabilities = {
        "Explorer": 'Set',
        }

    def __init__(self):
        pywidgets.Interaction.__init__(self)
        self.signal_connect('destroy', gtk.mainquit, None)

        if _GNOME_POWER:
            self.display = BrowserDisplay()
            dWindow = gtk.GtkWindow(title="Spelunking")
            dWindow.add(self.display)
            dWindow.show_all()
            self.display.makeDefaultCanvas()
        else:
            self.display = BrowserDisplay(self)

        # The referencable attached to the Perspective
        self.client = self

    def remote_console(self, message):
        self.output.console(message)

    def remote_receiveExplorer(self, xplorer):
        if _GNOME_POWER:
            self.display.receiveExplorer(xplorer)
        else:
            XXX # text display?

    def remote_listCapabilities(self):
        return self.capabilities

    def connected(self, perspective):
        self.loginWindow.hide()
        self.name = self.loginWindow.username.get_text()
        self.hostname = self.loginWindow.hostname.get_text()
        perspective.broker.notifyOnDisconnect(self.connectionLost)
        self.perspective = perspective
        self.show_all()
        self.set_title("Manhole: %s@%s" % (self.name, self.hostname))

    def connectionLost(self, reason=None):
        if not reason:
            reason = "Connection Lost"
        self.loginWindow.loginReport(reason)
        self.hide()
        self.loginWindow.show()

    def codeInput(self, text):
        methodName = 'do'
        if text[0] == '/':
            split = string.split(text[1:],' ',1)
            statement = split[0]
            if len(split) == 2:
                remainder = split[1]
            if statement in ('browse', 'explore'):
                methodName = 'explore'
                text = remainder
            elif statement == 'watch':
                methodName = 'watch'
                text = remainder
            elif statement == 'self_rebuild':
                rebuild.rebuild(explorer)
                if _GNOME_POWER:
                    rebuild.rebuild(spelunk_gnome)
                rebuild.rebuild(sys.modules[__name__])
                return
        try:
            self.perspective.callRemote(methodName, text)
        except pb.ProtocolError:
            # ASSUMPTION: pb.ProtocolError means we lost our connection.
            (eType, eVal, tb) = sys.exc_info()
            del tb
            s = string.join(traceback.format_exception_only(eType, eVal),
                            '')
            self.connectionLost(s)
        except:
            traceback.print_exc()
            gtk.mainquit()


class LineOrientedBrowserDisplay:
    def __init__(self, toplevel=None):
        if toplevel:
            self.toplevel = toplevel

    def receiveBrowserObject(self, obj):
        """Display a browser ObjectLink.
        """
        # This is a stop-gap implementation.  Ideally, everything
        # would be nicely formatted with pretty colours and you could
        # select referenced objects to browse them with
        # browse(selectedLink.identifier)

        if obj.type in map(explorer.typeString, [types.FunctionType,
                                                 types.MethodType]):
            arglist = []
            for arg in obj.value['signature']:
                if arg.has_key('default'):
                    a = "%s=%s" % (arg['name'], arg['default'])
                elif arg.has_key('list'):
                    a = "*%s" % (arg['name'],)
                elif arg.has_key('keywords'):
                    a = "**%s" % (arg['name'],)
                else:
                    a = arg['name']
                arglist.append(a)

            things = ''
            if obj.value.has_key('class'):
                things = "Class: %s\n" % (obj.value['class'],)
            if obj.value.has_key('self'):
                things = things + "Self: %s\n" % (obj.value['self'],)

            s = "%(name)s(%(arglist)s)\n%(things)s\n%(doc)s\n" % {
                'name': obj.value['name'],
                'doc': obj.value['doc'],
                'things': things,
                'arglist': string.join(arglist,", "),
                }
        else:
            s = str(obj) + '\n'

        self.toplevel.output.console([('stdout',s)])


if _GNOME_POWER:
    BrowserDisplay = spelunk_gnome.SpelunkDisplay
else:
    BrowserDisplay = LineOrientedBrowserDisplay

class Signature(pb.RemoteCopy, explorer.Signature):
    def __init__(self):
        pass

    __str__ = explorer.Signature.__str__

pb.setCopierForClass('twisted.manhole.explorer.Signature', Signature)
