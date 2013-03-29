# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.
"""
Test cases for positioning primitives.
"""
from twisted.trial.unittest import TestCase
from twisted.positioning import base
from twisted.positioning.base import Angles, Directions


class AngleTests(TestCase):
    """
    Tests for the L{twisted.positioning.base.Angle} class.
    """
    def test_empty(self):
        """
        The repr of an empty angle says that is of unknown type and unknown
        value.
        """
        a = base.Angle()
        self.assertEqual("<Angle of unknown type (unknown value)>", repr(a))


    def test_variation(self):
        """
        The repr of an empty variation says that it is a variation of unknown
        value.
        """
        a = base.Angle(angleType=Angles.VARIATION)
        self.assertEqual("<Variation (unknown value)>", repr(a))


    def test_unknownType(self):
        """
        The repr of an angle of unknown type but a given value displays that
        type and value in its repr.
        """
        a = base.Angle(1.0)
        self.assertEqual("<Angle of unknown type (1.0 degrees)>", repr(a))



class HeadingTests(TestCase):
    """
    Tests for the L{twisted.positioning.base.Heading} class.
    """
    def test_simple(self):
        """
        Tests that a simple heading has a value in decimal degrees, which is
        also its value when converted to a float. Its variation, and by
        consequence its corrected heading, is C{None}.
        """
        h = base.Heading(1.)
        self.assertEqual(h.inDecimalDegrees, 1.)
        self.assertEqual(float(h), 1.)
        self.assertEqual(h.variation, None)
        self.assertEqual(h.correctedHeading, None)


    def test_headingWithoutVariationRepr(self):
        """
        A repr of a heading with no variation reports its value and that the
        variation is unknown.
        """
        heading = base.Heading(1.)
        expectedRepr = "<Heading (1.0 degrees, unknown variation)>"
        self.assertEqual(repr(heading), expectedRepr)


    def test_headingWithVariationRepr(self):
        """
        A repr of a heading with known variation reports its value and the
        value of that variation.
        """
        angle, variation = 1.0, -10.0
        h = base.Heading.fromFloats(angle, variationValue=variation)

        variationRepr = '<Variation (%s degrees)>' % (variation,)
        expectedRepr = '<Heading (%s degrees, %s)>' % (angle, variationRepr)
        self.assertEqual(repr(h), expectedRepr)


    def test_valueEquality(self):
        """
        Headings with the same values compare equal.
        """
        self.assertEqual(base.Heading(1.), base.Heading(1.))


    def test_valueInequality(self):
        """
        Headings with different values compare unequal.
        """
        self.assertNotEquals(base.Heading(1.), base.Heading(2.))


    def test_zeroHeadingEdgeCase(self):
        """
        Headings can be instantiated with a value of 0 and no variation.
        """
        base.Heading(0)


    def test_zeroHeading180DegreeVariationEdgeCase(self):
        """
        Headings can be instantiated with a value of 0 and a variation of 180
        degrees.
        """
        base.Heading(0, 180)


    def _badValueTest(self, **kw):
        """
        Helper function for verifying that bad values raise C{ValueError}.

        @param kw: The keyword arguments passed to L{base.Heading.fromFloats}.
        """
        self.assertRaises(ValueError, base.Heading.fromFloats, **kw)


    def test_badAngleValueEdgeCase(self):
        """
        Headings can not be instantiated with a value of 360 degrees.
        """
        self._badValueTest(angleValue=360.0)


    def test_badVariationEdgeCase(self):
        """
        Headings can not be instantiated with a variation of -180 degrees.
        """
        self._badValueTest(variationValue=-180.0)


    def test_negativeHeading(self):
        """
        Negative heading values raise C{ValueError}.
        """
        self._badValueTest(angleValue=-10.0)


    def test_headingTooLarge(self):
        """
        Heading values greater than C{360.0} raise C{ValueError}.
        """
        self._badValueTest(angleValue=370.0)


    def test_variationTooNegative(self):
        """
        Variation values less than C{-180.0} raise C{ValueError}.
        """
        self._badValueTest(variationValue=-190.0)


    def test_variationTooPositive(self):
        """
        Variation values greater than C{180.0} raise C{ValueError}.
        """
        self._badValueTest(variationValue=190.0)


    def test_correctedHeading(self):
        """
        A heading with a value and a variation has a corrected heading.
        """
        h = base.Heading.fromFloats(1., variationValue=-10.)
        self.assertEqual(h.correctedHeading, base.Angle(11., Angles.HEADING))


    def test_correctedHeadingOverflow(self):
        """
        A heading with a value and a variation has the appropriate corrected
        heading value, even when the variation puts it across the 360 degree
        boundary.
        """
        h = base.Heading.fromFloats(359., variationValue=-2.)
        self.assertEqual(h.correctedHeading, base.Angle(1., Angles.HEADING))


    def test_correctedHeadingOverflowEdgeCase(self):
        """
        A heading with a value and a variation has the appropriate corrected
        heading value, even when the variation puts it exactly at the 360
        degree boundary.
        """
        h = base.Heading.fromFloats(359., variationValue=-1.)
        self.assertEqual(h.correctedHeading, base.Angle(0., Angles.HEADING))


    def test_correctedHeadingUnderflow(self):
        """
        A heading with a value and a variation has the appropriate corrected
        heading value, even when the variation puts it under the 0 degree
        boundary.
        """
        h = base.Heading.fromFloats(1., variationValue=2.)
        self.assertEqual(h.correctedHeading, base.Angle(359., Angles.HEADING))


    def test_correctedHeadingUnderflowEdgeCase(self):
        """
        A heading with a value and a variation has the appropriate corrected
        heading value, even when the variation puts it exactly at the 0
        degree boundary.
        """
        h = base.Heading.fromFloats(1., variationValue=1.)
        self.assertEqual(h.correctedHeading, base.Angle(0., Angles.HEADING))


    def test_setVariationSign(self):
        """
        Setting the sign of a heading changes the variation sign.
        """
        h = base.Heading.fromFloats(1., variationValue=1.)
        h.setSign(1)
        self.assertEqual(h.variation.inDecimalDegrees, 1.)
        h.setSign(-1)
        self.assertEqual(h.variation.inDecimalDegrees, -1.)


    def test_setBadVariationSign(self):
        """
        Setting the sign of a heading to values that aren't C{-1} or C{1}
        raises C{ValueError} and does not affect the heading.
        """
        h = base.Heading.fromFloats(1., variationValue=1.)
        self.assertRaises(ValueError, h.setSign, -50)
        self.assertEqual(h.variation.inDecimalDegrees, 1.)

        self.assertRaises(ValueError, h.setSign, 0)
        self.assertEqual(h.variation.inDecimalDegrees, 1.)

        self.assertRaises(ValueError, h.setSign, 50)
        self.assertEqual(h.variation.inDecimalDegrees, 1.)


    def test_setUnknownVariationSign(self):
        """
        Setting the sign on a heading with unknown variation raises
        C{ValueError}.
        """
        h = base.Heading.fromFloats(1.)
        self.assertIdentical(None, h.variation.inDecimalDegrees)
        self.assertRaises(ValueError, h.setSign, 1)



class CoordinateTests(TestCase): ## TODO: START HERE
    def test_simple(self):
        """
        Test that coordinates are convertible into a float, and verifies the
        generic coordinate repr.
        """
        value = 10.0
        c = base.Coordinate(value)
        self.assertEqual(float(c), value)
        expectedRepr = "<Angle of unknown type (%s degrees)>" % (value,)
        self.assertEqual(repr(c), expectedRepr)


    def test_positiveLatitude(self):
        """
        Tests creating positive latitudes and verifies their repr.
        """
        value = 50.0
        c = base.Coordinate(value, Angles.LATITUDE)
        self.assertEqual(repr(c), "<Latitude (%s degrees)>" % value)


    def test_negativeLatitude(self):
        """
        Tests creating negative latitudes and verifies their repr.
        """
        value = -50.0
        c = base.Coordinate(value, Angles.LATITUDE)
        self.assertEqual(repr(c), "<Latitude (%s degrees)>" % value)


    def test_positiveLongitude(self):
        """
        Tests creating positive longitudes and verifies their repr.
        """
        value = 50.0
        c = base.Coordinate(value, Angles.LONGITUDE)
        self.assertEqual(repr(c), "<Longitude (%s degrees)>" % value)


    def test_negativeLongitude(self):
        """
        Tests creating negative longitudes and verifies their repr.
        """
        value = -50.0
        c = base.Coordinate(value, Angles.LONGITUDE)
        self.assertEqual(repr(c), "<Longitude (%s degrees)>" % value)


    def test_badCoordinateType(self):
        """
        Tests that creating coordinates with bogus types raises C{ValueError}.
        """
        self.assertRaises(ValueError, base.Coordinate, 150.0, "BOGUS")


    def test_equality(self):
        """
        Tests that equal coordinates compare equal.
        """
        self.assertEqual(base.Coordinate(1.0), base.Coordinate(1.0))


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
        c1 = base.Coordinate(1.0, Angles.LATITUDE)
        c2 = base.Coordinate(1.0, Angles.LONGITUDE)
        self.assertNotEquals(c1, c2)


    def test_sign(self):
        """
        Tests that setting the sign on a coordinate works.
        """
        c = base.Coordinate(50., Angles.LATITUDE)
        c.setSign(1)
        self.assertEqual(c.inDecimalDegrees, 50.)
        c.setSign(-1)
        self.assertEqual(c.inDecimalDegrees, -50.)


    def test_badVariationSign(self):
        """
        Tests that setting a bogus sign value on a coordinate raises
        C{ValueError} and doesn't affect the coordinate.
        """
        value = 50.0
        c = base.Coordinate(value, Angles.LATITUDE)

        self.assertRaises(ValueError, c.setSign, -50)
        self.assertEqual(c.inDecimalDegrees, 50.)

        self.assertRaises(ValueError, c.setSign, 0)
        self.assertEqual(c.inDecimalDegrees, 50.)

        self.assertRaises(ValueError, c.setSign, 50)
        self.assertEqual(c.inDecimalDegrees, 50.)


    def test_hemispheres(self):
        """
        Checks that coordinates know which hemisphere they're in.
        """
        coordinatesAndHemispheres = [
            (base.Coordinate(1.0, Angles.LATITUDE), Directions.NORTH),
            (base.Coordinate(-1.0, Angles.LATITUDE), Directions.SOUTH),
            (base.Coordinate(1.0, Angles.LONGITUDE), Directions.EAST),
            (base.Coordinate(-1.0, Angles.LONGITUDE), Directions.WEST),
        ]

        for coordinate, expectedHemisphere in coordinatesAndHemispheres:
            self.assertEqual(expectedHemisphere, coordinate.hemisphere)


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
        self.assertRaises(ValueError, base.Coordinate, 150.0, Angles.LATITUDE)
        self.assertRaises(ValueError, base.Coordinate, -150.0, Angles.LATITUDE)


    def test_badLongitudeValues(self):
        """
        Tests that longitudes outside of M{-180.0 < longitude < 180.0} raise
        C{ValueError}.
        """
        self.assertRaises(ValueError, base.Coordinate, 250.0, Angles.LONGITUDE)
        self.assertRaises(ValueError, base.Coordinate, -250.0, Angles.LONGITUDE)


    def test_inDegreesMinutesSeconds(self):
        """
        Tests accessing coordinate values in degrees, minutes and seconds.
        """
        c = base.Coordinate(50.5, Angles.LATITUDE)
        self.assertEqual(c.inDegreesMinutesSeconds, (50, 30, 0))

        c = base.Coordinate(50.213, Angles.LATITUDE)
        self.assertEqual(c.inDegreesMinutesSeconds, (50, 12, 46))


    def test_unknownAngleInDegreesMinutesSeconds(self):
        """
        Tests accessing unknown coordinate values in degrees, minutes
        and seconds.
        """
        c = base.Coordinate(None, None)
        self.assertEqual(c.inDegreesMinutesSeconds, None)



class AltitudeTests(TestCase):
    """
    Tests for the L{twisted.positioning.base.Altitude} class.
    """
    def test_simple(self):
        """
        Tests basic altitude functionality.
        """
        a = base.Altitude(1.)
        self.assertEqual(float(a), 1.)
        self.assertEqual(a.inMeters, 1.)
        self.assertEqual(a.inFeet, 1./base.METERS_PER_FOOT)
        self.assertEqual(repr(a), "<Altitude (1.0 m)>")


    def test_equality(self):
        """
        Tests that equal altitudes compare equal.
        """
        a1 = base.Altitude(1.)
        a2 = base.Altitude(1.)
        self.assertEqual(a1, a2)


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
        self.assertEqual(s.inMetersPerSecond, 50.0)
        self.assertEqual(float(s), 50.0)
        self.assertEqual(repr(s), "<Speed (50.0 m/s)>")


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
        self.assertEqual(1/base.MPS_PER_KNOT, s.inKnots)


    def test_asFloat(self):
        """
        Tests that speeds can be converted into C{float}s correctly.
        """
        self.assertEqual(1.0, float(base.Speed(1.0)))



class ClimbTests(TestCase):
    """
    Tests for L{twisted.positioning.base.Climb}.
    """
    def test_simple(self):
        """
        Basic functionality for climb objects.
        """
        s = base.Climb(42.)
        self.assertEqual(s.inMetersPerSecond, 42.)
        self.assertEqual(float(s), 42.)
        self.assertEqual(repr(s), "<Climb (42.0 m/s)>")


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
        self.assertEqual(1/base.MPS_PER_KNOT, s.inKnots)


    def test_asFloat(self):
        """
        Tests that speeds can be converted into C{float}s correctly.
        """
        self.assertEqual(1.0, float(base.Climb(1.0)))



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
            self.assertEqual(None, x)


    def test_allUnsetWithInvariant(self):
        """
        Tests that creating an empty L{PositionError} works while checking the
        invariant.
        """
        pe = base.PositionError(testInvariant=True)
        for x in (pe.pdop, pe.hdop, pe.vdop):
            self.assertEqual(None, x)


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
        self.assertEqual(pe.pdop, 100.0)


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

        @param pe: The position error under test.
        @type pe: C{PositionError}
        @param pdop: The expected position dilution of precision.
        @type pdop: C{float} or C{NoneType}
        @param hdop: The expected horizontal dilution of precision.
        @type hdop: C{float} or C{NoneType}
        @param vdop: The expected vertical dilution of precision.
        @type vdop: C{float} or C{NoneType}
        """
        self.assertEqual(pe.pdop, pdop)
        self.assertEqual(pe.hdop, hdop)
        self.assertEqual(pe.vdop, vdop)
        self.assertEqual(repr(pe), self.REPR_TEMPLATE % (pdop, hdop, vdop))


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
        self.assertEqual(len(list(bi.usedBeacons)), 0)
        self.assertEqual(len(list(bi)), 0)
        self.assertEqual(repr(bi),
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

        self.assertEqual(len(list(bi.usedBeacons)), 0)
        self.assertEqual(bi.used, None)
        self.assertEqual(len(list(bi)), 9)
        self.assertEqual(repr(bi),
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

        self.assertEqual(len(list(bi.usedBeacons)), 5)
        self.assertEqual(bi.used, 5)
        self.assertEqual(len(list(bi)), 9)
        self.assertEqual(len(bi.beacons), 9)
        self.assertEqual(bi.seen, 9)
        self.assertEqual(repr(bi),
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
        self.assertEqual(repr(s), "<Beacon (identifier: A, used: Y)>")


    def test_unusedRepr(self):
        """
        Tests the repr of a positioning beacon not being used.
        """
        s = base.PositioningBeacon("A", False)
        self.assertEqual(repr(s), "<Beacon (identifier: A, used: N)>")


    def test_dontKnowIfUsed(self):
        """
        Tests the repr of a positioning beacon that might be used.
        """
        s = base.PositioningBeacon("A", None)
        self.assertEqual(repr(s), "<Beacon (identifier: A, used: ?)>")



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
        self.assertEqual(s.identifier, 1)
        self.assertEqual(s.azimuth, None)
        self.assertEqual(s.elevation, None)
        self.assertEqual(s.signalToNoiseRatio, None)
        self.assertEqual(repr(s), "<Satellite (1), azimuth: ?, "
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

        self.assertEqual(s.identifier, 1)
        self.assertEqual(s.azimuth, 270.)
        self.assertEqual(s.elevation, 30.)
        self.assertEqual(s.signalToNoiseRatio, 25.)
        self.assertEqual(repr(s), "<Satellite (1), azimuth: 270.0, "
                                   "elevation: 30.0, snr: 25.0, used: Y>")
