import socket, sys
sys.path.insert(0, '..')
import lettucewrap
socket.socket = lettucewrap.GreenSocket
from dumb import f

from twisted.internet import reactor
from twisted.python import log

log.startLogging(sys.stdout)

reactor.callLater(0, lettucewrap.wrapCall, f)
reactor.run()

