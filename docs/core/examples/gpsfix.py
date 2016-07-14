#!/usr/bin/env python

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
GPSTest is a simple example using the SerialPort transport and the NMEA 0183
and Rockwell Zodiac GPS protocols to display fix data as it is received from
the device.
"""
from __future__ import print_function

from twisted.python import log, usage
import sys

if sys.platform == 'win32':
    from twisted.internet import win32eventreactor
    win32eventreactor.install()


class GPSFixLogger:
    def handle_fix(self, *args):
      """
      handle_fix gets called whenever either rockwell.Zodiac or nmea.NMEAReceiver
      receives and decodes fix data.  Generally, GPS receivers will report a
      fix at 1Hz. Implementing only this method is sufficient for most purposes
      unless tracking of ground speed, course, utc date, or detailed satellite
      information is necessary.

      For example, plotting a map from MapQuest or a similar service only
      requires longitude and latitude.
      """
      log.msg('fix:\n' + 
      '\n'.join(map(lambda n: '  %s = %s' % tuple(n), zip(('utc', 'lon', 'lat', 'fix', 'sat', 'hdp', 'alt', 'geo', 'dgp'), map(repr, args)))))

class GPSOptions(usage.Options):
    optFlags = [
        ['zodiac', 'z', 'Use Rockwell Zodiac (DeLorme Earthmate) [default: NMEA 0183]'],
    ]
    optParameters = [
        ['outfile', 'o', None, 'Logfile [default: sys.stdout]'],
        ['baudrate', 'b', None, 'Serial baudrate [default: 4800 for NMEA, 9600 for Zodiac]'],
        ['port', 'p', '/dev/ttyS0', 'Serial Port device'],
    ]


if __name__ == '__main__':
    from twisted.internet import reactor
    from twisted.internet.serialport import SerialPort

    o = GPSOptions()
    try:
        o.parseOptions()
    except usage.UsageError as errortext:
        print('%s: %s' % (sys.argv[0], errortext))
        print('%s: Try --help for usage details.' % (sys.argv[0]))
        raise SystemExit(1)

    logFile = o.opts['outfile']
    if logFile is None:
        logFile = sys.stdout
    log.startLogging(logFile)

    if o.opts['zodiac']:
        from twisted.protocols.gps.rockwell import Zodiac as GPSProtocolBase
        baudrate = 9600
    else:
        from twisted.protocols.gps.nmea import NMEAReceiver as GPSProtocolBase
        baudrate = 4800
    class GPSTest(GPSProtocolBase, GPSFixLogger):
        pass
    
    if o.opts['baudrate']:
        baudrate = int(o.opts['baudrate'])


    port = o.opts['port']
    log.msg('Attempting to open %s at %dbps as a %s device' % (port, baudrate, GPSProtocolBase.__name__))
    s = SerialPort(GPSTest(), o.opts['port'], reactor, baudrate=baudrate)
    reactor.run()
