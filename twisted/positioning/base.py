# -*- test-case-name: twisted.positioning.test.test_base,twisted.positioning.test.test_sentence -*-
# Copyright (c) 2009-2011 Twisted Matrix Laboratories.
# See LICENSE for details.
"""
Generic positioning base classes.

@since: 11.1
"""
from zope.interface import implements
from twisted.python.util import FancyEqMixin

from twisted.positioning import ipositioning

MPS_PER_KNOT = 0.5144444444444444
MPS_PER_KPH = 0.27777777777777777
METERS_PER_FOOT = 0.3048

LATITUDE, LONGITUDE, HEADING, VARIATION = range(4)
NORTH, EAST, SOUTH, WEST = range(4)



class BasePositioningReceiver(object):
    """
    A base positioning receiver.

    This class would be a good base class for building positioning
    receivers. It implements the interface (so you don't have to) with stub
    methods.

    People who want to implement positioning receivers should subclass this
    class and override the specific callbacks they want to handle.
    """
    implements(ipositioning.IPositioningReceiver)

    def timeReceived(self, time):
        """
        Implements L{IPositioningReceiver.timeReceived} stub.
        """


    def headingReceived(self, heading):
        """
        Implements L{IPositioningReceiver.headingReceived} stub.
        """


    def speedReceived(self, speed):
        """
        Implements L{IPositioningReceiver.speedReceived} stub.
        """


    def climbReceived(self, climb):
        """
        Implements L{IPositioningReceiver.climbReceived} stub.
        """


    def positionReceived(self, latitude, longitude):
        """
        Implements L{IPositioningReceiver.positionReceived} stub.
        """


    def positionErrorReceived(self, positionError):
        """
        Implements L{IPositioningReceiver.positioningErrorReceived} stub.
        """


    def altitudeReceived(self, altitude):
        """
        Implements L{IPositioningReceiver.altitudeReceived} stub.
        """


    def beaconInformationReceived(self, beaconInformation):
        """
        Implements L{IPositioningReceiver.beaconInformationReceived} stub.
        """



class InvalidSentence(Exception):
    """
    An exception raised when a sentence is invalid.
    """



class InvalidChecksum(Exception):
    """
    An exception raised when the checksum of a sentence is invalid.
    """


class BaseSentence(object):
    """
    A base sentence class for a particular protocol.

    Using this base class, specific sentence classes can almost automatically
    be created for a particular protocol (except for the documentation of
    course) if that protocol implements the L{IPositioningSentenceProducer}
    interface. To do this, fill the ALLOWED_ATTRIBUTES class attribute using
    the C{getSentenceAttributes} class method of the producer::

        class FooSentence(BaseSentence):
            \"\"\"
            A sentence for integalactic transmodulator sentences.

            @ivar transmogrificationConstant: The value used in the
                transmogrifier while producing this sentence, corrected for
                gravitational fields.
            @type transmogrificationConstant: C{Tummy}
            \"\"\"
            ALLOWED_ATTRIBUTES = FooProtocol.getSentenceAttributes()

    @ivar presentAttribues: An iterable containing the names of the
        attributes that are present in this sentence.
    @type presentAttributes: iterable of C{str}

    @cvar ALLOWED_ATTRIBUTES: A set of attributes that are allowed in this
        sentence.
    @type ALLOWED_ATTRIBUTES: C{set} of C{str}
    """
    ALLOWED_ATTRIBUTES = set()


    def __init__(self, sentenceData):
        """
        Initializes a sentence with parsed sentence data.

        @param sentenceData: The parsed sentence data.
        @type sentenceData: C{dict} (C{str} -> C{str} or C{NoneType})
        """
        self._sentenceData = sentenceData


    presentAttributes = property(lambda self: iter(self._sentenceData))


    def __getattr__(self, name):
        """
        Gets an attribute of this sentence.
        """
        if name in self.ALLOWED_ATTRIBUTES:
            return self._sentenceData.get(name, None)
        else:
            className = self.__class__.__name__
            msg = "%s sentences have no %s attributes" % (className, name)
            raise AttributeError(msg)


    def __repr__(self):
        """
        Returns a textual representation of this sentence.

        @return: A textual representation of this sentence.
        @rtype: C{str}
        """
        items = self._sentenceData.items()
        data = ["%s: %s" % (k, v) for k, v in sorted(items) if k != "type"]
        dataRepr = ", ".join(data)

        typeRepr = self._sentenceData.get("type") or "unknown type"
        className = self.__class__.__name__

        return "<%s (%s) {%s}>" % (className, typeRepr, dataRepr)



class PositioningSentenceProducerMixin(object):
    """
    A mixin for certain protocols that produce positioning sentences.

    This mixin helps protocols that have C{SENTENCE_CONTENTS} class variables
    (such as the C{NMEAProtocol} and the C{ClassicGPSDProtocol}) implement the
    L{IPositioningSentenceProducingProtocol} interface.
    """
    #@classmethod
    def getSentenceAttributes(cls):
        """
        Returns a set of all attributes that might be found in the sentences
        produced by this protocol.

        This is basically a set of all the attributes of all the sentences that
        this protocol can produce.

        @return: The set of all possible sentence attribute names.
        @rtype: C{set} of C{str}
        """
        attributes = set(["type"])
        for attributeList in cls.SENTENCE_CONTENTS.values():
            for attribute in attributeList:
                if attribute is None:
                    continue
                attributes.add(attribute)

        return attributes


    getSentenceAttributes = classmethod(getSentenceAttributes)


    
class Angle(object, FancyEqMixin):
    """
    An object representing an angle.

    @ivar inDecimalDegrees: The value of this angle, expressed in decimal
        degrees. C{None} if unknown. This attribute is read-only.
    @type inDecimalDegrees: C{float} (or C{NoneType})
    @ivar inDegreesMinutesSeconds: The value of this angle, expressed in
        degrees, minutes and seconds. C{None} if unknown. This attribute is
        read-only.
    @type inDegreesMinutesSeconds: 3-C{tuple} of C{int} (or C{NoneType})

    @cvar RANGE_EXPRESSIONS: A collections of expressions for the allowable
        range for the angular value of a particular coordinate value.
    @type RANGE_EXPRESSIONS: A mapping of coordinate types (C{LATITUDE},
        C{LONGITUDE}, C{HEADING}, C{VARIATION}) to 1-argument callables.
    """
    RANGE_EXPRESSIONS = {
        LATITUDE: lambda latitude: -90.0 < latitude < 90.0,
        LONGITUDE: lambda longitude: -180.0 < longitude < 180.0,
        HEADING: lambda heading:  0 <= heading < 360,
        VARIATION: lambda variation: -180 < variation <= 180,
    }


    ANGLE_TYPE_NAMES  = {
        LATITUDE: "latitude",
        LONGITUDE: "longitude",
        VARIATION: "variation",
        HEADING: "heading",
    }


    compareAttributes = 'angleType', 'inDecimalDegrees'


    def __init__(self, angle=None, angleType=None):
        """
        Initializes an angle.

        @param angle: The value of the angle in decimal degrees. (C{None} if
            unknown).
        @type angle: C{float} or C{NoneType}
        @param angleType: A symbolic constant describing the angle type. Should
            be one of LATITUDE, LONGITUDE, HEADING, VARIATION. C{None} if
            unknown.

        @raises ValueError: If the angle type is not the default argument, but it
            is an unknown type (it's not present in C{Angle.RANGE_EXPRESSIONS}),
            or it is a known type but the supplied value was out of the allowable
            range for said type.
        """
        if angle is not None and angleType is not None:
            if angleType not in self.RANGE_EXPRESSIONS:
                raise ValueError("Unknown angle type")
            elif not self.RANGE_EXPRESSIONS[angleType](angle):
                raise ValueError("Angle %s not in allowed range for type %s"
                                 % (angle, self.ANGLE_TYPE_NAMES[angleType]))

        self.angleType = angleType
        self._angle = angle


    inDecimalDegrees = property(lambda self: self._angle)


    def _getDMS(self):
        """
        Gets the value of this angle as a degrees, minutes, seconds tuple.

        @return: This angle expressed in degrees, minutes, seconds. C{None} if
            the angle is unknown.
        @rtype: 3-C{tuple} of C{int} (or C{NoneType})
        """
        if self._angle is None:
            return None

        degrees = abs(int(self._angle))
        fractionalDegrees = abs(self._angle - int(self._angle))
        decimalMinutes = 60 * fractionalDegrees

        minutes = int(decimalMinutes)
        fractionalMinutes = decimalMinutes - int(decimalMinutes)
        decimalSeconds = 60 * fractionalMinutes

        return degrees, minutes, int(decimalSeconds)


    inDegreesMinutesSeconds = property(_getDMS)


    def setSign(self, sign):
        """
        Sets the sign of this angle.

        @param sign: The new sign. C{1} for positive and C{-1} for negative
            signs, respectively.
        @type sign: C{int}

        @raise ValueError: If the C{sign} parameter is not C{-1} or C{1}.
        """
        if sign not in (-1, 1):
            raise ValueError("bad sign (got %s, expected -1 or 1)" % sign)

        self._angle = sign * abs(self._angle)


    def __float__(self):
        """
        Returns this angle as a float.

        @return: The float value of this angle, expressed in degrees.
        @rtype: C{float}
        """
        return self._angle


    def __repr__(self):
        """
        Returns a string representation of this angle.

        @return: The string representation.
        @rtype: C{str}
        """
        return "<%s (%s)>" % (self._angleTypeNameRepr, self._angleValueRepr)


    def _getAngleValueRepr(self):
        """
        Returns a string representation of the angular value of this angle.

        This is a helper function for the actual C{__repr__}.

        @return: The string representation.
        @rtype: C{str}
        """
        if self.inDecimalDegrees is not None:
            return "%s degrees" % round(self.inDecimalDegrees, 2)
        else:
            return "unknown value"


    _angleValueRepr = property(_getAngleValueRepr)


    def _getAngleTypeNameRepr(self):
        """
        Returns a string representation of the type of this angle.

        This is a helper function for the actual C{__repr__}.

        @return: The string representation.
        @rtype: C{str}
        """
        angleTypeName = self.ANGLE_TYPE_NAMES.get(
            self.angleType, "angle of unknown type").capitalize()
        return angleTypeName


    _angleTypeNameRepr = property(_getAngleTypeNameRepr)



class Heading(Angle):
    """
    The heading of a mobile object.

    @ivar variation: The (optional) variation.
        The sign of the variation is positive for variations towards the east
        (clockwise from north), and negative for variations towards the west
        (counterclockwise from north).
        If the variation is unknown or not applicable, this is C{None}.
    @type variation: C{Angle} or C{NoneType}.
    @ivar correctedHeading: The heading, corrected for variation. If the
        variation is unknown (C{None}), is None. This attribute is read-only (its
        value is determined by the angle and variation attributes). The value is
        coerced to being between 0 (inclusive) and 360 (exclusive).
    """
    def __init__(self, angle=None, variation=None):
        """
        Initializes a angle with an optional variation.
        """
        Angle.__init__(self, angle, HEADING)
        self.variation = variation


    #@classmethod
    def fromFloats(cls, angleValue=None, variationValue=None):
        """
        Constructs a Heading from the float values of the angle and variation.

        @param angleValue: The angle value of this heading.
        @type angleValue: C{float}
        @param variationValue: The value of the variation of this heading.
        @type variationValue: C{float}
        """
        variation = Angle(variationValue, VARIATION)
        return cls(angleValue, variation)


    fromFloats = classmethod(fromFloats)


    def _getCorrectedHeading(self):
        """
        Corrects the heading by the given variation. This is sometimes known as
        the true heading.

        @return: The heading, corrected by the variation. If the variation or
            the angle are unknown, returns C{None}.
        @rtype: C{float} or C{NoneType}
        """
        if self._angle is None or self.variation is None:
            return None

        angle = (self.inDecimalDegrees - self.variation.inDecimalDegrees) % 360
        return Angle(angle, HEADING)


    correctedHeading = property(_getCorrectedHeading)


    def setSign(self, sign):
        """
        Sets the sign of the variation of this heading.

        @param sign: The new sign. C{1} for positive and C{-1} for negative
            signs, respectively.
        @type sign: C{int}

        @raise ValueErorr: If the C{sign} parameter is not C{-1} or C{1}.
        """
        if self.variation.inDecimalDegrees is None:
            raise ValueError("can't set the sign of an unknown variation")

        self.variation.setSign(sign)


    compareAttributes = list(Angle.compareAttributes) + ["variation"]


    def __repr__(self):
        """
        Returns a string representation of this angle.

        @return: The string representation.
        @rtype: C{str}
        """
        if self.variation is None:
            variationRepr = "unknown variation"
        else:
            variationRepr = repr(self.variation)

        return "<%s (%s, %s)>" % (
            self._angleTypeNameRepr, self._angleValueRepr, variationRepr)



class Coordinate(Angle, FancyEqMixin):
    """
    A coordinate.

    @ivar angle: The value of the coordinate in decimal degrees, with the usual
        rules for sign (northern and eastern hemispheres are positive, southern
        and western hemispheres are negative).
    @type angle: C{float}
    """
    def __init__(self, angle, coordinateType=None):
        """
        Initializes a coordinate.

        @param angle: The angle of this coordinate in decimal degrees. The
            hemisphere is determined by the sign (north and east are positive).
            If this coordinate describes a latitude, this value must be within
            -90.0 and +90.0 (exclusive). If this value describes a longitude,
            this value must be within -180.0 and +180.0 (exclusive).
        @type angle: C{float}
        @param coordinateType: One of L{LATITUDE}, L{LONGITUDE}. Used to return
            hemisphere names.
        """
        Angle.__init__(self, angle, coordinateType)


    HEMISPHERES_BY_TYPE_AND_SIGN = {
        LATITUDE: [
            NORTH, # positive
            SOUTH, # negative
        ],

        LONGITUDE: [
            EAST, # positve
            WEST, # negative
        ]
    }


    def _getHemisphere(self):
        """
        Gets the hemisphere of this coordinate.

        @return: A symbolic constant representing a hemisphere (C{NORTH},
            C{EAST}, C{SOUTH} or C{WEST}).
        """
        try:
            sign = int(self.inDecimalDegrees < 0)
            return self.HEMISPHERES_BY_TYPE_AND_SIGN[self.angleType][sign]
        except KeyError:
            raise ValueError("unknown coordinate type (cant find hemisphere)")


    hemisphere = property(fget=_getHemisphere)



class Altitude(object, FancyEqMixin):
    """
    An altitude.

    @ivar inMeters: The altitude represented by this object, in meters. This
        attribute is read-only.
    @type inMeters: C{float}

    @ivar inFeet: As above, but expressed in feet.
    @type inFeet: C{float}
    """
    compareAttributes = 'inMeters',

    def __init__(self, altitude):
        """
        Initializes an altitude.

        @param altitude: The altitude in meters.
        @type altitude: C{float}
        """
        self._altitude = altitude


    def _getAltitudeInFeet(self):
        """
        Gets the altitude this object represents, in feet.

        @return: The altitude, expressed in feet.
        @rtype: C{float}
        """
        return self._altitude / METERS_PER_FOOT


    inFeet = property(_getAltitudeInFeet)


    def _getAltitudeInMeters(self):
        """
        Returns the altitude this object represents, in meters.

        @return: The altitude, expressed in feet.
        @rtype: C{float}
        """
        return self._altitude


    inMeters = property(_getAltitudeInMeters)


    def __float__(self):
        """
        Returns the altitude represented by this object expressed in meters.

        @return: The altitude represented by this object, expressed in meters.
        @rtype: C{float}
        """
        return self._altitude


    def __repr__(self):
        """
        Returns a string representation of this altitude.

        @return: The string representation.
        @rtype: C{str}
        """
        return "<Altitude (%s m)>" % (self._altitude,)



class _BaseSpeed(object, FancyEqMixin):
    """
    An object representing the abstract concept of the speed (rate of
    movement) of a mobile object.

    This primarily has behavior for converting between units and comparison.

    @ivar inMetersPerSecond: The speed that this object represents, expressed
        in meters per second. This attribute is immutable.
    @type inMetersPerSecond: C{float}

    @ivar inKnots: Same as above, but expressed in knots.
    @type inKnots: C{float}
    """
    compareAttributes = 'inMetersPerSecond',

    def __init__(self, speed):
        """
        Initializes a speed.

        @param speed: The speed that this object represents, expressed in
            meters per second.
        @type speed: C{float}

        @raises ValueError: Raised if value was invalid for this particular
            kind of speed. Only happens in subclasses.
        """
        self._speed = speed


    def _getSpeedInKnots(self):
        """
        Returns the speed represented by this object, expressed in knots.

        @return: The speed this object represents, in knots.
        @rtype: C{float}
        """
        return self._speed / MPS_PER_KNOT


    inKnots = property(_getSpeedInKnots)


    inMetersPerSecond = property(lambda self: self._speed)


    def __float__(self):
        """
        Returns the speed represented by this object expressed in meters per
        second.

        @return: The speed represented by this object, expressed in meters per
            second.
        @rtype: C{float}
        """
        return self._speed


    def __repr__(self):
        """
        Returns a string representation of this speed object.

        @return: The string representation.
        @rtype: C{str}
        """
        speedValue = round(self.inMetersPerSecond, 2)
        return "<%s (%s m/s)>" % (self.__class__.__name__, speedValue)



class Speed(_BaseSpeed):
    """
    The speed (rate of movement) of a mobile object.
    """
    def __init__(self, speed):
        """
        Initializes a L{Speed} object.

        @param speed: The speed that this object represents, expressed in
            meters per second.
        @type speed: C{float}

        @raises ValueError: Raised if C{speed} is negative.
        """
        if speed < 0:
            raise ValueError("negative speed: %r" % (speed,))

        _BaseSpeed.__init__(self, speed)



class Climb(_BaseSpeed):
    """
    The climb ("vertical speed") of an object.
    """
    def __init__(self, climb):
        """
        Initializes a L{Clib} object.

        @param climb: The climb that this object represents, expressed in
            meters per second.
        @type climb: C{float}

        @raises ValueError: Raised if the provided climb was less than zero.
        """
        _BaseSpeed.__init__(self, climb)



class PositionError(object, FancyEqMixin):
    """
    Position error information.

    @ivar pdop: The position dilution of precision. C{None} if unknown.
    @type pdop: C{float} or C{NoneType}
    @ivar hdop: The horizontal dilution of precision. C{None} if unknown.
    @type hdop: C{float} or C{NoneType}
    @ivar vdop: The vertical dilution of precision. C{None} if unknown.
    @type vdop: C{float} or C{NoneType}
    """
    compareAttributes = 'pdop', 'hdop', 'vdop'

    def __init__(self, pdop=None, hdop=None, vdop=None, testInvariant=False):
        """
        Initializes a positioning error object.

        @param pdop: The position dilution of precision. C{None} if unknown.
        @type pdop: C{float} or C{NoneType}
        @param hdop: The horizontal dilution of precision. C{None} if unknown.
        @type hdop: C{float} or C{NoneType}
        @param vdop: The vertical dilution of precision. C{None} if unknown.
        @type vdop: C{float} or C{NoneType}
        @param testInvariant: Flag to test if the DOP invariant is valid or
            not. If C{True}, the invariant (PDOP = (HDOP**2 + VDOP**2)*.5) is
            checked at every mutation. By default, this is false, because the
            vast majority of DOP-providing devices ignore this invariant.
        @type testInvariant: c{bool}
        """
        self._pdop = pdop
        self._hdop = hdop
        self._vdop = vdop

        self._testInvariant = testInvariant
        self._testDilutionOfPositionInvariant()


    ALLOWABLE_TRESHOLD = 0.01


    def _testDilutionOfPositionInvariant(self):
        """
        Tests if this positioning error object satisfies the dilution of
        position invariant (PDOP = (HDOP**2 + VDOP**2)*.5), unless the
        C{self._testInvariant} instance variable is C{False}.

        @return: C{None} if the invariant was not satisifed or not tested.
        @raises ValueError: Raised if the invariant was tested but not
            satisfied.
        """
        if not self._testInvariant:
            return

        for x in (self.pdop, self.hdop, self.vdop):
            if x is None:
                return

        delta = abs(self.pdop - (self.hdop**2 + self.vdop**2)**.5)
        if delta > self.ALLOWABLE_TRESHOLD:
            raise ValueError("invalid combination of dilutions of precision: "
                             "position: %s, horizontal: %s, vertical: %s"
                             % (self.pdop, self.hdop, self.vdop))


    DOP_EXPRESSIONS = {
        'pdop': [
            lambda self: float(self._pdop),
            lambda self: (self._hdop**2 + self._vdop**2)**.5,
        ],

        'hdop': [
            lambda self: float(self._hdop),
            lambda self: (self._pdop**2 - self._vdop**2)**.5,
        ],

        'vdop': [
            lambda self: float(self._vdop),
            lambda self: (self._pdop**2 - self._hdop**2)**.5,
        ],
    }


    def _getDOP(self, dopType):
        """
        Gets a particular dilution of position value.

        @return: The DOP if it is known, C{None} otherwise.
        @rtype: C{float} or C{NoneType}
        """
        for dopExpression in self.DOP_EXPRESSIONS[dopType]:
            try:
                return dopExpression(self)
            except TypeError:
                continue


    def _setDOP(self, dopType, value):
        """
        Sets a particular dilution of position value.

        @param dopType: The type of dilution of position to set. One of
            ('pdop', 'hdop', 'vdop').
        @type dopType: C{str}

        @param value: The value to set the dilution of position type to.
        @type value: C{float}

        If this position error tests dilution of precision invariants,
        it will be checked. If the invariant is not satisfied, the
        assignment will be undone and C{ValueError} is raised.
        """
        attributeName = "_" + dopType

        oldValue = getattr(self, attributeName)
        setattr(self, attributeName, float(value))

        try:
            self._testDilutionOfPositionInvariant()
        except ValueError:
            setattr(self, attributeName, oldValue)
            raise


    pdop = property(fget=lambda self: self._getDOP('pdop'),
                    fset=lambda self, value: self._setDOP('pdop', value))


    hdop = property(fget=lambda self: self._getDOP('hdop'),
                    fset=lambda self, value: self._setDOP('hdop', value))


    vdop = property(fget=lambda self: self._getDOP('vdop'),
                    fset=lambda self, value: self._setDOP('vdop', value))


    _REPR_TEMPLATE = "<PositionError (pdop: %s, hdop: %s, vdop: %s)>"


    def __repr__(self):
        """
        Returns a string representation of positioning information object.

        @return: The string representation.
        @rtype: C{str}
        """
        return self._REPR_TEMPLATE % (self.pdop, self.hdop, self.vdop)



class BeaconInformation(object):
    """
    Information about positioning beacons (a generalized term for the reference
    objects that help you determine your position, such as satellites or cell
    towers).

    @ivar beacons: A set of visible beacons. Note that visible beacons are not
        necessarily used in acquiring a postioning fix.
    @type beacons: C{set} of L{IPositioningBeacon}

    @ivar usedBeacons: An iterable of the beacons that were used in obtaining a
        positioning fix. This only contains beacons that are actually used, not
        beacons of which it is  unknown if they are used or not. This attribute
        is immutable.
    @type usedBeacons: iterable of L{IPositioningBeacon}

    @ivar seen: The amount of beacons that can be seen. This attribute is
        immutable.
    @type seen: C{int}
    @ivar used: The amount of beacons that were used in obtaining the
        positioning fix. This attribute is immutable.
    @type used: C{int}
    """
    def __init__(self, beacons=None):
        """
        Initializes a beacon information object.

        @param beacons: A collection of beacons that will be present in this
            beacon information object.
        @type beacons: iterable of L{IPositioningBeacon} or C{Nonetype}
        """
        self.beacons = set(beacons or [])


    def _getUsedBeacons(self):
        """
        Returns a generator of used beacons.

        @return: A generator containing all of the used positioning beacons. This
            only contains beacons that are actually used, not beacons of which it
            is  unknown if they are used or not.
        @rtype: iterable of L{PositioningBeacon}
        """
        for beacon in self.beacons:
            if beacon.isUsed:
                yield beacon


    usedBeacons = property(fget=_getUsedBeacons)


    def _getNumberOfBeaconsSeen(self):
        """
        Returns the number of beacons that can be seen.

        @return: The number of beacons that can be seen.
        @rtype: C{int}
        """
        return len(self.beacons)


    seen = property(_getNumberOfBeaconsSeen)


    def _getNumberOfBeaconsUsed(self):
        """
        Returns the number of beacons that can be seen.

        @return: The number of beacons that can be seen, or C{None} if the number
            is unknown. This happens as soon as one of the beacons has an unknown
            (C{None}) C{isUsed} attribute.
        @rtype: C{int} or C{NoneType}
        """
        numberOfUsedBeacons = 0
        for beacon in self.beacons:
            if beacon.isUsed is None:
                return None
            elif beacon.isUsed:
                numberOfUsedBeacons += 1
        return numberOfUsedBeacons


    used = property(_getNumberOfBeaconsUsed)


    def __iter__(self):
        """
        Yields the beacons in this beacon information object.

        @return: A generator producing the beacons in this beacon information
            object.
        @rtype: iterable of L{PositioningBeacon}
        """
        for beacon in self.beacons:
            yield beacon


    def __repr__(self):
        """
        Returns a string representation of this beacon information object.

        The beacons are sorted by their identifier.

        @return: The string representation.
        @rtype: C{str}
        """
        beaconReprs = ", ".join([repr(beacon) for beacon in
            sorted(self.beacons, key=lambda x: x.identifier)])

        if self.used is not None:
            used = str(self.used)
        else:
            used = "?"

        return "<BeaconInformation (seen: %s, used: %s, beacons: {%s})>" % (
            self.seen, used, beaconReprs)



class PositioningBeacon(object):
    """
    A positioning beacon.

    @ivar identifier: The unqiue identifier for this satellite. This is usually
        an integer. For GPS, this is also known as the PRN.
    @type identifier: Pretty much anything that can be used as a unique
        identifier. Depends on the implementation.
    @ivar isUsed: C{True} if the satellite is currently being used to obtain a
        fix, C{False} if it is not currently being used, C{None} if unknown.
    @type isUsed: C{bool} or C{NoneType}
    """
    def __init__(self, identifier, isUsed=None):
        """
        Initializes a positioning beacon.

        @param identifier: The identifier for this beacon.
        @type identifier: Can be pretty much anything (see ivar documentation).
        @param isUsed: Determines if this beacon is used in obtaining a
            positioning fix (see the ivar documentation).
        @type isUsed: C{bool} or C{NoneType}
        """
        self.identifier = identifier
        self.isUsed = isUsed


    def __hash__(self):
        """
        Returns the hash of the identifier for this beacon.

        @return: The hash of the identifier. (C{hash(self.identifier)})
        @rtype: C{int}
        """
        return hash(self.identifier)


    def _usedRepr(self):
        """
        Returns a single character representation of the status of this
        satellite in terms of being used for attaining a positioning fix.

        @return: One of ("Y", "N", "?") depending on the status of the
            satellite.
        @rtype: C{str}
        """
        return {True: "Y", False: "N", None: "?"}[self.isUsed]


    def __repr__(self):
        """
        Returns a string representation of this beacon.

        @return: The string representation.
        @rtype: C{str}
        """
        return "<Beacon (identifier: %s, used: %s)>" \
            % (self.identifier, self._usedRepr())



class Satellite(PositioningBeacon):
    """
    A satellite.

    @ivar azimuth: The azimuth of the satellite. This is the heading (positive
        angle relative to true north) where the satellite appears to be to the
        device.
    @ivar elevation: The (positive) angle above the horizon where this
        satellite appears to be to the device.
    @ivar signalToNoiseRatio: The signal to noise ratio of the signal coming
        from this satellite.
    """
    def __init__(self,
                 identifier,
                 azimuth=None,
                 elevation=None,
                 signalToNoiseRatio=None,
                 isUsed=None):
        """
        Initializes a satellite object.

        @param identifier: The PRN (unique identifier) of this satellite.
        @type identifier: C{int}
        @param azimuth: The azimuth of the satellite (see instance variable
            documentation).
        @type azimuth: C{float}
        @param elevation: The elevation of the satellite (see instance variable
            documentation).
        @type elevation: C{float}
        @param signalToNoiseRatio: The signal to noise ratio of the connection
            to this satellite (see instance variable documentation).
        @type signalToNoiseRatio: C{float}

        """
        super(Satellite, self).__init__(int(identifier), isUsed)

        self.azimuth = azimuth
        self.elevation = elevation
        self.signalToNoiseRatio = signalToNoiseRatio


    def __repr__(self):
        """
        Returns a string representation of this Satellite.

        @return: The string representation.
        @rtype: C{str}
        """
        azimuth, elevation, snr = [{None: "?"}.get(x, x)
            for x in self.azimuth, self.elevation, self.signalToNoiseRatio]

        properties = "azimuth: %s, elevation: %s, snr: %s" % (
            azimuth, elevation, snr)

        return "<Satellite (%s), %s, used: %s>" % (
            self.identifier, properties, self._usedRepr())
