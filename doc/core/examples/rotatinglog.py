
# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
# 
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
# 
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

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
