
# DEFERred EXecution EXamples

### make sure errors come out in order
import sys
from twisted.python import log
log.logerr = sys.stdout

# Create a pseudo "remote" object for executing this stuff
from twisted.spread.util import LocalAsRemote
class Adder(LocalAsRemote):
    def async_add(self, a, b):
        print 'adding', a, b
        return a + b
        
adder = Adder()
