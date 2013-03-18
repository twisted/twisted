# Copyright (c) 2009-2011 Twisted Matrix Laboratories.
# See LICENSE for details.
"""
Test cases for using NMEA sentences.
"""
import datetime
from zope.interface import implements

from twisted.positioning import base, nmea, ipositioning
from twisted.trial.unittest import TestCase

from twisted.positioning.base import LATITUDE, LONGITUDE

# Sample sentences
GPGGA = '$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47'
GPRMC = '$GPRMC,123519,A,4807.038,N,01131.000,E,022.4,084.4,230394,003.1,W*6A'
GPGSA = '$GPGSA,A,3,19,28,14,18,27,22,31,39,,,,,1.7,1.0,1.3*34'
GPHDT = '$GPHDT,038.005,T*3B'
GPGLL = '$GPGLL,4916.45,N,12311.12,W,225444,A*31'
GPGLL_PARTIAL = '$GPGLL,3751.65,S,14507.36,E*77'

GPGSV_SINGLE = '$GPGSV,1,1,11,03,03,111,00,04,15,270,00,06,01,010,00,,,,*4b'
GPGSV_EMPTY_MIDDLE = '$GPGSV,1,1,11,03,03,111,00,,,,,,,,,13,06,292,00*75'
GPGSV_SEQ = GPGSV_FIRST, GPGSV_MIDDLE, GPGSV_LAST = """
$GPGSV,3,1,11,03,03,111,00,04,15,270,00,06,01,010,00,13,06,292,00*74
$GPGSV,3,2,11,14,25,170,00,16,57,208,39,18,67,296,40,19,40,246,00*74
$GPGSV,3,3,11,22,42,067,42,24,14,311,43,27,05,244,00,,,,*4D
""".split()



class NMEATestReceiver(object):
    """
    An NMEA receiver for testing.

    Remembers the last sentence it has received.
    """
    implements(ipositioning.INMEAReceiver)

    def __init__(self):
        self.clear()


    def clear(self):
        """
        Forgets the received sentence (if any), by setting
        C{self.receivedSentence} to C{None}.
        """
        self.receivedSentence = None


    def sentenceReceived(self, sentence):
        self.receivedSentence = sentence



class NMEACallbackTestProtocol(nmea.NMEAProtocol):
    """
    An NMEA protocol with a bunch of callbacks that remembers when
    those callbacks have been called.
    """
    def __init__(self):
        nmea.NMEAProtocol.__init__(self, None)

        for sentenceType in nmea.NMEAProtocol.SENTENCE_CONTENTS:
            self._createCallback(sentenceType)

        self.clear()


    def clear(self):
        """
        Forgets all of the called methods, by setting C{self.called} to
        C{None}.
        """
        self.called = {}


    SENTENCE_TYPES = list(nmea.NMEAProtocol.SENTENCE_CONTENTS)


    def _createCallback(self, sentenceType):
        """
        Creates a callback for an NMEA sentence.
        """
        def callback(sentence):
            self.called[sentenceType] = True

        setattr(self, "nmea_" + sentenceType, callback)



class CallbackTests(TestCase):
    """
    Tests if callbacks on NMEA protocols are correctly called.
    """
    def setUp(self):
        self.callbackProtocol = NMEACallbackTestProtocol()


    def test_callbacksCalled(self):
        """
        Tests that the correct callbacks fire, and that *only* those fire.
        """
        sentencesByType = {'GPGGA': ['$GPGGA*56'],
                           'GPGLL': ['$GPGLL*50'],
                           'GPGSA': ['$GPGSA*42'],
                           'GPGSV': ['$GPGSV*55'],
                           'GPHDT': ['$GPHDT*4f'],
                           'GPRMC': ['$GPRMC*4b']}

        for calledSentenceType in sentencesByType:
            for sentence in sentencesByType[calledSentenceType]:
                self.callbackProtocol.lineReceived(sentence)
                called = self.callbackProtocol.called

                for sentenceType in NMEACallbackTestProtocol.SENTENCE_TYPES:
                    if sentenceType == calledSentenceType:
                        self.assertEquals(called[sentenceType], True)
                    else:
                        self.assertNotIn(sentenceType, called)

                self.callbackProtocol.clear()



class SplitTest(TestCase):
    """
    Checks splitting of NMEA sentences.
    """
    def test_withChecksum(self):
        """
        Tests that an NMEA sentence with a checksum gets split correctly.
        """
        splitSentence = nmea.split("$GPGGA,spam,eggs*00")
        self.assertEqual(splitSentence, ['GPGGA', 'spam', 'eggs'])


    def test_noCheckum(self):
        """
        Tests that an NMEA sentence without a checksum gets split correctly.
        """
        splitSentence = nmea.split("$GPGGA,spam,eggs*")
        self.assertEqual(splitSentence, ['GPGGA', 'spam', 'eggs'])



class ChecksumTests(TestCase):
    """
    NMEA sentence checksum verification tests.
    """
    def test_valid(self):
        """
        Tests checkum validation for valid or missing checksums.
        """
        sentences = [GPGGA, GPGGA[:-2]]

        for s in sentences:
            nmea.validateChecksum(s)


    def test_invalid(self):
        """
        Tests checksum validation on invalid checksums.
        """
        bareSentence, checksum = GPGGA.split("*")
        badChecksum = "%x" % (int(checksum, 16) + 1)
        sentences = ["%s*%s" % (bareSentence, badChecksum)]

        for s in sentences:
            self.assertRaises(base.InvalidChecksum, nmea.validateChecksum, s)



class NMEAReceiverSetup:
    """
    A mixin for tests that need an NMEA receiver (and a protocol attached to
    it).

    @ivar receiver: An NMEA receiver that remembers the last sentence.
    @type receiver: L{NMEATestReceiver}

    @ivar protocol: An NMEA protocol attached to the receiver.
    @type protocol: L{twisted.positioning.nmea.NMEAProtocol}
    """
    def setUp(self):
        self.receiver = NMEATestReceiver()
        self.protocol = nmea.NMEAProtocol(self.receiver)    



class GSVSequenceTests(NMEAReceiverSetup, TestCase):
    """
    Tests if GSV sentence sequences are identified correctly.
    """
    def test_firstSentence(self):
        """
        Tests if the last sentence in a GSV sequence is correctly identified.
        """
        self.protocol.lineReceived(GPGSV_FIRST)
        sentence = self.receiver.receivedSentence

        self.assertTrue(sentence._isFirstGSVSentence())
        self.assertFalse(sentence._isLastGSVSentence())


    def test_middleSentence(self):
        """
        Tests if a sentence in the middle of a GSV sequence is correctly
        identified (as being neither the last nor the first).
        """
        self.protocol.lineReceived(GPGSV_MIDDLE)
        sentence = self.receiver.receivedSentence

        self.assertFalse(sentence._isFirstGSVSentence())
        self.assertFalse(sentence._isLastGSVSentence())


    def test_lastSentence(self):
        """
        Tests if the last sentence in a GSV sequence is correctly identified.
        """
        self.protocol.lineReceived(GPGSV_LAST)
        sentence = self.receiver.receivedSentence

        self.assertFalse(sentence._isFirstGSVSentence())
        self.assertTrue(sentence._isLastGSVSentence())



class BogusSentenceTests(NMEAReceiverSetup, TestCase):
    """
    Tests for verifying predictable failure for bogus NMEA sentences.
    """
    def assertRaisesOnSentence(self, exceptionClass, sentence):
        """
        Asserts that the protocol raises C{exceptionClass} when it receives
        C{sentence}.

        @param exceptionClass: The exception class expected to be raised.
        @type exceptionClass: C{Exception} subclass

        @param sentence: The (bogus) NMEA sentence.
        @type sentence: C{str}
        """
        self.assertRaises(exceptionClass, self.protocol.lineReceived, sentence)


    def test_raiseOnUnknownSentenceType(self):
        """
        Tests that the protocol raises C{ValueError} when you feed it a
        well-formed sentence of unknown type.
        """
        self.assertRaisesOnSentence(ValueError, "$GPBOGUS*5b")


    def test_raiseOnMalformedSentences(self):
        """
        Tests that the protocol raises L{base.InvalidSentence} when you feed
        it a malformed sentence.
        """
        self.assertRaisesOnSentence(base.InvalidSentence, "GPBOGUS")



class NMEASentenceTests(NMEAReceiverSetup, TestCase):
    """
    Tests for L{nmea.NMEASentence} objects.
    """
    def test_repr(self):
        """
        Checks that the C{repr} of L{nmea.NMEASentence} objects is
        predictable.
        """
        sentencesWithExpectedRepr = [
            (GPGSA,
             "<NMEASentence (GPGSA) {"
             "dataMode: A, "
             "fixType: 3, "
             "horizontalDilutionOfPrecision: 1.0, "
             "positionDilutionOfPrecision: 1.7, "
             "usedSatellitePRN_0: 19, "
             "usedSatellitePRN_1: 28, "
             "usedSatellitePRN_2: 14, "
             "usedSatellitePRN_3: 18, "
             "usedSatellitePRN_4: 27, "
             "usedSatellitePRN_5: 22, "
             "usedSatellitePRN_6: 31, "
             "usedSatellitePRN_7: 39, "
             "verticalDilutionOfPrecision: 1.3"
             "}>"),
        ]

        for sentence, repr_ in sentencesWithExpectedRepr:
            self.protocol.lineReceived(sentence)
            received = self.receiver.receivedSentence
            self.assertEquals(repr(received), repr_)



class ParsingTests(NMEAReceiverSetup, TestCase):
    """
    Tests if raw NMEA sentences get parsed correctly.

    This doesn't really involve any interpretation, just turning ugly raw NMEA
    representations into objects that are more pleasant to work with.
    """
    def _parserTest(self, sentence, expected):
        """
        Passes a sentence to the protocol and gets the parsed sentence from
        the receiver. Then verifies that the parsed sentence contains the
        expected data.
        """
        self.protocol.lineReceived(sentence)
        received = self.receiver.receivedSentence
        self.assertEquals(expected, received._sentenceData)


    def test_fullRMC(self):
        """
        Tests that a full RMC sentence is correctly parsed.
        """
        expected = {
             'type': 'GPRMC',
             'latitudeFloat': '4807.038',
             'latitudeHemisphere': 'N',
             'longitudeFloat': '01131.000',
             'longitudeHemisphere': 'E',
             'magneticVariation': '003.1',
             'magneticVariationDirection': 'W',
             'speedInKnots': '022.4',
             'timestamp': '123519',
             'datestamp': '230394',
             'trueHeading': '084.4',
             'dataMode': 'A',
        }
        self._parserTest(GPRMC, expected)


    def test_fullGGA(self):
        """
        Tests that a full GGA sentence is correctly parsed.
        """
        expected = {
            'type': 'GPGGA',

            'altitude': '545.4',
            'altitudeUnits': 'M',
            'heightOfGeoidAboveWGS84': '46.9',
            'heightOfGeoidAboveWGS84Units': 'M',

            'horizontalDilutionOfPrecision': '0.9',

            'latitudeFloat': '4807.038',
            'latitudeHemisphere': 'N',
            'longitudeFloat': '01131.000',
            'longitudeHemisphere': 'E',

            'numberOfSatellitesSeen': '08',
            'timestamp': '123519',
            'fixQuality': '1',
        }
        self._parserTest(GPGGA, expected)


    def test_fullGLL(self):
        """
        Tests that a full GLL sentence is correctly parsed.
        """
        expected = {
            'type': 'GPGLL',

            'latitudeFloat': '4916.45',
            'latitudeHemisphere': 'N',
            'longitudeFloat': '12311.12',
            'longitudeHemisphere': 'W',

            'timestamp': '225444',
            'dataMode': 'A',
        }
        self._parserTest(GPGLL, expected)


    def test_partialGLL(self):
        """
        Tests that a partial GLL sentence is correctly parsed.
        """
        expected = {
            'type': 'GPGLL',

            'latitudeFloat': '3751.65',
            'latitudeHemisphere': 'S',
            'longitudeFloat': '14507.36',
            'longitudeHemisphere': 'E',
        }
        self._parserTest(GPGLL_PARTIAL, expected)


    def test_fullGSV(self):
        """
        Tests that a full GSV sentence is correctly parsed.
        """
        expected = {
            'type': 'GPGSV',
            'GSVSentenceIndex': '1',
            'numberOfGSVSentences': '3',
            'numberOfSatellitesSeen': '11',

            'azimuth_0': '111',
            'azimuth_1': '270',
            'azimuth_2': '010',
            'azimuth_3': '292',

            'elevation_0': '03',
            'elevation_1': '15',
            'elevation_2': '01',
            'elevation_3': '06',

            'satellitePRN_0': '03',
            'satellitePRN_1': '04',
            'satellitePRN_2': '06',
            'satellitePRN_3': '13',

            'signalToNoiseRatio_0': '00',
            'signalToNoiseRatio_1': '00',
            'signalToNoiseRatio_2': '00',
            'signalToNoiseRatio_3': '00',
        }
        self._parserTest(GPGSV_FIRST, expected)


    def test_partialGSV(self):
        """
        Tests that a partial GSV sentence is correctly parsed.
        """
        expected = {
            'type': 'GPGSV',
            'GSVSentenceIndex': '3',
            'numberOfGSVSentences': '3',
            'numberOfSatellitesSeen': '11',

            'azimuth_0': '067',
            'azimuth_1': '311',
            'azimuth_2': '244',

            'elevation_0': '42',
            'elevation_1': '14',
            'elevation_2': '05',

            'satellitePRN_0': '22',
            'satellitePRN_1': '24',
            'satellitePRN_2': '27',

            'signalToNoiseRatio_0': '42',
            'signalToNoiseRatio_1': '43',
            'signalToNoiseRatio_2': '00',
        }
        self._parserTest(GPGSV_LAST, expected)


    def test_fullHDT(self):
        """
        Tests that a full HDT sentence is correctly parsed.
        """
        expected = {
            'type': 'GPHDT',
            'trueHeading': '038.005',
        }
        self._parserTest(GPHDT, expected)


    def test_typicalGSA(self):
        """
        Tests that a typical GSA sentence is correctly parsed.
        """
        expected = {
            'type': 'GPGSA',

            'dataMode': 'A',
            'fixType': '3',
            
            'usedSatellitePRN_0': '19',
            'usedSatellitePRN_1': '28',
            'usedSatellitePRN_2': '14',
            'usedSatellitePRN_3': '18',
            'usedSatellitePRN_4': '27',
            'usedSatellitePRN_5': '22',
            'usedSatellitePRN_6': '31',
            'usedSatellitePRN_7': '39',

            'positionDilutionOfPrecision': '1.7',
            'horizontalDilutionOfPrecision': '1.0',
            'verticalDilutionOfPrecision': '1.3',
        }
        self._parserTest(GPGSA, expected)



class FixerTestMixin:
    """
    Mixin for tests for the fixers on L{nmea.NMEAAdapter} that adapt
    from NMEA-specific notations to generic Python objects.

    @ivar adapter: The NMEA adapter.
    @type adapter: L{nmea.NMEAAdapter}
    """
    def setUp(self):
        self.adapter = nmea.NMEAAdapter(base.BasePositioningReceiver())


    def _fixerTest(self, sentenceData, expected=None, exceptionClass=None):
        """
        A generic adapter fixer test.

        Creates a sentence from the C{sentenceData} and sends that to the
        adapter. If C{exceptionClass} is not passed, this is assumed to work,
        and C{expected} is compared with the adapter's internal state.
        Otherwise, passing the sentence to the adapter is checked to raise
        C{exceptionClass}.

        @param sentenceData: Raw sentence content.
        @type sentenceData: C{dict} mapping C{str} to C{str}

        @param expected: The expected state of the adapter.
        @type expected: C{dict} or C{None}

        @param exceptionClass: The exception to be raised by the adapter.
        @type exceptionClass: subclass of C{Exception}
        """
        sentence = nmea.NMEASentence(sentenceData)
        def receiveSentence():
            self.adapter.sentenceReceived(sentence)

        if exceptionClass is None:
            receiveSentence()
            self.assertEquals(self.adapter._state, expected)
        else:
            self.assertRaises(exceptionClass, receiveSentence)

        self.adapter.clear()



class TimestampFixerTests(FixerTestMixin, TestCase):
    """
    Tests conversion from NMEA timestamps to C{datetime.time} objects.
    """
    def test_simple(self):
        """
        Tests that a simple timestamp is converted correctly.
        """
        data = {'timestamp': '123456'} # 12:34:56Z
        expected = {'_time': datetime.time(12, 34, 56)}
        self._fixerTest(data, expected)


    def test_broken(self):
        """
        Tests that a broken timestamp raises C{ValueError}.
        """
        badTimestamps = '993456', '129956', '123499'

        for t in badTimestamps:
            self._fixerTest({'timestamp': t}, exceptionClass=ValueError)



class DatestampFixerTests(FixerTestMixin, TestCase):
    def test_intelligent(self):
        """
        Tests "intelligent" datestamp handling (guess century based on last
        two digits). Also tests that this is the default.
        """
        self.assertEqual(self.adapter.DATESTAMP_HANDLING,
                         self.adapter.INTELLIGENT_DATESTAMPS)

        datestring, date = '010199', datetime.date(1999, 1, 1)
        self._fixerTest({'datestamp': datestring}, {'_date': date})

        datestring, date = '010109', datetime.date(2009, 1, 1)
        self._fixerTest({'datestamp': datestring}, {'_date': date})


    def test_19xx(self):
        """
        Tests 20th-century-only datestam handling method.
        """
        self.adapter.DATESTAMP_HANDLING = self.adapter.DATESTAMPS_FROM_19XX

        datestring, date = '010199', datetime.date(1999, 1, 1)
        self._fixerTest({'datestamp': datestring}, {'_date': date})

        datestring, date = '010109', datetime.date(1909, 1, 1)
        self._fixerTest({'datestamp': datestring}, {'_date': date})


    def test_20xx(self):
        """
        Tests 21st-century-only datestam handling method.
        """
        self.adapter.DATESTAMP_HANDLING = self.adapter.DATESTAMPS_FROM_20XX

        datestring, date = '010199', datetime.date(2099, 1, 1)
        self._fixerTest({'datestamp': datestring}, {'_date': date})

        datestring, date = '010109', datetime.date(2009, 1, 1)
        self._fixerTest({'datestamp': datestring}, {'_date': date})


    def test_bogusMethod(self):
        """
        Tests that using a nonexistent datestamp handling method raises C{ValueError}.
        """
        self.adapter.DATESTAMP_HANDLING = "BOGUS_VALUE"
        self._fixerTest({'datestamp': '010199'}, exceptionClass=ValueError)


    def test_broken(self):
        """
        Tests that a broken datestring raises C{ValueError}.
        """
        self._fixerTest({'datestamp': '123456'}, exceptionClass=ValueError)



def _nmeaFloat(degrees, minutes):
    """
    Builds an NMEA float representation for a given angle in degrees and
    decimal minutes.

    @param degrees: The integer degrees for this angle.
    @type degrees: C{int}
    @param minutes: The decimal minutes value for this angle.
    @type minutes: C{float}
    @return: The NMEA float representation for this angle.
    @rtype: C{str}
    """
    return "%i%0.3f" % (degrees, minutes)


def _coordinateSign(hemisphere):
    """
    Return the sign of a coordinate.

    This is C{1} if the coordinate is in the northern or eastern hemispheres,
    C{-1} otherwise.

    @param hemisphere: NMEA shorthand for the hemisphere. One of "NESW".
    @type hemisphere: C{str}

    @return: The sign of the coordinate value.
    @rtype: C{int}
    """
    return 1 if hemisphere in "NE" else -1


def _coordinateType(hemisphere):
    """
    Return the type of a coordinate.

    This is L{LATITUDE} if the coordinate is in the northern or southern
    hemispheres, L{LONGITUDE} otherwise.

    @param hemisphere: NMEA shorthand for the hemisphere. One of "NESW".
    @type hemisphere: C{str}

    @return: The type of the coordinate (L{LATITUDE} or L{LONGITUDE})
    """
    return LATITUDE if hemisphere in "NS" else LONGITUDE



class CoordinateFixerTests(FixerTestMixin, TestCase):
    """
    Tests turning NMEA coordinate notations into something more pleasant.
    """
    def _coordinateFixerTest(self, degrees, minutes, hemisphere):
        """
        Tests that an NMEA representation of a coordinate at the given
        location converts correctly into a L{base.Coordinate}.
        """
        coordinateType = _coordinateType(hemisphere)
        if coordinateType is LATITUDE:
            typeName = "latitude"
        else:
            typeName = "longitude"

        sentenceData = {"%sFloat" % typeName: _nmeaFloat(degrees, minutes),
                        "%sHemisphere" % typeName: hemisphere}
        
        coordinateValue = _coordinateSign(hemisphere)*(degrees + minutes/60)
        coordinate = base.Coordinate(coordinateValue, coordinateType)

        self._fixerTest(sentenceData, {typeName: coordinate})


    def test_north(self):
        """
        Tests that NMEA coordinate representations in the northern hemisphere
        convert correctly.
        """
        self._coordinateFixerTest(10, 30.0, "N")


    def test_south(self):
        """
        Tests that NMEA coordinate representations in the southern hemisphere
        convert correctly.
        """
        self._coordinateFixerTest(45, 12.145, "S")


    def test_east(self):
        """
        Tests that NMEA coordinate representations in the eastern hemisphere
        convert correctly.
        """
        self._coordinateFixerTest(53, 31.513, "E")


    def test_west(self):
        """
        Tests that NMEA coordinate representations in the western hemisphere
        convert correctly.
        """
        self._coordinateFixerTest(12, 45.120, "W")


    def test_badHemisphere(self):
        """
        Tests that NMEA coordinate representations for nonexistent hemispheres
        raise C{ValueError} when you attempt to parse them.
        """
        sentenceData = {'longitudeHemisphere': 'Q'}
        self._fixerTest(sentenceData, exceptionClass=ValueError)


    def test_badHemisphereSign(self):
        """
        Tests that NMEA coordinate repesentation parsing fails predictably
        when you pass nonexistent coordinate types (not latitude or
        longitude).
        """
        getSign = lambda: self.adapter._getHemisphereSign("BOGUS_VALUE")
        self.assertRaises(ValueError, getSign)



class AltitudeFixerTests(FixerTestMixin, TestCase):
    """
    Tests that NMEA representations of altitudes are correctly converted.
    """
    def test_fixAltitude(self):
        """
        Tests that the NMEA representation of an altitude (above mean sea
        level) is correctly converted.
        """
        key, value = 'altitude', '545.4'
        altitude = base.Altitude(float(value))
        self._fixerTest({key: value}, {key: altitude})


    def test_heightOfGeoidAboveWGS84(self):
        """
        Tests that the NMEA representation of an altitude of the geoid (above
        the WGS84 reference level) is correctly converted.
        """
        key, value = 'heightOfGeoidAboveWGS84', '46.9'
        altitude = base.Altitude(float(value))
        self._fixerTest({key: value}, {key: altitude})



class SpeedFixerTests(FixerTestMixin, TestCase):
    """
    Tests that NMEA representations of speeds are correctly converted.
    """
    def test_speedInKnots(self):
        """
        Tests if speeds reported in knots correctly get converted to
        meters per second.
        """
        key, value, targetKey = "speedInKnots", "10", "speed"
        speed = base.Speed(float(value) * base.MPS_PER_KNOT)
        self._fixerTest({key: value}, {targetKey: speed})



class VariationFixerTests(FixerTestMixin, TestCase):
    """
    Tests if the absolute values of magnetic variations on the heading
    and their sign get combined correctly, and if that value gets
    combined with a heading correctly.
    """
    def test_west(self):
        """
        Tests westward (negative) magnetic variation.
        """
        variation, direction = "1.34", "W"
        heading = base.Heading.fromFloats(variationValue=-1*float(variation))
        sentenceData = {'magneticVariation': variation,
                        'magneticVariationDirection': direction}

        self._fixerTest(sentenceData, {'heading': heading})


    def test_east(self):
        """
        Tests eastward (positive) magnetic variation.
        """
        variation, direction = "1.34", "E"
        heading = base.Heading.fromFloats(variationValue=float(variation))
        sentenceData = {'magneticVariation': variation,
                        'magneticVariationDirection': direction}

        self._fixerTest(sentenceData, {'heading': heading})


    def test_withHeading(self):
        """
        Tests if variation values get combined with headings correctly.
        """
        trueHeading, variation, direction = "123.12", "1.34", "E"
        sentenceData = {'trueHeading': trueHeading,
                        'magneticVariation': variation,
                        'magneticVariationDirection': direction}
        heading = base.Heading.fromFloats(float(trueHeading),
                                          variationValue=float(variation))
        self._fixerTest(sentenceData, {'heading': heading})



class PositionErrorFixerTests(FixerTestMixin, TestCase):
    """
    Position errors in NMEA are passed as dilutions of precision (DOP). This
    is a measure relative to some specified value of the GPS device as its
    "reference" precision. Unfortunately, there are very few ways of figuring
    this out from just the device (sans manual).

    There are two basic DOP values: vertical and horizontal. HDOP tells you
    how precise your location is on the face of the earth (pretending it's
    flat, at least locally). VDOP tells you how precise your altitude is
    known. PDOP (position DOP) is a dependent value defined as the Nuclidean
    norm of those two, and gives you a more generic "goodness of fix" value.
    """
    def test_simple(self):
        self._fixerTest(
            {'horizontalDilutionOfPrecision': '11'},
            {'positionError': base.PositionError(hdop=11.)})


    def test_mixing(self):
        pdop, hdop, vdop = "1", "1", "1"
        positionError = base.PositionError(pdop=float(pdop),
                                           hdop=float(hdop),
                                           vdop=float(vdop))
        sentenceData = {'positionDilutionOfPrecision': pdop,
                        'horizontalDilutionOfPrecision': hdop,
                        'verticalDilutionOfPrecision': vdop}
        self._fixerTest(sentenceData, {"positionError": positionError})


class ValidFixTests(FixerTestMixin, TestCase):
    """
    Tests that data reported from a valid fix is used.
    """
    def test_GGA(self):
        """
        Tests that GGA data with a valid fix is used.
        """
        sentenceData = {'type': 'GPGGA',
                        'altitude': '545.4',
                        'fixQuality': nmea.GGA_GPS_FIX}
        expectedState = {'altitude': base.Altitude(545.4)}

        self._fixerTest(sentenceData, expectedState)


    def test_GLL(self):
        """
        Tests that GLL data with a valid data mode is used.
        """
        sentenceData = {'type': 'GPGLL',
                        'altitude': '545.4',
                        'dataMode': nmea.DATA_ACTIVE}
        expectedState = {'altitude': base.Altitude(545.4)}

        self._fixerTest(sentenceData, expectedState)



class InvalidFixTests(FixerTestMixin, TestCase):
    """
    Tests that data being reported from a bad or incomplete fix isn't
    used. Although the specification dictates that GPSes shouldn't produce
    NMEA sentences with real-looking values for altitude or position in them
    unless they have at least some semblance of a GPS fix, this is widely
    ignored.
    """
    def _invalidFixTest(self, sentenceData):
        """
        Tests that sentences with an invalid fix or data mode result in empty
        state (ie, the data isn't used).
        """
        self._fixerTest(sentenceData, {})


    def test_GGA(self):
        """
        Tests that GGA sentence data is unused when there is no fix.
        """
        sentenceData = {'type': 'GPGGA',
                        'altitude': '545.4',
                        'fixQuality': nmea.GGA_INVALID_FIX}

        self._invalidFixTest(sentenceData)


    def test_GLL(self):
        """
        Tests that GLL sentence data is unused when the data is flagged as
        void.
        """
        sentenceData = {'type': 'GPGLL',
                        'altitude': '545.4',
                        'dataMode': nmea.DATA_VOID}

        self._invalidFixTest(sentenceData)


        
    def test_badGSADataMode(self):
        """
        Tests that GSA sentence data is not used when there is no GPS fix, but
        the data mode claims the data is "active". Some GPSes do do this,
        unfortunately, and that means you shouldn't use the data.
        """
        sentenceData = {'type': 'GPGSA',
                        'altitude': '545.4',
                        'dataMode': nmea.DATA_ACTIVE,
                        'fixType': nmea.GSA_NO_FIX}
        self._invalidFixTest(sentenceData)


        
    def test_badGSAFixType(self):
        """
        Tests that GSA sentence data is not used when the fix claims to be
        valid (albeit only 2D), but the data mode says the data is void. Some
        GPSes do do this, unfortunately, and that means you shouldn't use the
        data.
        """
        sentenceData = {'type': 'GPGSA',
                        'altitude': '545.4',
                        'dataMode': nmea.DATA_VOID,
                        'fixType': nmea.GSA_2D_FIX}
        self._invalidFixTest(sentenceData)



    def test_badGSADataModeAndFixType(self):
        """
        Tests that GSA sentence data is not use when neither the fix nor the
        data mode is any good.
        """
        sentenceData = {'type': 'GPGSA',
                        'altitude': '545.4',
                        'dataMode': nmea.DATA_VOID,
                        'fixType': nmea.GSA_NO_FIX}
        self._invalidFixTest(sentenceData)



class MockNMEAReceiver(base.BasePositioningReceiver):
    """
    A mock NMEA receiver.

    Mocks all the L{IPositioningReceiver} methods with stubs that don't do
    anything but register that they were called.
    """
    def __init__(self):
        self.clear()

        for methodName in ipositioning.IPositioningReceiver:
            self._addCallback(methodName)


    def clear(self):
        """
        Forget all the methods that have been called on this receiver, by
        emptying C{self.called}.
        """
        self.called = {}


    def _addCallback(self, name):
        def callback(*a, **kw):
            self.called[name] = True

        setattr(self, name, callback)



class NMEAReceiverTest(TestCase):
    """
    Tests for the NMEA receiver.
    """
    def setUp(self):
        self.receiver = MockNMEAReceiver()
        self.adapter = nmea.NMEAAdapter(self.receiver)
        self.protocol = nmea.NMEAProtocol(self.adapter)


    def _receiverTest(self, sentences, expectedFired=(), extraTest=None):
        """
        A generic test for NMEA receiver behavior.

        @param sentences: The sequence of sentences to simulate receiving.
        @type sentences: iterable of C{str}
        @param expectedFired: The names of the callbacks expected to fire.
        @type expectedFired: iterable of C{str}
        @param extraTest: An optional extra test hook.
        @type extraTest: nullary callable
        """
        for sentence in sentences:
            self.protocol.lineReceived(sentence)

        actuallyFired = self.receiver.called.keys()
        self.assertEquals(set(actuallyFired), set(expectedFired))

        if extraTest is not None:
            extraTest()

        self.receiver.clear()
        self.adapter.clear()


    def test_positionErrorUpdateAcrossStates(self):
        """
        Tests that the positioning error is updated across multiple states.
        """
        sentences = [GPGSA] + GPGSV_SEQ
        callbacksFired = ['positionErrorReceived', 'beaconInformationReceived']

        def checkBeaconInformation():
            beaconInformation = self.adapter._state['beaconInformation']
            self.assertEqual(beaconInformation.seen, 11)
            self.assertEqual(beaconInformation.used, 5)

        self._receiverTest(sentences, callbacksFired, checkBeaconInformation)


    def test_emptyMiddleGSV(self):
        """
        Tests that a GSV sentence with empty entries in any position
        does not mean the entries in subsequent positions are ignored.
        """
        sentences = [GPGSV_EMPTY_MIDDLE]
        callbacksFired = ['beaconInformationReceived']

        def checkBeaconInformation():
            beaconInformation = self.adapter._state['beaconInformation']
            self.assertEqual(beaconInformation.seen, 2)
            prns = [satellite.identifier for satellite in beaconInformation]
            self.assertIn(13, prns)

        self._receiverTest(sentences, callbacksFired, checkBeaconInformation)

    def test_GGASentences(self):
        """
        Tests that a sequence of GGA sentences fires C{positionReceived},
        C{positionErrorReceived} and C{altitudeReceived}.
        """
        sentences = [GPGGA]
        callbacksFired = ['positionReceived',
                          'positionErrorReceived',
                          'altitudeReceived']

        self._receiverTest(sentences, callbacksFired)


    def test_RMCSentences(self):
        """
        Tests that a sequence of RMC sentences fires C{positionReceived},
        C{speedReceived}, C{headingReceived} and C{timeReceived}.
        """
        sentences = [GPRMC]
        callbacksFired = ['headingReceived',
                          'speedReceived',
                          'positionReceived',
                          'timeReceived']

        self._receiverTest(sentences, callbacksFired)


    def test_GSVSentences(self):
        """
        Verifies that a complete sequence of GSV sentences fires
        C{beaconInformationReceived}.
        """
        sentences = [GPGSV_FIRST, GPGSV_MIDDLE, GPGSV_LAST]
        callbacksFired = ['beaconInformationReceived']

        def checkPartialInformation():
            self.assertNotIn('_partialBeaconInformation', self.adapter._state)

        self._receiverTest(sentences, callbacksFired, checkPartialInformation)


    def test_emptyMiddleEntriesGSVSequence(self):
        """
        Verifies that a complete sequence of GSV sentences with empty entries
        in the middle still fires C{beaconInformationReceived}.
        """
        sentences = [GPGSV_EMPTY_MIDDLE]
        self._receiverTest(sentences, ["beaconInformationReceived"])


    def test_incompleteGSVSequence(self):
        """
        Verifies that an incomplete sequence of GSV sentences does not fire.
        """
        sentences = [GPGSV_FIRST]
        self._receiverTest(sentences)


    def test_singleSentenceGSVSequence(self):
        """
        Verifies that the parser does not fail badly when the sequence consists
        of only one sentence (but is otherwise complete).
        """
        sentences = [GPGSV_SINGLE]
        self._receiverTest(sentences, ["beaconInformationReceived"])


    def test_GLLSentences(self):
        """
        Verfies that GLL sentences fire C{positionReceived}.
        """
        sentences = [GPGLL_PARTIAL, GPGLL]
        self._receiverTest(sentences,  ['positionReceived'])


    def test_HDTSentences(self):
        """
        Verfies that HDT sentences fire C{headingReceived}.
        """
        sentences = [GPHDT]
        self._receiverTest(sentences, ['headingReceived'])


    def test_mixedSentences(self):
        """
        Verifies that a mix of sentences fires the correct callbacks.
        """
        sentences = [GPRMC, GPGGA]
        callbacksFired = ['altitudeReceived',
                          'speedReceived',
                          'positionReceived',
                          'positionErrorReceived',
                          'timeReceived',
                          'headingReceived']

        def checkTime():
            expectedDateTime = datetime.datetime(1994, 3, 23, 12, 35, 19)
            self.assertEquals(self.adapter._state['time'], expectedDateTime)

        self._receiverTest(sentences, callbacksFired, checkTime)


    def test_lotsOfMixedSentences(self):
        """
        Tests for an entire gamut of sentences. These are more than you'd
        expect from your average consumer GPS device. They have most of the
        important information, including beacon information and visibility.
        """
        sentences = [GPGSA] + GPGSV_SEQ + [GPRMC, GPGGA, GPGLL]

        callbacksFired = ['headingReceived',
                          'beaconInformationReceived',
                          'speedReceived',
                          'positionReceived',
                          'timeReceived',
                          'altitudeReceived',
                          'positionErrorReceived']

        self._receiverTest(sentences, callbacksFired)
