#!/usr/bin/env python

import os, os.path, types

from twisted.python import components
import zope.interface as zi


class IPlug(components.Interface):
    def power(volts):
        """a socket supplies me with volts of electricity which i feed to my device"""


class ElectricDevice(object):
    expectedVolts = 0
    name = "Generic Device"

    def feedPower(self, volts):
        if volts == self.expectedVolts:
            print "I am a %s. I was plugged in properly and am now operating." % self.name
        else:
            print "\nBANG! ZAP! *=> SPARKS FLY EVERYWHERE <=*"
            print "I was plugged in improperly and "
            print "now you have no %s any more." % self.name


class HairDryer(ElectricDevice):
    zi.implements(IPlug)

    expectedVolts = 110
    name = "Hair Dryer"

    def power(self, volts):
        print "I, the %s, am feeding myself power" % self.name
        self.feedPower(volts)


class ButterKnife(object):
    name = "Butter Knife"
    def power(self, volts):
        print "ZZZZZZAP! YOU PLUGGED IN THE BUTTER KNIFE! YOU'RE DEAD!!!!\n"



class ISocket(components.Interface):
    voltage = zi.Attribute("the level of voltage to supply to things plugged into me")
    def plugIn(obj):
        """the action of plugging in an object obj"""


class RegularSocket(object):
    """A regular ol' socket that just powers whatever is plugged into it"""
    zi.implements(ISocket)
    voltage = 110

    def plugIn(self, obj):
        obj.power(self.voltage)


class GFCISocket(object):
    """A special Ground Fault Circuit Interrupt socket that makes sure
    you don't get electrocuted"""

    zi.implements(ISocket)
    voltage = 110
    tripped = False

    def plugIn(self, obj):
        if self.tripped:
            print "Sorry, my circuit breaker tripped, cannot supply power."
            return

        if IPlug.providedBy(obj):
            obj.power(self.voltage)
        else:
            print "Warning! You didn't plugIn a valid IPlug object! Shutting off power!"
            self.tripped = True


def main():
    socket = RegularSocket()
    gfci = GFCISocket()
    hairDryer = HairDryer()
    butterKnife = ButterKnife()
    
    print "\n\nwith a regular socket\n"
    socket.plugIn(hairDryer)
    socket.plugIn(butterKnife)

    print "\n\nwith a GFCI socket\n"

    gfci.plugIn(hairDryer)
    gfci.plugIn(butterKnife)
    
    print "\n\n"

if __name__ == '__main__':
    main()
