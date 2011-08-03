# -*- test-case-name: twisted.positioning.test.test_nmea -*-
# Copyright (c) 2009-2011 Twisted Matrix Laboratories.
# See LICENSE for details.
"""
Classes for working with NMEA (and vaguely NMEA-like) sentence producing
devices.

@since: 11.1
"""

import itertools
import operator
import datetime
from zope.interface import implements, classProvides

from twisted.protocols.basic import LineReceiver
from twisted.positioning import base, ipositioning
from twisted.positioning.base import LATITUDE, LONGITUDE, VARIATION

# GPGGA fix quality:
(GGA_INVALID_FIX, GGA_GPS_FIX, GGA_DGPS_FIX, GGA_PPS_FIX, GGA_RTK_FIX,
 GGA_FLOAT_RTK_FIX, GGA_DEAD_RECKONING, GGA_MANUAL_FIX, GGA_SIMULATED_FIX
 ) = [str(x) for x in range(9)]

# GPGLL/GPRMC fix quality:
DATA_ACTIVE, DATA_VOID = "A", "V"

# Selection modes (used in a variety of sentences):
MODE_AUTO, MODE_MANUAL = 'A', 'M'

# GPGSA fix types:
GSA_NO_FIX, GSA_2D_FIX, GSA_3D_FIX = '1', '2', '3'

NMEA_NORTH, NMEA_EAST, NMEA_SOUTH, NMEA_WEST = "N", "E", "S", "W"


def split(sentence):
    """
    Returns the split version of an NMEA sentence, minus header
    and checksum.

    @param sentence: The NMEA sentence to split.
    @type sentence: C{str}

    >>> split("$GPGGA,spam,eggs*00")
    ['GPGGA', 'spam', 'eggs']
    """
    if sentence[-3] == "*": # sentence with checksum
        return sentence[1:-3].split(',')
    elif sentence[-1] == "*": # sentence without checksum
        return sentence[1:-1].split(',')
    else:
        raise base.InvalidSentence("malformed sentence %s" % sentence)


def validateChecksum(sentence):
    """
    Validates the checksum of an NMEA sentence.

    @param sentence: The NMEA sentence to check the checksum of.
    @type sentence: C{str}

    @raise ValueError: If the sentence has an invalid checksum.

    Simply returns on sentences that either don't have a checksum,
    or have a valid checksum.
    """
    if sentence[-3] == '*': # sentence has a checksum
        reference, source = int(sentence[-2:], 16), sentence[1:-3]
        computed = reduce(operator.xor, (ord(x) for x in source))
        if computed != reference:
            raise base.InvalidChecksum("%02x != %02x" % (computed, reference))



class NMEAProtocol(LineReceiver, base.PositioningSentenceProducerMixin):
    """
    A protocol that parses and verifies the checksum of an NMEA sentence (in
    string form, not L{NMEASentence}), and delegates to a receiver.

    It receives lines and verifies these lines are NMEA sentences. If
    they are, verifies their checksum and unpacks them into their
    components. It then wraps them in L{NMEASentence} objects and
    calls the appropriate receiver method with them.
    """
    classProvides(ipositioning.IPositioningSentenceProducer)
    METHOD_PREFIX = "nmea_"

    def __init__(self, receiver):
        """
        Initializes an NMEAProtocol.

        @param receiver: A receiver for NMEAProtocol sentence objects.
        @type receiver: L{INMEAReceiver}
        """
        self.receiver = receiver


    def lineReceived(self, rawSentence):
        """
        Parses the data from the sentence and validates the checksum.

        @param rawSentence: The MMEA positioning sentence.
        @type rawSentence: C{str}
        """
        sentence = rawSentence.strip()

        validateChecksum(sentence)
        splitSentence = split(sentence)

        sentenceType, contents = splitSentence[0], splitSentence[1:]

        try:
            keys = self.SENTENCE_CONTENTS[sentenceType]
        except KeyError:
            raise ValueError("unknown sentence type %s" % sentenceType)

        sentenceData = {"type": sentenceType}
        for key, value in itertools.izip(keys, contents):
            if key is not None and value != "":
                sentenceData[key] = value

        sentence = NMEASentence(sentenceData)

        try:
            callback = getattr(self, self.METHOD_PREFIX + sentenceType)
            callback(sentence)
        except AttributeError:
            pass # No sentence-specific callback on the protocol

        if self.receiver is not None:
            self.receiver.sentenceReceived(sentence)


    SENTENCE_CONTENTS = {
        'GPGGA': [
            'timestamp',

            'latitudeFloat',
            'latitudeHemisphere',
            'longitudeFloat',
            'longitudeHemisphere',

            'fixQuality',
            'numberOfSatellitesSeen',
            'horizontalDilutionOfPrecision',

            'altitude',
            'altitudeUnits',
            'heightOfGeoidAboveWGS84',
            'heightOfGeoidAboveWGS84Units',

            # The next parts are DGPS information.
        ],

        'GPRMC': [
            'timestamp',

            'dataMode',

            'latitudeFloat',
            'latitudeHemisphere',
            'longitudeFloat',
            'longitudeHemisphere',

            'speedInKnots',

            'trueHeading',

            'datestamp',

            'magneticVariation',
            'magneticVariationDirection',
        ],

        'GPGSV': [
            'numberOfGSVSentences',
            'GSVSentenceIndex',

            'numberOfSatellitesSeen',

            'satellitePRN_0',
            'elevation_0',
            'azimuth_0',
            'signalToNoiseRatio_0',

            'satellitePRN_1',
            'elevation_1',
            'azimuth_1',
            'signalToNoiseRatio_1',

            'satellitePRN_2',
            'elevation_2',
            'azimuth_2',
            'signalToNoiseRatio_2',

            'satellitePRN_3',
            'elevation_3',
            'azimuth_3',
            'signalToNoiseRatio_3',
        ],

        'GPGLL': [
            'latitudeFloat',
            'latitudeHemisphere',
            'longitudeFloat',
            'longitudeHemisphere',
            'timestamp',
            'dataMode',
        ],

        'GPHDT': [
            'trueHeading',
        ],

        'GPTRF': [
            'datestamp',
            'timestamp',

            'latitudeFloat',
            'latitudeHemisphere',
            'longitudeFloat',
            'longitudeHemisphere',

            'elevation',
            'numberOfIterations', # unused
            'numberOfDopplerIntervals', # unused 
            'updateDistanceInNauticalMiles', # unused
            'satellitePRN',
        ],

        'GPGSA': [
            'dataMode',
            'fixType',

            'usedSatellitePRN_0',
            'usedSatellitePRN_1',
            'usedSatellitePRN_2',
            'usedSatellitePRN_3',
            'usedSatellitePRN_4',
            'usedSatellitePRN_5',
            'usedSatellitePRN_6',
            'usedSatellitePRN_7',
            'usedSatellitePRN_8',
            'usedSatellitePRN_9',
            'usedSatellitePRN_10',
            'usedSatellitePRN_11',

            'positionDilutionOfPrecision',
            'horizontalDilutionOfPrecision',
            'verticalDilutionOfPrecision',
        ]
    }


class NMEASentence(base.BaseSentence):
    """
    An object representing an NMEA sentence.

    The attributes of this objects are raw NMEA protocol data, which
    are all ASCII bytestrings.

    This object contains all the raw NMEA protocol data in a single
    sentence.  Not all of these necessarily have to be present in the
    sentence. Missing attributes are None when accessed.

    Sentence-specific junk:

    @ivar type: The sentence type ("GPGGA", "GPGSV"...).
    @ivar numberOfGSVSentences: The total number of GSV sentences in a
        sequence.
    @ivar GSVSentenceIndex: The index of this GSV sentence in the GSV
        sequence.

    Time-related attributes:

    @ivar timestamp: A timestamp. ("123456" -> 12:34:56Z)
    @ivar datestamp: A datestamp. ("230394" -> 23 Mar 1994)

    Location-related attributes:

    @ivar latitudeFloat: Latitude value. (for example: "1234.567" ->
        12 degrees, 34.567 minutes).
    @ivar latitudeHemisphere: Latitudinal hemisphere ("N" or "S").
    @ivar longitudeFloat: Longitude value. See C{latitudeFloat} for an
        example.
    @ivar longitudeHemisphere: Longitudinal hemisphere ("E" or "W").
    @ivar altitude: The altitude above mean sea level.
    @ivar altitudeUnits: Units in which altitude is expressed. (Always
        "M" for meters.)
    @ivar heightOfGeoidAboveWGS84: The local height of the geoid above
        the WGS84 ellipsoid model.
    @ivar heightOfGeoidAboveWGS84Units: The units in which the height
        above the geoid is expressed. (Always "M" for meters.)

    Attributes related to direction and movement:

    @ivar trueHeading: The true heading.
    @ivar magneticVariation: The magnetic variation.
    @ivar magneticVariationDirection: The direction of the magnetic
        variation. One of C{"E"} or C{"W"}.
    @ivar speedInKnots: The ground speed, expressed in knots.

    Attributes related to fix and data quality:

    @ivar fixQuality: The quality of the fix. This is a single digit
        from C{"0"} to C{"8"}. The important ones are C{"0"} (invalid
        fix), C{"1"} (GPS fix) and C{"2"} (DGPS fix).
    @ivar dataMode: Signals if the data is usable or not. One of
        L{DATA_ACTIVE} or L{DATA_VOID}.
    @ivar numberOfSatellitesSeen: The number of satellites seen by the
        receiver.
    @ivar numberOfSatellitesUsed: The number of satellites used in
        computing the fix.

    Attributes related to precision:

    @ivar horizontalDilutionOfPrecision: The dilution of the precision of the
        position on a plane tangential to the geoid. (HDOP)
    @ivar verticalDilutionOfPrecision: As C{horizontalDilutionOfPrecision},
        but for a position on a plane perpendicular to the geoid. (VDOP)
    @ivar positionDilutionOfPrecision: Euclidian norm of HDOP and VDOP.

    Attributes related to satellite-specific data:

    @ivar C{satellitePRN}: The unique identifcation number of a particular
        satelite. Optionally suffixed with C{_N} if multiple satellites are
        referenced in a sentence, where C{N in range(4)}.
    @ivar C{elevation}: The elevation of a satellite in decimal degrees.
        Optionally suffixed with C{_N}, as with C{satellitePRN}.
    @ivar C{azimuth}: The azimuth of a satellite in decimal degrees.
        Optionally suffixed with C{_N}, as with C{satellitePRN}.
    @ivar C{signalToNoiseRatio}: The SNR of a satellite signal, in decibels.
        Optionally suffixed with C{_N}, as with C{satellitePRN}.
    @ivar C{usedSatellitePRN_N}: Where C{int(N) in range(12)}. The PRN
        of a satelite used in computing the fix.

    """
    ALLOWED_ATTRIBUTES = NMEAProtocol.getSentenceAttributes()
    
    def _isFirstGSVSentence(self):
        """
        Tests if this current GSV sentence is the first one in a sequence.
        """
        return self.GSVSentenceIndex == "1"


    def _isLastGSVSentence(self):
        """
        Tests if this current GSV sentence is the final one in a sequence.
        """
        return self.GSVSentenceIndex == self.numberOfGSVSentences



class NMEAAdapter(object):
    """
    An adapter from NMEAProtocol receivers to positioning receivers.

    @cvar DATESTAMP_HANDLING: Determines the way incomplete (two-digit) NMEA
        datestamps are handled.. One of L{INTELLIGENT_DATESTAMPS} (default,
        assumes dates are twenty-first century if the two-digit date is below
        the L{INTELLIGENT_DATE_THRESHOLD}, twentieth century otherwise),
        L{DATESTAMPS_FROM_20XX} (assumes all dates are twenty-first century),
        L{DATESTAMPS_FROM_19XX} (assumes all dates are twentieth century).
        All of these are class attributes of this class.

    @cvar INTELLIGENT_DATE_THRESHOLD: The threshold that determines which
        century we guess a year is in. If the year value in a sentence is above
        this value, assumes the 20th century (19xx), otherwise assumes the
        twenty-first century (20xx).
    @type INTELLIGENT_DATE_THRESHOLD: L{int}
    """
    implements(ipositioning.INMEAReceiver)


    def __init__(self, receiver):
        """
        Initializes a new NMEA adapter.

        @param receiver: The receiver for positioning sentences.
        @type receiver: L{twisted.positioning.IPositioningReceiver}
        """
        self._state = {}
        self._sentenceData = {}
        self._receiver = receiver


    def _fixTimestamp(self):
        """
        Turns the NMEAProtocol timestamp notation into a datetime.time object.
        The time in this object is expressed as Zulu time.
        """
        timestamp = self.currentSentence.timestamp.split('.')[0]
        timeObject = datetime.datetime.strptime(timestamp, '%H%M%S').time()
        self._sentenceData['_time'] = timeObject


    INTELLIGENT_DATESTAMPS = 0
    DATESTAMPS_FROM_20XX = 1
    DATESTAMPS_FROM_19XX = 2

    DATESTAMP_HANDLING = INTELLIGENT_DATESTAMPS
    INTELLIGENT_DATE_THRESHOLD = 80


    def _fixDatestamp(self):
        """
        Turns an NMEA datestamp format into a C{datetime.date} object.
        """
        datestamp = self.currentSentence.datestamp

        day, month, year = [int(ordinalString) for ordinalString in
                            (datestamp[0:2], datestamp[2:4], datestamp[4:6])]

        if self.DATESTAMP_HANDLING == self.INTELLIGENT_DATESTAMPS:
            if year > self.INTELLIGENT_DATE_THRESHOLD:
                year = int('19%02d' % year)
            else:
                year = int('20%02d' % year)

        elif self.DATESTAMP_HANDLING == self.DATESTAMPS_FROM_20XX:
            year = int('20%02d' % year)

        elif self.DATESTAMP_HANDLING == self.DATESTAMPS_FROM_19XX:
            year = int('19%02d' % year)

        else:
            raise ValueError("unknown datestamp handling method (%s)"
                             % (self.DATESTAMP_HANDLING,))

        self._sentenceData['_date'] = datetime.date(year, month, day)


    def _fixCoordinateFloat(self, coordinateType):
        """
        Turns the NMEAProtocol coordinate format into Python float.

        @param coordinateType: The coordinate type. Should be L{base.LATITUDE}
            or L{base.LONGITUDE}.
        """
        coordinateName = base.Coordinate.ANGLE_TYPE_NAMES[coordinateType]
        key = coordinateName + 'Float'
        nmeaCoordinate = getattr(self.currentSentence, key)

        left, right = nmeaCoordinate.split('.')

        degrees, minutes = int(left[:-2]), float("%s.%s" % (left[-2:], right))
        angle = degrees + minutes/60
        coordinate = base.Coordinate(angle, coordinateType)
        self._sentenceData[coordinateName] = coordinate


    def _fixHemisphereSign(self, coordinateType, sentenceDataKey=None):
        """
        Fixes the sign for a hemisphere.

        This method must be called after the magnitude for the thing it
        determines the sign of has been set. This is done by the following
        functions:

            - C{self.FIXERS['magneticVariation']}
            - C{self.FIXERS['latitudeFloat']}
            - C{self.FIXERS['longitudeFloat']}

        @param coordinateType: Coordinate type. One of L{base.LATITUDE},
            L{base.LONGITUDE} or L{base.VARIATION}.
        """
        sentenceDataKey = sentenceDataKey or coordinateType
        sign = self._getHemisphereSign(coordinateType)
        self._sentenceData[sentenceDataKey].setSign(sign)


    COORDINATE_SIGNS = {
        NMEA_NORTH: 1,
        NMEA_EAST: 1,
        NMEA_SOUTH: -1,
        NMEA_WEST: -1
    }


    def _getHemisphereSign(self, coordinateType):
        """
        Returns the hemisphere sign for a given coordinate type.

        @param coordinateType: Coordinate type. One of L{base.LATITUDE},
            L{base.LONGITUDE} or L{base.VARIATION}.
        """
        if coordinateType in (LATITUDE, LONGITUDE):
            hemisphereKey = (base.Coordinate.ANGLE_TYPE_NAMES[coordinateType]
                             + 'Hemisphere')
        elif coordinateType == VARIATION:
            hemisphereKey = 'magneticVariationDirection'
        else:
            raise ValueError("unknown coordinate type %s" % (coordinateType,))

        hemisphere = getattr(self.currentSentence, hemisphereKey)

        try: 
           return self.COORDINATE_SIGNS[hemisphere.upper()]
        except KeyError:
            raise ValueError("bad hemisphere/direction: %s" % hemisphere)


    def _convert(self, sourceKey, converter=float, destinationKey=None):
        """
        A simple conversion fix.

        @param sourceKey: The attribute name of the value to fix.
        @type sourceKey: C{str} (Python identifier)

        @param converter: The function that converts the value.
        @type converter: unary callable

        @param destinationKey: The target attribute key. If unset or
            C{None}, same as C{sourceKey}.
        @type destinationKey: C{str} (Python identifier)
        """
        currentValue = getattr(self.currentSentence, sourceKey)

        if destinationKey is None:
            destinationKey = sourceKey

        self._sentenceData[destinationKey] = converter(currentValue)



    STATEFUL_UPDATE = {
        # sentenceKey: (stateKey, factory, attributeName, converter),
        'trueHeading':
            ('heading', base.Heading, '_angle', float),
        'magneticVariation':
            ('heading', base.Heading, 'variation',
             lambda angle: base.Angle(float(angle), VARIATION)),

        'horizontalDilutionOfPrecision':
            ('positionError', base.PositionError, 'hdop', float),
        'verticalDilutionOfPrecision':
            ('positionError', base.PositionError, 'vdop', float),
        'positionDilutionOfPrecision':
            ('positionError', base.PositionError, 'pdop', float),

    }


    def _statefulUpdate(self, sentenceKey):
        """
        Does a stateful update of a particular positioning attribute.

        @param sentenceKey: The name of the key in the sentence attributes,
            C{NMEAAdapter.STATEFUL_UPDATE} dictionary and the adapter state.
        @type sentenceKey: C{str}
        """
        state, factory, attr, converter = self.STATEFUL_UPDATE[sentenceKey]

        if state not in self._sentenceData:
            self._sentenceData[state] = self._state.get(state, factory())

        newValue = converter(getattr(self.currentSentence, sentenceKey))
        setattr(self._sentenceData[state], attr, newValue)


    ACCEPTABLE_UNITS = frozenset(['M'])
    UNIT_CONVERTERS = {
        'N': lambda inKnots: base.Speed(float(inKnots) * base.MPS_PER_KNOT),
        'K': lambda inKPH: base.Speed(float(inKPH) * base.MPS_PER_KPH),
    }


    def _fixUnits(self, unitKey=None, valueKey=None, sourceKey=None, unit=None):
        """
        Fixes the units of a certain value.

        @param unit: The unit that is being converted I{from}. If unspecified
            or None, asks the current sentence for the C{unitKey}. If that also
            fails, raises C{AttributeError}.
        @type unit: C{str}
        @param unitKey: The name of the key/attribute under which the unit can
            be found in the current sentence. If the C{unit} parameter is set,
            this parameter is not used.
        @type unitKey: C{str}
        @param sourceKey: The name of the key/attribute that contains the
            current value to be converted (expressed in units as defined
            according to the the C{unit} parameter). If unset, will use the
            same key as the value key.
        @type sourceKey: C{str}
        @param valueKey: The key name in which the data will be stored in the
            C{_sentenceData} instance attribute. If unset, attempts to strip
            "Units" from the C{unitKey} parameter.
        @type valueKey: C{str}

        None of the keys are allowed to be the empty string.
        """
        unit = unit or getattr(self.currentSentence, unitKey)
        valueKey = valueKey or unitKey.strip('Units')
        sourceKey = sourceKey or valueKey

        if unit not in self.ACCEPTABLE_UNITS:
            converter = self.UNIT_CONVERTERS[unit]
            currentValue = getattr(self.currentSentence, sourceKey)
            self._sentenceData[valueKey] = converter(currentValue)


    GSV_KEYS = "satellitePRN", "azimuth", "elevation", "signalToNoiseRatio"


    def _fixGSV(self):
        """
        Parses partial visible satellite information from a GSV sentence.
        """
        # To anyone who knows NMEA, this method's name should raise a chuckle's
        # worth of schadenfreude. 'Fix' GSV? Hah! Ludicrous.
        self._sentenceData['_partialBeaconInformation'] = base.BeaconInformation()

        for index in range(4):
            keys = ["%s_%i" % (key, index) for key in self.GSV_KEYS]
            values = [getattr(self.currentSentence, k) for k in keys]
            prn, azimuth, elevation, snr = values

            if prn is None or snr is None:
                # The peephole optimizer optimizes the jump away, meaning that
                # coverage.py isn't covered. It is. Replace it with break and
                # watch the test case fail.
                # ML thread about this issue: http://goo.gl/1KNUi
                # Related CPython bug: http://bugs.python.org/issue2506
                continue # pragma: no cover

            satellite = base.Satellite(prn, azimuth, elevation, snr)
            bi = self._sentenceData['_partialBeaconInformation']
            bi.beacons.add(satellite)


    def _fixGSA(self):
        """
        Extracts the information regarding which satellites were used in
        obtaining the GPS fix from a GSA sentence.

        @precondition: A GSA sentence was fired.
        @postcondition: The current sentence data (C{self._sentenceData} will
            contain a set of the currently used PRNs (under the key
            C{_usedPRNs}.
        """
        self._sentenceData['_usedPRNs'] = set()
        for key in ("usedSatellitePRN_%d" % x for x in range(12)):
            prn = getattr(self.currentSentence, key, None)
            if prn is not None:
                self._sentenceData['_usedPRNs'].add(int(prn))


    SPECIFIC_SENTENCE_FIXES = {
        'GPGSV': _fixGSV,
        'GPGSA': _fixGSA,
    }


    def _sentenceSpecificFix(self):
        """
        Executes a fix for a specific type of sentence.
        """
        fixer = self.SPECIFIC_SENTENCE_FIXES.get(self.currentSentence.type)
        if fixer is not None:
            fixer(self)


    FIXERS = {
        'type':
            lambda self: self._sentenceSpecificFix(),

        'timestamp':
            lambda self: self._fixTimestamp(),
        'datestamp':
            lambda self: self._fixDatestamp(),

        'latitudeFloat':
            lambda self: self._fixCoordinateFloat(LATITUDE),
        'latitudeHemisphere':
            lambda self: self._fixHemisphereSign(LATITUDE, 'latitude'),
        'longitudeFloat':
            lambda self: self._fixCoordinateFloat(LONGITUDE),
        'longitudeHemisphere':
            lambda self: self._fixHemisphereSign(LONGITUDE, 'longitude'),

        'altitude':
            lambda self: self._convert('altitude',
                converter=lambda strRepr: base.Altitude(float(strRepr))),
        'altitudeUnits':
            lambda self: self._fixUnits(unitKey='altitudeUnits'),

        'heightOfGeoidAboveWGS84':
            lambda self: self._convert('heightOfGeoidAboveWGS84',
                converter=lambda strRepr: base.Altitude(float(strRepr))),
        'heightOfGeoidAboveWGS84Units':
            lambda self: self._fixUnits(
                unitKey='heightOfGeoidAboveWGS84Units'),

        'trueHeading':
            lambda self: self._statefulUpdate('trueHeading'),
        'magneticVariation':
            lambda self: self._statefulUpdate('magneticVariation'),

        'magneticVariationDirection':
            lambda self: self._fixHemisphereSign(VARIATION,
                                                 'heading'),

        'speedInKnots':
            lambda self: self._fixUnits(valueKey='speed',
                                        sourceKey='speedInKnots',
                                        unit='N'),

        'positionDilutionOfPrecision':
            lambda self: self._statefulUpdate('positionDilutionOfPrecision'),
        'horizontalDilutionOfPrecision':
            lambda self: self._statefulUpdate('horizontalDilutionOfPrecision'),
        'verticalDilutionOfPrecision':
            lambda self: self._statefulUpdate('verticalDilutionOfPrecision'),
    }


    def clear(self):
        """
        Resets this adapter.

        This will empty the adapter state and the current sentence data.
        """
        self._state = {}
        self._sentenceData = {}


    def sentenceReceived(self, sentence):
        """
        Called when a sentence is received.

        Will clean the received NMEAProtocol sentence up, and then update the
        adapter's state, followed by firing the callbacks.

        If the received sentence was invalid, the state will be cleared.

        @param sentence: The sentence that is received.
        @type sentence: L{NMEASentence}
        """
        self.currentSentence = sentence

        try:
            self._validateCurrentSentence()
            self._cleanCurrentSentence()
        except base.InvalidSentence:
            self.clear()

        self._updateSentence()
        self._fireSentenceCallbacks()


    def _validateCurrentSentence(self):
        """
        Tests if a sentence contains a valid fix.
        """
        if (self.currentSentence.fixQuality == GGA_INVALID_FIX
            or self.currentSentence.dataMode == DATA_VOID
            or self.currentSentence.fixType == GSA_NO_FIX):
            raise base.InvalidSentence("bad sentence")


    def _cleanCurrentSentence(self):
        """
        Cleans the current sentence.
        """
        for key in sorted(self.currentSentence.presentAttributes):
            fixer = self.FIXERS.get(key, None)

            if fixer is not None:
                fixer(self)


    def _updateSentence(self):
        """
        Updates the current state with the new information from the sentence.
        """
        self._updateBeaconInformation()
        self._combineDateAndTime()
        self._state.update(self._sentenceData)


    def _updateBeaconInformation(self):
        """
        Updates existing beacon information state with new data.
        """
        new = self._sentenceData.get('_partialBeaconInformation')
        if new is None:
            return

        usedPRNs = (self._state.get('_usedPRNs')
                    or self._sentenceData.get('_usedPRNs'))
        if usedPRNs is not None:
            for beacon in new.beacons:
                beacon.isUsed = (beacon.identifier in usedPRNs)

        old = self._state.get('_partialBeaconInformation')
        if old is not None:
            new.beacons.update(old.beacons)

        if self.currentSentence._isLastGSVSentence():
            if not self.currentSentence._isFirstGSVSentence():
                # not a 1-sentence sequence, get rid of partial information
                del self._state['_partialBeaconInformation']
            bi = self._sentenceData.pop('_partialBeaconInformation')
            self._sentenceData['beaconInformation'] = bi


    def _combineDateAndTime(self):
        """
        Combines a C{datetime.date} object and a C{datetime.time} object,
        collected from one or more NMEA sentences, into a single
        C{datetime.datetime} object suitable for sending to the
        L{IPositioningReceiver}.
        """
        if not ('_date' in self._sentenceData or '_time' in self._sentenceData):
            return

        date, time = [self._sentenceData.get(key) or self._state.get(key)
                      for key in ('_date', '_time')]

        if date is None or time is None:
            return

        dt = datetime.datetime.combine(date, time)
        self._sentenceData['time'] = dt


    def _fireSentenceCallbacks(self):
        """
        Fires sentence callbacks for the current sentence.

        A callback will only fire if all of the keys it requires are present in
        the current state and at least one such field was altered in the
        current sentence.

        The callbacks will only be fired with data from L{self._state}.
        """
        for callbackName, requiredFields in self.REQUIRED_CALLBACK_FIELDS.items():
            callback = getattr(self._receiver, callbackName)

            kwargs = {}
            atLeastOnePresentInSentence = False

            try:
                for field in requiredFields:
                    if field in self._sentenceData:
                        atLeastOnePresentInSentence = True
                    kwargs[field] = self._state[field]
            except KeyError:
                continue

            if atLeastOnePresentInSentence:
                callback(**kwargs)



NMEAAdapter.REQUIRED_CALLBACK_FIELDS = dict(
    (name, method.positional) for name, method
    in ipositioning.IPositioningReceiver.namesAndDescriptions())
