
from twisted.python import log

class LogBook(object):
    def __init__(self):
        self.notebook = gtk.Notebook()
        self.tabs = {}
        log.addObserver(self._gotLog)

    def observe(self, name, thunk):
        if name in self.tabs:
            print ":-("
        buff = gtk.TextBuffer()
        view = gtk.TextView(buff)
        self.notebook.append_page(view, gtk.Label(name))
        self.tabs[name] = buff, thunk

    def _gotLog(self, logdict):
        for name, (buff, thunk) in self.tabs.items():
            val = thunk(logdict)
            if val is not None:
                buff.insert(buff.get_end_iter(), val)

if __name__ == '__main__':
    from twisted.internet import gtk2reactor
    gtk2reactor.install()
    from twisted.internet import reactor
    import gtk
    
    w = gtk.Window()
    w.connect('destroy', gtk.main_quit)
    book = LogBook()
    thunk = lambda d: 'message' in d and ' '.join(d['message'])
    book.observe("MAIN", thunk)
    w.add(book.notebook)
    w.show_all()
    reactor.callLater(2, log.msg, 'HI BARNEY')
    reactor.run()
