
from twisted.python import log

class LogBook(object):
    """
    A gtk2 logging widget. Add my 'notebook' attribute to your widget
    tree after you instantiate me. Call my 'observe' method to add new
    log-viewing tabs.
    """
    def __init__(self):
        self.notebook = gtk.Notebook()
        self.tabs = {}
        log.addObserver(self._gotLog)

    def observe(self, name, thunk):
        """observe(name, thunk)

        Call this when you want to add a new log-viewing tab. 'name'
        is the name of the tab, and 'thunk' is a function that takes a
        logdict and returns a string to append to the text buffer.
        """
        if name in self.tabs:
            print ":-("
        buff = gtk.TextBuffer()
        view = gtk.TextView(buff)
        self.notebook.append_page(view, gtk.Label(name))
        self.tabs[name] = buff, thunk

    def _gotLog(self, logdict):
        for buff, thunk in self.tabs.values():
            val = thunk(logdict)
            if val:
                buff.insert(buff.get_end_iter(), val)

if __name__ == '__main__':
    from twisted.internet import gtk2reactor
    gtk2reactor.install()
    from twisted.internet import reactor
    import gtk
    
    w = gtk.Window()
    w.connect('destroy', gtk.main_quit)
    book = LogBook()
    thunk = lambda d: 'message' in d and str(d) + '\n'
    errthunk = lambda d: 'isError' in d and d['isError'] and str(d) + '\n'
    book.observe("MAIN", thunk)
    book.observe(":-(", errthunk)
    w.add(book.notebook)
    w.show_all()
    reactor.callLater(2, log.msg, 'HI BARNEY')
    reactor.callLater(2, log.err, 'HI BARNEY2')
    reactor.callLater(2, log.msg, 'HI BARNEY3')
    reactor.callLater(3, log.err, 'HI BARNEY4')
    reactor.callLater(3, log.msg, 'HI BARNEY5')
    reactor.callLater(3, log.err, 'HI BARNEY6')
    
    reactor.run()
