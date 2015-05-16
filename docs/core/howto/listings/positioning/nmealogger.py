#!/usr/bin/env python
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.
"""
Connects to an NMEA device, logs beacon information and position.
"""
import sys
from twisted.internet import reactor, serialport
from twisted.positioning import base, nmea
from twisted.python import log, usage


class PositioningReceiver(base.BasePositioningReceiver):
    def positionReceived(self, latitude, longitude):
        log.msg("I'm at {} lat, {} lon".format(latitude, longitude))


    def beaconInformationReceived(self, beaconInformation):
        template = "{0.seen} beacons seen, {0.used} beacons used"
        log.msg(template.format(beaconInformation))



class Options(usage.Options):
    optParameters = [
        ['baud-rate', 'b', 4800, "Baud rate (default: 4800)"],
        ['serial-port', 'p', '/dev/ttyS0', 'Serial Port device'],
    ]



def run():
    log.startLogging(sys.stdout)

    opts = Options()
    try:
        opts.parseOptions()
    except usage.UsageError, message:
        print "{}: {}".format(sys.argv[0], message)
        return

    positioningReceiver = PositioningReceiver()
    nmeaReceiver = nmea.NMEAAdapter(positioningReceiver)
    proto = nmea.NMEAProtocol(nmeaReceiver)

    port, baudrate = opts["serial-port"], opts["baud-rate"]
    serialport.SerialPort(proto, port, reactor, baudrate=baudrate)

    reactor.run()



if __name__ == "__main__":
    run()
