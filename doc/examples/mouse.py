#!/usr/bin/python

# TODO set line speed, tty modes, etc.
# This works for me:

# speed 1200 baud; rows 0; columns 0; line = 0;
# intr = ^C; quit = ^\; erase = ^?; kill = ^U; eof = ^D;
# eol = <undef>; eol2 = <undef>; start = ^Q; stop = ^S; susp = ^Z;
# rprnt = ^R; werase = ^W; lnext = ^V; flush = ^O; min = 1; time = 0;
# -parenb -parodd cs7 hupcl -cstopb cread clocal -crtscts ignbrk
# -brkint ignpar -parmrk -inpck -istrip -inlcr -igncr -icrnl -ixon
# -ixoff -iuclc -ixany -imaxbel -opost -olcuc -ocrnl -onlcr -onocr
# -onlret -ofill -ofdel nl0 cr0 tab0 bs0 vt0 ff0 -isig -icanon -iexten
# -echo -echoe -echok -echonl -noflsh -xcase -tostop -echoprt -echoctl
# -echoke

import sys, os, os.path
from twisted.internet import reactor
from twisted.python import usage
from twisted.protocols.mice import mouseman
from twisted.internet import protocol, abstract, fdesc

class SerialPort(abstract.FileDescriptor):
    def __init__(self, filename):
        self.fd = os.open(filename, os.O_RDONLY)

    def fileno(self):
        return self.fd

    def doRead(self):
        return fdesc.readFromFD(self.fileno(), self.protocol.dataReceived)

class Options(usage.Options):
    synopsis = "Usage: %s [--file=FILE]" % os.path.basename(sys.argv[0])
    optParameters = [['file', 'f', '/dev/tts/0']]

class McFooMouse(mouseman.MouseMan):
    def down_left(self):
        print "LEFT"
    def up_left(self):
        print "left"

    def down_middle(self):
        print "MIDDLE"
    def up_middle(self):
        print "middle"

    def down_right(self):
        print "RIGHT"
    def up_right(self):
        print "right"

    def move(self, x, y):
        print "(%d,%d)" % (x, y)

o = Options()
transport = SerialPort(o.opts['file'])
transport.protocol = McFooMouse()
reactor.addReader(transport)
reactor.run()
