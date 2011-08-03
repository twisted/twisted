# Copyright (c) 2009-2011 Twisted Matrix Laboratories.
# See LICENSE for details.
"""
Test cases for positioning primitives.
"""
from twisted.trial.unittest import TestCase
from twisted.positioning import base
from twisted.positioning.base import LATITUDE, LONGITUDE
from twisted.positioning.base import NORTH, EAST, SOUTH, WEST


class AngleTests(TestCase):
    """
    Tests for the L{twisted.positioning.base.Angle} class.
    """
    def test_empty(self):
        """
        Tests the repr of an empty angle.
        """
        a = base.Angle()
        self.assertEquals("<Angle of unknown type (unknown value)>", repr(a))


    def test_variation(self):
        """
        Tests the repr of an empty variation.
        """
        a = base.Angle(angleType=base.VARIATION)
        self.assertEquals("<Variation (unknown value)>", repr(a))


    def test_unknownType(self):
        """
        Tests the repr of an unknown angle of a 1 decimal degree value.
        """
        a = base.Angle(1.0)
        self.assertEquals("<Angle of unknown type (1.0 degrees)>", repr(a))



class HeadingTests(TestCase):
    """
    Tests for the L{twisted.positioning.base.Heading} class.
    """
    def test_simple(self):
        """
        Tests some of the basic features of a very simple heading.
        """
        h = base.Heading(1.)
        self.assertEquals(h.inDecimalDegrees, 1.)
        self.assertEquals(h.variation, None)
        self.assertEquals(h.correctedHeading, None)
        self.assertEquals(float(h), 1.)


    def test_headingWithoutVariationRepr(self):
        """
        Tests the repr of a heading without a variation.
        """
        h = base.Heading(1.)
        self.assertEquals(repr(h), "<Heading (1.0 degrees, unknown variation)>")


    def test_headingWithVariationRepr(self):
        """
        Tests the repr of a heading with a variation.
        """
        angle, variation = 1.0, -10.0
        h = base.Heading.fromFloats(angle, variationValue=variation)

        variationRepr = '<Variation (%s degrees)>' % (variation,)
        expectedRepr = '<Heading (%s degrees, %s)>' % (angle, variationRepr)
        self.assertEquals(repr(h), expectedRepr)


    def test_equality(self):
        """
        Tests if equal headings compare equal.
        """
        self.assertEquals(base.Heading(1.), base.Heading(1.))


    def test_inequality(self):
        """
        Tests if unequal headings compare unequal.
        """
        self.assertNotEquals(base.Heading(1.), base.Heading(2.))


    def test_edgeCases(self):
        """
        Tests that the two edge cases of a heading value of zero and a heading
        value of zero with a variation of C{180.0} don't fail.
        """
        base.Heading(0)
        base.Heading(0, 180)


    def _badValueTest(self, **kw):
        """
        Helper function for verifying that bad values raise C{ValueError}.

        Passes C{**kw} to L{base.Heading.fromFloats}, and checks if that raises.
        """
        self.assertRaises(ValueError, base.Heading.fromFloats, **kw)


    def test_badAngleValueEdgeCase(self):
        """
        Tests that a heading with value C{360.0} fails.
        """
        self._badValueTest(angleValue=360.0)


    def test_badVariationEdgeCase(self):
        """
        Tests that a variation of C{-180.0} fails.
        """
        self._badValueTest(variationValue=-180.0)


    def test_negativeHeading(self):
        """
        Tests that negative heading values cause C{ValueError}.
        """
        self._badValueTest(angleValue=-10.0)


    def test_headingTooLarge(self):
        """
        Tests that an angle value larger than C{360.0} raises C{ValueError}.
        """
        self._badValueTest(angleValue=370.0)


    def test_variationTooNegative(self):
        """
        Tests that variation values less than C{-180.0} fail.
        """
        self._badValueTest(variationValue=-190.0)


    def test_variationTooPositive(self):
        """
        Tests that variation values greater than C{-180.0} fail.
        """
        self._badValueTest(variationValue=190.0)


    def test_correctedHeading(self):
        """
        Simple test for a corrected heading.
        """
        h = base.Heading.fromFloats(1., variationValue=-10.)
        self.assertEquals(h.correctedHeading, base.Angle(11., base.HEADING))


    def test_correctedHeadingOverflow(self):
        """
        Tests that a corrected heading that comes out above 360 degrees is
        correctly handled.
        """
        h = base.Heading.fromFloats(359., variationValue=-2.)
        self.assertEquals(h.correctedHeading, base.Angle(1., base.HEADING))


    def test_correctedHeadingOverflowEdgeCase(self):
        """
        Tests that a corrected heading that comes out to exactly 360 degrees
        is correctly handled.
        """
        h = base.Heading.fromFloats(359., variationValue=-1.)
        self.assertEquals(h.correctedHeading, base.Angle(0., base.HEADING))


    def test_correctedHeadingUnderflow(self):
        """
        Tests that a corrected heading that comes out under 0 degrees is
        correctly handled.
        """
        h = base.Heading.fromFloats(1., variationValue=2.)
        self.assertEquals(h.correctedHeading, base.Angle(359., base.HEADING))


    def test_correctedHeadingUnderflowEdgeCase(self):
        """
        Tests that a corrected heading that comes out under 0 degrees is
        correctly handled.
        """
        h = base.Heading.fromFloats(1., variationValue=1.)
        self.assertEquals(h.correctedHeading, base.Angle(0., base.HEADING))


    def test_setVariationSign(self):
        """
        Tests that setting the sign on a variation works.
        """
        h = base.Heading.fromFloats(1., variationValue=1.)
        h.setSign(1)
        self.assertEquals(h.variation.inDecimalDegrees, 1.)
        h.setSign(-1)
        self.assertEquals(h.variation.inDecimalDegrees, -1.)


    def test_setBadVariationSign(self):
        """
        Tests that setting invalid sign values on a variation fails
        predictably.
        """
        h = base.Heading.fromFloats(1., variationValue=1.)
        self.assertRaises(ValueError, h.setSign, -50)
        self.assertEquals(h.variation.inDecimalDegrees, 1.)

        self.assertRaises(ValueError, h.setSign, 0)
        self.assertEquals(h.variation.inDecimalDegrees, 1.)

        self.assertRaises(ValueError, h.setSign, 50)
        self.assertEquals(h.variation.inDecimalDegrees, 1.)


    def test_setUnknownVariationSign(self):
        """
        Tests that setting an otherwise correct sign on an unknown variation
        fails predictably.
        """
        h = base.Heading.fromFloats(1.)
        self.assertEquals(None, h.variation.inDecimalDegrees)
        self.assertRaises(ValueError, h.setSign, 1)



class CoordinateTests(TestCase):
    def test_simple(self):
        """
        Test that coordinates are convertible into a float, and verifies the
        generic coordinate repr.
        """
        value = 10.0
        c = base.Coordinate(value)
        self.assertEquals(float(c), value)
        expectedRepr = "<Angle of unknown type (%s degrees)>" % (value,) 
        self.assertEquals(repr(c), expectedRepr)


    def test_positiveLatitude(self):
        """
        Tests creating positive latitudes and verifies their repr.
        """
        value = 50.0
        c = base.Coordinate(value, LATITUDE)
        self.assertEquals(repr(c), "<Latitude (%s degrees)>" % value)


    def test_negativeLatitude(self):
        """
        Tests creating negative latitudes and verifies their repr.
        """
        value = -50.0
        c = base.Coordinate(value, LATITUDE)
        self.assertEquals(repr(c), "<Latitude (%s degrees)>" % value)


    def test_positiveLongitude(self):
        """
        Tests creating positive longitudes and verifies their repr.
        """
        value = 50.0
        c = base.Coordinate(value, LONGITUDE)
        self.assertEquals(repr(c), "<Longitude (%s degrees)>" % value)


    def test_negativeLongitude(self):
        """
        Tests creating negative longitudes and verifies their repr.
        """
        value = -50.0
        c = base.Coordinate(value, LONGITUDE)
        self.assertEquals(repr(c), "<Longitude (%s degrees)>" % value)


    def test_badCoordinateType(self):
        """
        Tests that creating coordinates with bogus types raises C{ValueError}.
        """
        self.assertRaises(ValueError, base.Coordinate, 150.0, "BOGUS")


    def test_equality(self):
        """
        Tests that equal coordinates compare equal.
        """
        self.assertEquals(base.Coordinate(1.0), base.Coordinate(1.0))


    def test_differentAnglesInequality(self):
        """
        Tests that coordinates with different angles compare unequal.
        """
        c1 = base.Coordinate(1.0)
        c2 = base.Coordinate(-1.0)
        self.assertNotEquals(c1, c2)


    def test_differentTypesInequality(self):
        """
        Tests that coordinates with the same angles but different types
        compare unequal.
        """
        c1 = base.Coordinate(1.0, LATITUDE)
        c2 = base.Coordinate(1.0, LONGITUDE)
        self.assertNotEquals(c1, c2)


    def test_sign(self):
        """
        Tests that setting the sign on a coordinate works.
        """
        c = base.Coordinate(50., LATITUDE)
        c.setSign(1)
        self.assertEquals(c.inDecimalDegrees, 50.)
        c.setSign(-1)
        self.assertEquals(c.inDecimalDegrees, -50.)


    def test_badVariationSign(self):
        """
        Tests that setting a bogus sign value on a coordinate raises
        C{ValueError} and doesn't affect the coordinate.
        """
        value = 50.0
        c = base.Coordinate(value, LATITUDE)

        self.assertRaises(ValueError, c.setSign, -50)
        self.assertEquals(c.inDecimalDegrees, 50.)

        self.assertRaises(ValueError, c.setSign, 0)
        self.assertEquals(c.inDecimalDegrees, 50.)

        self.assertRaises(ValueError, c.setSign, 50)
        self.assertEquals(c.inDecimalDegrees, 50.)


    def test_hemispheres(self):
        """
        Checks that coordinates know which hemisphere they're in.
        """
        coordinatesAndHemispheres = [
            (base.Coordinate(1.0, LATITUDE), NORTH),
            (base.Coordinate(-1.0, LATITUDE), SOUTH),
            (base.Coordinate(1.0, LONGITUDE), EAST),
            (base.Coordinate(-1.0, LONGITUDE), WEST),
        ]

        for coordinate, expectedHemisphere in coordinatesAndHemispheres:
            self.assertEquals(expectedHemisphere, coordinate.hemisphere)


    def test_badHemisphere(self):
        """
        Checks that asking for a hemisphere when the coordinate doesn't know
        raises C{ValueError}.
        """
        c = base.Coordinate(1.0, None)
        self.assertRaises(ValueError, lambda: c.hemisphere)


    def test_badLatitudeValues(self):
        """
        Tests that latitudes outside of M{-90.0 < latitude < 90.0} raise
        C{ValueError}.
        """
        self.assertRaises(ValueError, base.Coordinate, 150.0, LATITUDE)
        self.assertRaises(ValueError, base.Coordinate, -150.0, LATITUDE)


    def test_badLongitudeValues(self):
        """
        Tests that longitudes outside of M{-180.0 < longitude < 180.0} raise
        C{ValueError}.
        """
        self.assertRaises(ValueError, base.Coordinate, 250.0, LONGITUDE)
        self.assertRaises(ValueError, base.Coordinate, -250.0, LONGITUDE)


    def test_inDegreesMinutesSeconds(self):
        """
        Tests accessing coordinate values in degrees, minutes and seconds.
        """
        c = base.Coordinate(50.5, LATITUDE)
        self.assertEquals(c.inDegreesMinutesSeconds, (50, 30, 0))

        c = base.Coordinate(50.213, LATITUDE)
        self.assertEquals(c.inDegreesMinutesSeconds, (50, 12, 46))


    def test_unknownAngleInDegreesMinutesSeconds(self):
        """
        Tests accessing unknown coordinate values in degrees, minutes
        and seconds.
        """
        c = base.Coordinate(None, None)
        self.assertEquals(c.inDegreesMinutesSeconds, None)



class AltitudeTests(TestCase):
    """
    Tests for the L{twisted.positioning.base.Altitude} class.
    """
    def test_simple(self):
        """
        Tests basic altitude functionality.
        """
        a = base.Altitude(1.)
        self.assertEquals(float(a), 1.)
        self.assertEquals(a.inMeters, 1.)
        self.assertEquals(a.inFeet, 1./base.METERS_PER_FOOT)
        self.assertEquals(repr(a), "<Altitude (1.0 m)>")


    def test_equality(self):
        """
        Tests that equal altitudes compare equal.
        """
        a1 = base.Altitude(1.)
        a2 = base.Altitude(1.)
        self.assertEquals(a1, a2)


    def test_inequality(self):
        """
        Tests that unequal altitudes compare unequal.
        """
        a1 = base.Altitude(1.)
        a2 = base.Altitude(-1.)
        self.assertNotEquals(a1, a2)



class SpeedTests(TestCase):
    """
    Tests for the L{twisted.positioning.base.Speed} class.
    """
    def test_simple(self):
        """
        Tests basic speed functionality.
        """
        s = base.Speed(50.0)
        self.assertEquals(s.inMetersPerSecond, 50.0)
        self.assertEquals(float(s), 50.0)
        self.assertEquals(repr(s), "<Speed (50.0 m/s)>")


    def test_negativeSpeeds(self):
        """
        Tests that negative speeds raise C{ValueError}.
        """
        self.assertRaises(ValueError, base.Speed, -1.0)


    def test_inKnots(self):
        """
        Tests that speeds can be converted into knots correctly.
        """
        s = base.Speed(1.0)
        self.assertEquals(1/base.MPS_PER_KNOT, s.inKnots)


    def test_asFloat(self):
        """
        Tests that speeds can be converted into C{float}s correctly.
        """
        self.assertEquals(1.0, float(base.Speed(1.0)))



class ClimbTests(TestCase):
    """
    Tests for L{twisted.positioning.base.Climb}.
    """
    def test_simple(self):
        """
        Basic functionality for climb objects.
        """
        s = base.Climb(42.)
        self.assertEquals(s.inMetersPerSecond, 42.)
        self.assertEquals(float(s), 42.)
        self.assertEquals(repr(s), "<Climb (42.0 m/s)>")


    def test_negativeClimbs(self):
        """
        Tests that creating negative climbs works.
        """
        base.Climb(-42.)


    def test_speedInKnots(self):
        """
        Tests that climbs can be converted into knots correctly.
        """
        s = base.Climb(1.0)
        self.assertEquals(1/base.MPS_PER_KNOT, s.inKnots)


    def test_asFloat(self):
        """
        Tests that speeds can be converted into C{float}s correctly.
        """
        self.assertEquals(1.0, float(base.Climb(1.0)))



class PositionErrorTests(TestCase):
    """
    Tests for L{twisted.positioning.base.PositionError}.
    """
    def test_allUnset(self):
        """
        Tests that creating an empty L{PositionError} works without checking
        the invariant.
        """
        pe = base.PositionError()
        for x in (pe.pdop, pe.hdop, pe.vdop):
            self.assertEquals(None, x)


    def test_allUnsetWithInvariant(self):
        """
        Tests that creating an empty L{PositionError} works while checking the
        invariant.
        """
        pe = base.PositionError(testInvariant=True)
        for x in (pe.pdop, pe.hdop, pe.vdop):
            self.assertEquals(None, x)


    def test_simpleWithoutInvariant(self):
        """
        Tests that creating a simple L{PositionError} with just a HDOP without
        checking the invariant works.
        """
        base.PositionError(hdop=1.0)


    def test_simpleWithInvariant(self):
        """
        Tests that creating a simple L{PositionError} with just a HDOP while
        checking the invariant works.
        """
        base.PositionError(hdop=1.0, testInvariant=True)


    def test_invalidWithoutInvariant(self):
        """
        Tests that creating a simple L{PositionError} with all values set
        without checking the invariant works.
        """
        base.PositionError(pdop=1.0, vdop=1.0, hdop=1.0)


    def test_invalidWithInvariant(self):
        """
        Tests that creating a simple L{PositionError} with all values set to
        inconsistent values while checking the invariant raises C{ValueError}.
        """
        self.assertRaises(ValueError, base.PositionError,
                          pdop=1.0, vdop=1.0, hdop=1.0, testInvariant=True)


    def test_setDOPWithoutInvariant(self):
        """
        Tests that setting the PDOP value (with HDOP and VDOP already known)
        to an inconsistent value without checking the invariant works.
        """
        pe = base.PositionError(hdop=1.0, vdop=1.0)
        pe.pdop = 100.0
        self.assertEquals(pe.pdop, 100.0)


    def test_setDOPWithInvariant(self):
        """
        Tests that setting the PDOP value (with HDOP and VDOP already known)
        to an inconsistent value while checking the invariant raises
        C{ValueError}.
        """
        pe = base.PositionError(hdop=1.0, vdop=1.0, testInvariant=True)
        pdop = pe.pdop

        def setPDOP(pe):
            pe.pdop = 100.0

        self.assertRaises(ValueError, setPDOP, pe)
        self.assertEqual(pe.pdop, pdop)


    REPR_TEMPLATE = "<PositionError (pdop: %s, hdop: %s, vdop: %s)>"


    def _testDOP(self, pe, pdop, hdop, vdop):
        """
        Tests the DOP values in a position error, and the repr of that
        position error.
        """
        self.assertEquals(pe.pdop, pdop)
        self.assertEquals(pe.hdop, hdop)
        self.assertEquals(pe.vdop, vdop)
        self.assertEquals(repr(pe), self.REPR_TEMPLATE % (pdop, hdop, vdop))


    def test_positionAndHorizontalSet(self):
        """
        Tests that the VDOP is correctly determined from PDOP and HDOP.
        """
        pdop, hdop = 2.0, 1.0
        vdop = (pdop**2 - hdop**2)**.5
        pe = base.PositionError(pdop=pdop, hdop=hdop)
        self._testDOP(pe, pdop, hdop, vdop)


    def test_positionAndVerticalSet(self):
        """
        Tests that the HDOP is correctly determined from PDOP and VDOP.
        """
        pdop, vdop = 2.0, 1.0
        hdop = (pdop**2 - vdop**2)**.5
        pe = base.PositionError(pdop=pdop, vdop=vdop)
        self._testDOP(pe, pdop, hdop, vdop)


    def test_horizontalAndVerticalSet(self):
        """
        Tests that the PDOP is correctly determined from HDOP and VDOP.
        """
        hdop, vdop = 1.0, 1.0
        pdop = (hdop**2 + vdop**2)**.5
        pe = base.PositionError(hdop=hdop, vdop=vdop)
        self._testDOP(pe, pdop, hdop, vdop)



class BeaconInformationTests(TestCase):
    """
    Tests for L{twisted.positioning.base.BeaconInformation}.
    """
    def test_minimal(self):
        """
        Tests some basic features of a minimal beacon information object.

        Tests the number of used beacons is zero, the total number of
        beacons (the number of seen beacons) is zero, and the repr of
        the object.
        """
        bi = base.BeaconInformation()
        self.assertEquals(len(list(bi.usedBeacons)), 0)
        self.assertEquals(len(list(bi)), 0)
        self.assertEquals(repr(bi),
            "<BeaconInformation (seen: 0, used: 0, beacons: {})>")


    satelliteKwargs = {"azimuth": 1, "elevation": 1, "signalToNoiseRatio": 1.}


    def test_simple(self):
        """
        Tests a beacon information with a bunch of satellites, none of
        which used in computing a fix.
        """
        def _buildSatellite(**kw):
            kwargs = dict(self.satelliteKwargs)
            kwargs.update(kw)
            return base.Satellite(isUsed=None, **kwargs)

        beacons = set()
        for prn in range(1, 10):
            beacons.add(_buildSatellite(identifier=prn))

        bi = base.BeaconInformation(beacons)

        self.assertEquals(len(list(bi.usedBeacons)), 0)
        self.assertEquals(bi.used, None)
        self.assertEquals(len(list(bi)), 9)
        self.assertEquals(repr(bi),
            "<BeaconInformation (seen: 9, used: ?, beacons: {"
            "<Satellite (1), azimuth: 1, elevation: 1, snr: 1.0, used: ?>, "
            "<Satellite (2), azimuth: 1, elevation: 1, snr: 1.0, used: ?>, "
            "<Satellite (3), azimuth: 1, elevation: 1, snr: 1.0, used: ?>, "
            "<Satellite (4), azimuth: 1, elevation: 1, snr: 1.0, used: ?>, "
            "<Satellite (5), azimuth: 1, elevation: 1, snr: 1.0, used: ?>, "
            "<Satellite (6), azimuth: 1, elevation: 1, snr: 1.0, used: ?>, "
            "<Satellite (7), azimuth: 1, elevation: 1, snr: 1.0, used: ?>, "
            "<Satellite (8), azimuth: 1, elevation: 1, snr: 1.0, used: ?>, "
            "<Satellite (9), azimuth: 1, elevation: 1, snr: 1.0, used: ?>"
            "})>")


    def test_someSatellitesUsed(self):
        """
        Tests a beacon information with a bunch of satellites, some of
        them used in computing a fix.
        """
        def _buildSatellite(**kw):
            kwargs = dict(self.satelliteKwargs)
            kwargs.update(kw)
            return base.Satellite(**kwargs)

        beacons = set()
        for prn in range(1, 10):
            isUsed = bool(prn % 2)
            satellite = _buildSatellite(identifier=prn, isUsed=isUsed)
            beacons.add(satellite)

        bi = base.BeaconInformation(beacons)

        self.assertEquals(len(list(bi.usedBeacons)), 5)
        self.assertEquals(bi.used, 5)
        self.assertEquals(len(list(bi)), 9)
        self.assertEquals(len(bi.beacons), 9)
        self.assertEquals(bi.seen, 9)
        self.assertEquals(repr(bi),
            "<BeaconInformation (seen: 9, used: 5, beacons: {"
            "<Satellite (1), azimuth: 1, elevation: 1, snr: 1.0, used: Y>, "
            "<Satellite (2), azimuth: 1, elevation: 1, snr: 1.0, used: N>, "
            "<Satellite (3), azimuth: 1, elevation: 1, snr: 1.0, used: Y>, "
            "<Satellite (4), azimuth: 1, elevation: 1, snr: 1.0, used: N>, "
            "<Satellite (5), azimuth: 1, elevation: 1, snr: 1.0, used: Y>, "
            "<Satellite (6), azimuth: 1, elevation: 1, snr: 1.0, used: N>, "
            "<Satellite (7), azimuth: 1, elevation: 1, snr: 1.0, used: Y>, "
            "<Satellite (8), azimuth: 1, elevation: 1, snr: 1.0, used: N>, "
            "<Satellite (9), azimuth: 1, elevation: 1, snr: 1.0, used: Y>"
            "})>")



class PositioningBeaconTests(TestCase):
    """
    Tests for L{twisted.positioning.base.PositioningBeacon}.
    """
    def test_usedRepr(self):
        """
        Tests the repr of a positioning beacon being used.
        """
        s = base.PositioningBeacon("A", True)
        self.assertEquals(repr(s), "<Beacon (identifier: A, used: Y)>")


    def test_unusedRepr(self):
        """
        Tests the repr of a positioning beacon not being used.
        """
        s = base.PositioningBeacon("A", False)
        self.assertEquals(repr(s), "<Beacon (identifier: A, used: N)>")


    def test_dontKnowIfUsed(self):
        """
        Tests the repr of a positioning beacon that might be used.
        """
        s = base.PositioningBeacon("A", None)
        self.assertEquals(repr(s), "<Beacon (identifier: A, used: ?)>")



class SatelliteTests(TestCase):
    """
    Tests for L{twisted.positioning.base.Satellite}.
    """
    def test_minimal(self):
        """
        Tests a minimal satellite that only has a known PRN.

        Tests that the azimuth, elevation and signal to noise ratios
        are C{None} and verifies the repr.
        """
        s = base.Satellite(1)
        self.assertEquals(s.identifier, 1)
        self.assertEquals(s.azimuth, None)
        self.assertEquals(s.elevation, None)
        self.assertEquals(s.signalToNoiseRatio, None)
        self.assertEquals(repr(s), "<Satellite (1), azimuth: ?, "
                                   "elevation: ?, snr: ?, used: ?>")


    def test_simple(self):
        """
        Tests a minimal satellite that only has a known PRN.

        Tests that the azimuth, elevation and signal to noise ratios
        are correct and verifies the repr.
        """
        s = base.Satellite(identifier=1,
                           azimuth=270.,
                           elevation=30.,
                           signalToNoiseRatio=25.,
                           isUsed=True)

        self.assertEquals(s.identifier, 1)
        self.assertEquals(s.azimuth, 270.)
        self.assertEquals(s.elevation, 30.)
        self.assertEquals(s.signalToNoiseRatio, 25.)
        self.assertEquals(repr(s), "<Satellite (1), azimuth: 270.0, "
                                   "elevation: 30.0, snr: 25.0, used: Y>")
