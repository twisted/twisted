from twisted.internet import reactor
from twisted.web.client import downloadPage
from twisted.python.util import println
import sys

downloadPage(sys.argv[1], "foo").addCallbacks(
   lambda value:reactor.stop(),
   lambda error:(println("an error occurred",error),reactor.stop()))
reactor.run()
