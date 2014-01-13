
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


"""
An example of using the rotating log.
"""

from twisted.python import log
from twisted.python import logfile

# rotate every 100 bytes
f = logfile.LogFile("test.log", "/tmp", rotateLength=100)

# setup logging to use our new logfile
log.startLogging(f)

# print a few message
for i in range(10):
    log.msg("this is a test of the logfile: %s" % i)

# rotate the logfile manually
f.rotate()

log.msg("goodbye")
