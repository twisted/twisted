
# System Imports
import code, string, sys, traceback
import gtk
True = 1
False = 0

# Twisted Imports
from twisted.spread.ui import gtkutil
from twisted.python import util
rcfile = util.sibpath(__file__, 'gtkrc')
gtk.rc_parse(rcfile)


def isCursorOnFirstLine(entry):
    firstnewline = string.find(entry.get_chars(0,-1), '\n')
    if entry.get_point() <= firstnewline or firstnewline == -1:
        return 1

def isCursorOnLastLine(entry):
    if entry.get_point() >= string.rfind(string.rstrip(entry.get_chars(0,-1)), '\n'):
        return 1


class InputText(gtk.GtkText):
    linemode = 0
    blockcount = 0

    def __init__(self, toplevel=None):
        gtk.GtkText.__init__(self)
        self['name'] = 'Input'
        self.set_editable(gtk.TRUE)
        self.connect("key_press_event", self.processKey)
        #self.set_word_wrap(gtk.TRUE)

        self.history = []
        self.histpos = 0

        if toplevel:
            self.toplevel = toplevel

    def historyUp(self):
        if self.histpos > 0:
            self.histpos = self.histpos - 1
            self.delete_text(0, -1)
            self.insert_defaults(self.history[self.histpos])
            self.set_position(0)

    def historyDown(self):
        if self.histpos < len(self.history) - 1:
            self.histpos = self.histpos + 1
            self.delete_text(0, -1)
            self.insert_defaults(self.history[self.histpos])
        elif self.histpos == len(self.history) - 1:
            self.histpos = self.histpos + 1
            self.delete_text(0, -1)

    def processKey(self, entry, event):
        # TODO: make key bindings easier to customize.

        stopSignal = False
        # ASSUMPTION: Assume Meta == mod4
        isMeta = event.state & gtk.GDK.MOD4_MASK
        if event.keyval == gtk.GDK.Return:
            isShift = event.state & gtk.GDK.SHIFT_MASK
            if isShift:
                self.linemode = True
                self.insert_defaults('\n')
            else:
                stopSignal = True
                text = self.get_chars(0,-1)
                if not text: return
                try:
                    if text[0] == '/':
                        # It's a local-command, don't evaluate it as
                        # Python.
                        c = True
                    else:
                        # This will tell us it's a complete expression.
                        c = code.compile_command(text)
                except SyntaxError, e:
                    # Ding!
                    self.set_positionLineOffset(e.lineno, e.offset)
                    print "offset", e.offset
                    errmsg = {'traceback': [],
                              'exception': [str(e) + '\n']}
                    self.toplevel.output.console([('exception', errmsg)])
                except OverflowError, e:
                    e = traceback.format_exception_only(OverflowError, e)
                    errmsg = {'traceback': [],
                              'exception': e}
                    self.toplevel.output.console([('exception', errmsg)])
                else:
                    if c is None:
                        self.linemode = True
                        stopSignal = False
                    else:
                        self.sendMessage(entry)
                        self.clear()

        elif ((event.keyval == gtk.GDK.Up and isCursorOnFirstLine(self))
              or (isMeta and event.string == 'p')):
            self.historyUp()
            stopSignal = True
        elif ((event.keyval == gtk.GDK.Down and isCursorOnLastLine(self))
              or (isMeta and event.string == 'n')):
            self.historyDown()
            stopSignal = True

        if stopSignal:
            self.emit_stop_by_name("key_press_event")
            return True

    def clear(self):
        self.delete_text(0, -1)
        self.linemode = False

    def set_positionLineOffset(self, line, offset):
        text = self.get_chars(0, -1)
        pos = 0
        for l in xrange(line - 1):
            pos = string.index(text, '\n', pos) + 1
        pos = pos + offset - 1
        self.set_position(pos)

    def sendMessage(self, unused_data=None):
        text = self.get_chars(0,-1)
        if self.linemode:
            self.blockcount = self.blockcount + 1
            fmt = ">>> # begin %s\n%%s\n#end %s\n" % (
                self.blockcount, self.blockcount)
        else:
            fmt = ">>> %s\n"
        self.history.append(text)
        self.histpos = len(self.history)
        self.toplevel.output.console([['command',fmt % text]])
        self.toplevel.codeInput(text)


    def readHistoryFile(self, filename=None):
        if filename is None:
            filename = self.historyfile

        f = open(filename, 'r', 1)
        self.history.extend(f.readlines())
        f.close()
        self.histpos = len(self.history)

    def writeHistoryFile(self, filename=None):
        if filename is None:
            filename = self.historyfile

        f = open(filename, 'a', 1)
        f.writelines(self.history)
        f.close()


class Interaction(gtk.GtkWindow):
    titleText = "Abstract Python Console"

    def __init__(self):
        gtk.GtkWindow.__init__(self, gtk.WINDOW_TOPLEVEL)
        self.set_title(self.titleText)
        self.set_default_size(300, 300)
        self.set_name("Manhole")

        vbox = gtk.GtkVBox()
        pane = gtk.GtkVPaned()

        self.output = OutputConsole(toplevel=self)
        pane.pack1(gtkutil.scrollify(self.output), gtk.TRUE, gtk.FALSE)

        self.input = InputText(toplevel=self)
        pane.pack2(gtkutil.scrollify(self.input), gtk.FALSE, gtk.TRUE)
        vbox.pack_start(pane, 1,1,0)

        self.add(vbox)
        self.input.grab_focus()

    def codeInput(self, text):
        raise NotImplementedError("Bleh.")


class LocalInteraction(Interaction):
    titleText = "Local Python Console"
    def __init__(self):
        Interaction.__init__(self)
        self.globalNS = {}
        self.localNS = {}
        self.filename = "<gtk console>"

    def codeInput(self, text):
        from twisted.manhole.service import runInConsole
        val = runInConsole(text, self.output.console,
                           self.globalNS, self.localNS, self.filename)
        if val is not None:
            self.localNS["_"] = val
            self.output.console([("result", repr(val) + "\n")])

class OutputConsole(gtk.GtkText):
    maxBufSz = 10000

    def __init__(self, toplevel=None):
        gtk.GtkText.__init__(self)
        self['name'] = "Console"
        gtkutil.defocusify(self)
        #self.set_word_wrap(gtk.TRUE)

        if toplevel:
            self.toplevel = toplevel

    def console(self, message):
        self.set_point(self.get_length())
        self.freeze()
        previous_kind = None
        style = self.get_style()
        style_cache = {}
        try:
            for element in message:
                if element[0] == 'exception':
                    s = traceback.format_list(element[1]['traceback'])
                    s.extend(element[1]['exception'])
                    s = string.join(s, '')
                else:
                    s = element[1]

                if element[0] != previous_kind:
                    style = style_cache.get(element[0], None)
                    if style is None:
                        gtk.rc_parse_string(
                            'widget \"Manhole.*.Console\" '
                            'style \"Console_%s\"\n'
                            % (element[0]))
                        self.set_rc_style()
                        style_cache[element[0]] = style = self.get_style()
                # XXX: You'd think we'd use style.bg instead of 'None'
                # here, but that doesn't seem to match the color of
                # the backdrop.
                self.insert(style.font, style.fg[gtk.STATE_NORMAL],
                            None, s)
                previous_kind = element[0]
            l = self.get_length()
            diff = self.maxBufSz - l
            if diff < 0:
                diff = - diff
                self.delete_text(0,diff)
        finally:
            self.thaw()
        a = self.get_vadjustment()
        a.set_value(a.upper - a.page_size)
