#!/usr/bin/env python

import os, os.path, types

from twisted.python import components
import zope.interface as zi

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
    


class IPlug(components.Interface):
    def power(volts):
        """a socket supplies me with volts of electricity which i feed to my device"""
       

class Plug(components.Adapter):
    zi.interfaces(IPlug)
    name = "Plug"
    def power(self, volts):
        self.original.feedPower(volts)


class Socket(object):
    voltage = 110
    def plugIn(self, obj):
        """I supply a device with power through an IPlug interface"""
        obj.power(self.voltage)
            

if __name__ == '__main__':
    main()
