from twisted.web.google import checkGoogle
from twisted.python.util import println
from twisted.internet import reactor 
import sys

checkGoogle(sys.argv[1:]).addCallbacks(
 lambda l:(println(l),reactor.stop()),
 lambda e:(println('error:',e),reactor.stop()))
reactor.run()
