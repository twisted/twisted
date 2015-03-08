#!/usr/bin/env python

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Example using MouseMan protocol with the SerialPort transport.
"""

# TODO set tty modes, etc.
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

import sys
from twisted.python import usage, log
from twisted.protocols.mice import mouseman

if sys.platform == 'win32':
    # win32 serial does not work yet!
    raise NotImplementedError, "The SerialPort transport does not currently support Win32"
    from twisted.internet import win32eventreactor
    win32eventreactor.install()

class Options(usage.Options):
    optParameters = [
        ['port', 'p', '/dev/mouse', 'Device for serial mouse'],
        ['baudrate', 'b', '1200', 'Baudrate for serial mouse'],
        ['outfile', 'o', None, 'Logfile [default: sys.stdout]'],
    ]

class McFooMouse(mouseman.MouseMan):
    def down_left(self):
        log.msg("LEFT")

    def up_left(self):
        log.msg("left")

    def down_middle(self):
        log.msg("MIDDLE")

    def up_middle(self):
        log.msg("middle")

    def down_right(self):
        log.msg("RIGHT")

    def up_right(self):
        log.msg("right")

    def move(self, x, y):
        log.msg("(%d,%d)" % (x, y))

if __name__ == '__main__':
    from twisted.internet import reactor
    from twisted.internet.serialport import SerialPort
    o = Options()
    try:
        o.parseOptions()
    except usage.UsageError, errortext:
        print "%s: %s" % (sys.argv[0], errortext)
        print "%s: Try --help for usage details." % (sys.argv[0])
        raise SystemExit, 1

    logFile = sys.stdout
    if o.opts['outfile']:
        logFile = o.opts['outfile']
    log.startLogging(logFile)
    
    SerialPort(McFooMouse(), o.opts['port'], reactor, baudrate=int(o.opts['baudrate']))
    reactor.run()
