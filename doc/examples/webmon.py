"""
Usage: webmon.py <url> [...]
Write to stdout when a URL becomes available/unavailable, or when the content
changes.
"""
from twisted.web import monitor
from twisted.internet import reactor
import sys

class ChangeChecker(monitor.ChangeChecker):

    def reportChange(self, old, new):
        if old is None:
            print self.url, "available"
        elif new is None:
            print self.url, "not available"
        else:
            print self.url, "changed"

for url in sys.argv[1:]:
    checker = ChangeChecker(url, 30)
    checker.start()
reactor.run()
