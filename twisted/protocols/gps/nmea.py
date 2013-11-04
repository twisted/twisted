# -*- test-case-name: twisted.test.test_nmea -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
NMEA 0183 implementation

Maintainer: Bob Ippolito

The following NMEA 0183 sentences are currently understood::
    GPGGA (fix)
    GPGLL (position)
    GPRMC (position and time)
    GPGSA (active satellites)
 
The following NMEA 0183 sentences require implementation::
    None really, the others aren't generally useful or implemented in most devices anyhow

Other desired features::
    - A NMEA 0183 producer to emulate GPS devices (?)
"""

import operator
from functools import reduce

from twisted.protocols import basic

POSFIX_INVALID, POSFIX_SPS, POSFIX_DGPS, POSFIX_PPS = 0, 1, 2, 3
MODE_AUTO, MODE_FORCED = 'A', 'M'
MODE_NOFIX, MODE_2D, MODE_3D = 1, 2, 3

class InvalidSentence(Exception):
    pass

class InvalidChecksum(Exception):
    pass

class NMEAReceiver(basic.LineReceiver):
    """
    This parses most common NMEA-0183 messages, presumably from a serial GPS
    device at 4800 bps.
    """
    delimiter = '\r\n'
    dispatch = {
        'GPGGA': 'fix',
        'GPGLL': 'position',
        'GPGSA': 'activesatellites',
        'GPRMC': 'positiontime',
        'GPGSV': 'viewsatellites',    # not implemented
        'GPVTG': 'course',            # not implemented
        'GPALM': 'almanac',           # not implemented
        'GPGRS': 'range',             # not implemented
        'GPGST': 'noise',             # not implemented
        'GPMSS': 'beacon',            # not implemented
        'GPZDA': 'time',              # not implemented
    }
    # generally you may miss the beginning of the first message
    ignore_invalid_sentence = 1
    # checksums shouldn't be invalid
    ignore_checksum_mismatch = 0
    # ignore unknown sentence types
    ignore_unknown_sentencetypes = 0
    # do we want to even bother checking to see if it's from the 20th century?
    convert_dates_before_y2k = 1

    def lineReceived(self, line):
        if not line.startswith('$'):
            if self.ignore_invalid_sentence:
                return
            raise InvalidSentence("%r does not begin with $" % (line,))
        # message is everything between $ and *, checksum is xor of all ASCII
        # values of the message
        strmessage, checksum = line[1:].strip().split('*')
        message = strmessage.split(',')
        sentencetype, message = message[0], message[1:]
        dispatch = self.dispatch.get(sentencetype, None)
        if (not dispatch) and (not self.ignore_unknown_sentencetypes):
            raise InvalidSentence("sentencetype %r" % (sentencetype,))
        if not self.ignore_checksum_mismatch:
            checksum = int(checksum, 16)
            calculated_checksum = reduce(operator.xor, map(ord, strmessage))
            if checksum != calculated_checksum:
                raise InvalidChecksum("Given 0x%02X != 0x%02X" % (checksum,
                    calculated_checksum))
        handler = getattr(self, "handle_%s" % dispatch, None)
        decoder = getattr(self, "decode_%s" % dispatch, None)
        if not (dispatch and handler and decoder):
            # missing dispatch, handler, or decoder
            return
        # return handler(*decoder(*message))
        try:
            decoded = decoder(*message)
        except Exception, e:
            raise InvalidSentence("%r is not a valid %s (%s) sentence" % (
                line, sentencetype, dispatch))
        return handler(*decoded)

    def decode_position(self, latitude, ns, longitude, ew, utc, status):
        latitude, longitude = self._decode_latlon(latitude, ns, longitude, ew)
        utc = self._decode_utc(utc)
        if status == 'A':
            status = 1
        else:
            status = 0
        return (
            latitude,
            longitude,
            utc,
            status,
        )

    def decode_positiontime(self, utc, status, latitude, ns, longitude, ew, speed, course, utcdate, magvar, magdir):
        utc = self._decode_utc(utc)
        latitude, longitude = self._decode_latlon(latitude, ns, longitude, ew)
        if speed != '':
            speed = float(speed)
        else:
            speed = None
        if course != '':
            course = float(course)
        else:
            course = None
        utcdate = 2000+int(utcdate[4:6]), int(utcdate[2:4]), int(utcdate[0:2])
        if self.convert_dates_before_y2k and utcdate[0] > 2073:
            # GPS was invented by the US DoD in 1973, but NMEA uses 2 digit year.
            # Highly unlikely that we'll be using NMEA or this twisted module in 70 years,
            # but remotely possible that you'll be using it to play back data from the 20th century.
            utcdate = (utcdate[0] - 100, utcdate[1], utcdate[2])
        if magvar != '':
            magvar = float(magvar)
        if magdir == 'W':
            magvar = -magvar
        else:
            magvar = None
        return (
            latitude,
            longitude,
            speed,
            course,
            # UTC seconds past utcdate
            utc,
            # UTC (year, month, day)
            utcdate,
            # None or magnetic variation in degrees (west is negative)
            magvar,
        )

    def _decode_utc(self, utc):
        utc_hh, utc_mm, utc_ss = map(float, (utc[:2], utc[2:4], utc[4:]))
        return utc_hh * 3600.0 + utc_mm * 60.0 + utc_ss

    def _decode_latlon(self, latitude, ns, longitude, ew):
        latitude = float(latitude[:2]) + float(latitude[2:])/60.0
        if ns == 'S':
            latitude = -latitude
        longitude = float(longitude[:3]) + float(longitude[3:])/60.0
        if ew == 'W':
            longitude = -longitude
        return (latitude, longitude)

    def decode_activesatellites(self, mode1, mode2, *args):
        satellites, (pdop, hdop, vdop) = args[:12], map(float, args[12:])
        satlist = []
        for n in satellites:
            if n:
                satlist.append(int(n))
            else:
                satlist.append(None)
        mode = (mode1, int(mode2))
        return (
            # satellite list by channel
            tuple(satlist),
            # (MODE_AUTO/MODE_FORCED, MODE_NOFIX/MODE_2DFIX/MODE_3DFIX)
            mode,
            # position dilution of precision
            pdop,
            # horizontal dilution of precision
            hdop,
            # vertical dilution of precision
            vdop,
        )
    
    def decode_fix(self, utc, latitude, ns, longitude, ew, posfix, satellites, hdop, altitude, altitude_units, geoid_separation, geoid_separation_units, dgps_age, dgps_station_id):
        latitude, longitude = self._decode_latlon(latitude, ns, longitude, ew)
        utc = self._decode_utc(utc)
        posfix = int(posfix)
        satellites = int(satellites)
        hdop = float(hdop)
        altitude = (float(altitude), altitude_units)
        if geoid_separation != '':
            geoid = (float(geoid_separation), geoid_separation_units)
        else:
            geoid = None
        if dgps_age != '':
            dgps = (float(dgps_age), dgps_station_id)
        else:
            dgps = None
        return (
            # seconds since 00:00 UTC
            utc,                 
            # latitude (degrees)
            latitude,       
            # longitude (degrees)
            longitude,     
            # position fix status (POSFIX_INVALID, POSFIX_SPS, POSFIX_DGPS, POSFIX_PPS)
            posfix,           
            # number of satellites used for fix 0 <= satellites <= 12 
            satellites,   
            # horizontal dilution of precision
            hdop,               
            # None or (altitude according to WGS-84 ellipsoid, units (typically 'M' for meters)) 
            altitude,
            # None or (geoid separation according to WGS-84 ellipsoid, units (typically 'M' for meters))
            geoid,
            # (age of dgps data in seconds, dgps station id)
            dgps,
        )
