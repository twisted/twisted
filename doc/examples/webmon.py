"""
Usage: webmon.py <url> [...]
Write to stdout when a URL becomes available/unavailable, or when the content
changes.
"""
from twisted.web import monitor
from twisted.internet import reactor
import sys, time

class ChangeNotified(monitor.BaseChangeNotified):

    def __init__(self, url):
        self.url = url

    def reportChange(self, old, new):
        print time.ctime(),
        if old is None:
            print self.url, "available"
        elif new is None:
            print self.url, "not available"
        else:
            print self.url, "changed"

for url in sys.argv[1:]:
    notified = ChangeNotified(url)
    checker = monitor.ChangeChecker(notified, url, 30)
    checker.start()
reactor.run()
