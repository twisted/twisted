#!/usr/bin/env python

import os, os.path, types

from twisted.python import components
import zope.interface as zi


### our devices of varying nationality

class ElectricDevice:
    expectedVolts = 0
    name = "Generic Device"

    def power(self, volts):
        if volts == self.expectedVolts:
            print "I am a %s. I was plugged in properly and am now operating." % self.name
        else:
            print "\nBANG! ZAP! *=> SPARKS FLY EVERYWHERE <=*"
            print "I was plugged in improperly and "
            print "now you have no %s any more." % self.name

class USHairDryer(ElectricDevice):
    expectedVolts = 110
    name = "US Hair Dryer"

class UKStereo(ElectricDevice):
    expectedVolts = 220
    name = "UK Stereo"



### our sockets provide different levels of voltage

class Socket(object):
    """i power devices
    @cvar voltage: the voltage I supply to a device plugged into me
    """
    voltage = 0
    
    def plugIn(self, device):
        """device is the device to plug into me"""
        device.power(self.voltage)

class USSocket(Socket):
    voltage = 110

class UKSocket(Socket):
    voltage = 220



### our power converters that allows us to plug things in places they were not
### not designed to be plugged into


class IVoltageConverter(components.Interface):
    def power(volts):
        """I convert volts to the proper level to use with a certain device"""


class USDevice(components.Adapter):
    zi.implements(IVoltageConverter)

    def power(self, volts):
        self.original.power(volts + 110)


class UKDevice(components.Adapter):
    zi.implements(IVoltageConverter)

    def power(self, volts):
        self.original.power(volts - 110)



### now to register our adapters

components.registerAdapter(UKDevice, USHairDryer, IVoltageConverter)
components.registerAdapter(USDevice, UKStereo, IVoltageConverter)



def main():
    usHairDryer = USHairDryer()
    ukStereo = UKStereo()

    usSocket = USSocket()
    ukSocket = UKSocket()

    print "\n\nfirst we try a few combinations of plugging devices into sockets\n\n" 
    usSocket.plugIn(usHairDryer)
    ukSocket.plugIn(ukStereo)

    ukSocket.plugIn(usHairDryer)
    usSocket.plugIn(ukStereo)
    

    print "\n\nNow, we make use of our IVoltageConverter gizmo and try again\n\n"
    ukSocket.plugIn(IVoltageConverter(usHairDryer))
    usSocket.plugIn(IVoltageConverter(ukStereo))


if __name__ == '__main__':
    main()
