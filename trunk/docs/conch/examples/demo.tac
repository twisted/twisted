# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

# You can run this .tac file directly with:
#    twistd -ny demo.tac

"""Nearly pointless demonstration of the manhole interactive interpreter.

This does about the same thing as demo_manhole, but uses the tap
module's makeService method instead.  The only interesting difference
is that in this version, the telnet server also requires
authentication.

Note, you will have to create a file named \"passwd\" and populate it
with credentials (in the format of passwd(5)) to use this demo.
"""

from twisted.application import service
application = service.Application("TAC Demo")

from twisted.conch import manhole_tap
manhole_tap.makeService({"telnetPort": "tcp:6023",
                         "sshPort": "tcp:6022",
                         "namespace": {"foo": "bar"},
                         "passwd": "passwd"}).setServiceParent(application)
