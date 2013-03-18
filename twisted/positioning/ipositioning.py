# Copyright (c) 2009-2011 Twisted Matrix Laboratories.
# See LICENSE for details.
"""
Positioning interfaces.

@since: 11.1
"""
from zope.interface import Interface


class IPositioningReceiver(Interface):
    """
    An interface for positioning providers.
    """
    def positionReceived(latitude, longitude):
        """
        Method called when a position is received.

        @param latitude: The latitude of the received position.
        @type latitude: L{twisted.positioning.base.Coordinate}
        @param longitude: The longitude of the received position.
        @type longitude: L{twisted.positioning.base.Coordinate}
        """


    def positionErrorReceived(positionError):
        """
        Method called when position error is received.

        @param positioningError: The position error.
        @type positioningError: L{twisted.positioning.base.PositionError}
        """

    def timeReceived(time):
        """
        Method called when time and date information arrives.

        @param time: The date and time (expressed in UTC unless otherwise
            specified).
        @type time: L{datetime.datetime}
        """


    def headingReceived(heading):
        """
        Method called when a true heading is received.

        @param heading: The heading.
        @type heading: L{twisted.positioning.base.Heading}
        """


    def altitudeReceived(altitude):
        """
        Method called when an altitude is received.

        @param altitude: The altitude.
        @type altitude: L{twisted.positioning.base.Altitude}
        """


    def speedReceived(speed):
        """
        Method called when the speed is received.

        @param speed: The speed of a mobile object.
        @type speed: L{twisted.positioning.base.Speed}
        """


    def climbReceived(climb):
        """
        Method called when the climb is received.

        @param climb: The climb of the mobile object.
        @type climb: L{twisted.positioning.base.Climb}
        """

    def beaconInformationReceived(beaconInformation):
        """
        Method called when positioning beacon information is received.

        @param beaconInformation: The beacon information.
        @type beaconInformation: L{twisted.positioning.base.BeaconInformation}
        """



class INMEAReceiver(Interface):
    """
    An object that can receive NMEA data.
    """
    def sentenceReceived(sentence):
        """
        Method called when a sentence is received.

        @param sentence: The received NMEA sentence.
        @type L{twisted.positioning.nmea.NMEASentence}
        """



class IPositioningSentenceProducer(Interface):
    """
    A protocol that produces positioning sentences.

    Implementing this protocol allows sentence classes to be automagically
    generated for a particular protocol.
    """
    def getSentenceAttributes(self):
        """
        Returns a set of attributes that might be present in a sentence produced
        by this sentence producer.

        @return: A set of attributes that might be present in a given sentence.
        @rtype: C{set} of C{str}
        """
