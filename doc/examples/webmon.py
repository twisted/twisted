"""
Usage: webmon.py <url>
Write to stdout when URL becomes available/unavailable, or when the content
changes. Write a "." every five seconds, when the status of the URL stays the
same.
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

    def reportNoChange(self):
        sys.stdout.write(".")
        sys.stdout.flush()

checker = ChangeChecker(sys.argv[1], 5)
reactor.run()
