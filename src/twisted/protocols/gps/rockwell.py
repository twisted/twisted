# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.
 

"""
Rockwell Semiconductor Zodiac Serial Protocol
Coded from official protocol specs (Order No. GPS-25, 09/24/1996, Revision 11)

Maintainer: Bob Ippolito

The following Rockwell Zodiac messages are currently understood::
    EARTHA\\r\\n (a hack to "turn on" a DeLorme Earthmate)
    1000 (Geodesic Position Status Output)
    1002 (Channel Summary)
    1003 (Visible Satellites)
    1011 (Receiver ID)

The following Rockwell Zodiac messages require implementation::
    None really, the others aren't quite so useful and require bidirectional communication w/ the device

Other desired features::
    - Compatibility with the DeLorme Tripmate and other devices with this chipset (?)
"""

import math
import struct

from twisted.internet import protocol
from twisted.python import log

DEBUG = 1


class ZodiacParseError(ValueError):
  pass



class Zodiac(protocol.Protocol):
  dispatch = {
    # Output Messages (* means they get sent by the receiver by default periodically)
    1000: 'fix',          # *Geodesic Position Status Output
    1001: 'ecef',         # ECEF Position Status Output
    1002: 'channels',     # *Channel Summary
    1003: 'satellites',   # *Visible Satellites
    1005: 'dgps',         # Differential GPS Status
    1007: 'channelmeas',  # Channel Measurement
    1011: 'id',           # *Receiver ID
    1012: 'usersettings', # User-Settings Output
    1100: 'testresults',  # Built-In Test Results
    1102: 'meastimemark', # Measurement Time Mark
    1108: 'utctimemark',  # UTC Time Mark Pulse Output
    1130: 'serial',       # Serial Port Communication Parameters In Use
    1135: 'eepromupdate', # EEPROM Update
    1136: 'eepromstatus', # EEPROM Status
  }
  # these aren't used for anything yet, just sitting here for reference
  messages = {
    # Input Messages
    'fix':      1200,     # Geodesic Position and Velocity Initialization
    'udatum':   1210,     # User-Defined Datum Definition
    'mdatum':   1211,     # Map Datum Select
    'smask':    1212,     # Satellite Elevation Mask Control
    'sselect':  1213,     # Satellite Candidate Select
    'dgpsc':    1214,     # Differential GPS Control
    'startc':   1216,     # Cold Start Control
    'svalid':   1217,     # Solution Validity Control
    'antenna':  1218,     # Antenna Type Select
    'altinput': 1219,     # User-Entered Altitude Input
    'appctl':   1220,     # Application Platform Control
    'navcfg':   1221,     # Nav Configuration
    'test':     1300,     # Perform Built-In Test Command
    'restart':  1303,     # Restart Command
    'serial':   1330,     # Serial Port Communications Parameters
    'msgctl':   1331,     # Message Protocol Control
    'dgpsd':    1351,     # Raw DGPS RTCM SC-104 Data
  }  
  MAX_LENGTH = 296
  allow_earthmate_hack = 1
  recvd = ""
  
  def dataReceived(self, recd):
    self.recvd = self.recvd + recd
    while len(self.recvd) >= 10:

      # hack for DeLorme EarthMate
      if self.recvd[:8] == 'EARTHA\r\n':
        if self.allow_earthmate_hack:
          self.allow_earthmate_hack = 0
          self.transport.write('EARTHA\r\n')
        self.recvd = self.recvd[8:]
        continue
      
      if self.recvd[0:2] != '\xFF\x81':
        if DEBUG:
          raise ZodiacParseError('Invalid Sync %r' % self.recvd)
        else:
          raise ZodiacParseError
      sync, msg_id, length, acknak, checksum = struct.unpack('<HHHHh', self.recvd[:10])
      
      # verify checksum
      cksum = -(sum(sync, msg_id, length, acknak) & 0xFFFF)
      cksum, = struct.unpack('<h', struct.pack('<h', cksum))
      if cksum != checksum:
        if DEBUG:
          raise ZodiacParseError('Invalid Header Checksum %r != %r %r' % (checksum, cksum, self.recvd[:8]))
        else:
          raise ZodiacParseError
      
      # length was in words, now it's bytes
      length = length * 2

      # do we need more data ?
      neededBytes = 10
      if length:
        neededBytes += length + 2
      if len(self.recvd) < neededBytes:
        break

      if neededBytes > self.MAX_LENGTH:
        raise ZodiacParseError("Invalid Header??")

      # empty messages pass empty strings
      message = ''

      # does this message have data ?
      if length:
        message = self.recvd[10:10 + length], 
        checksum = struct.unpack('<h', self.recvd[10 + length:neededBytes])[0]
        cksum = 0x10000 - (sum(
            struct.unpack('<%dH' % (length/2), message)) & 0xFFFF)
        cksum, = struct.unpack('<h', struct.pack('<h', cksum))
        if cksum != checksum:
          if DEBUG:
            log.dmsg('msg_id = %r length = %r' % (msg_id, length), debug=True)
            raise ZodiacParseError('Invalid Data Checksum %r != %r %r' % (
                checksum, cksum, message))
          else:
            raise ZodiacParseError

      # discard used buffer, dispatch message
      self.recvd = self.recvd[neededBytes:]
      self.receivedMessage(msg_id, message, acknak)
  
  def receivedMessage(self, msg_id, message, acknak):
    dispatch = self.dispatch.get(msg_id, None)
    if not dispatch:
      raise ZodiacParseError('Unknown msg_id = %r' % msg_id)
    handler = getattr(self, 'handle_%s' % dispatch, None)
    decoder = getattr(self, 'decode_%s' % dispatch, None)
    if not (handler and decoder):
      # missing handler or decoder
      #if DEBUG:
      #  log.msg('MISSING HANDLER/DECODER PAIR FOR: %r' % (dispatch,), debug=True)
      return
    decoded = decoder(message)
    return handler(*decoded)
  
  def decode_fix(self, message):
    assert len(message) == 98, "Geodesic Position Status Output should be 55 words total (98 byte message)"
    (ticks, msgseq, satseq, navstatus, navtype, nmeasure, polar, gpswk, gpses, gpsns, utcdy, utcmo, utcyr, utchr, utcmn, utcsc, utcns, latitude, longitude, height, geoidalsep, speed, course, magvar, climb, mapdatum, exhposerr, exvposerr, extimeerr, exphvelerr, clkbias, clkbiasdev, clkdrift, clkdriftdev) = struct.unpack('<LhhHHHHHLLHHHHHHLlllhLHhhHLLLHllll', message)

    # there's a lot of shit in here.. 
    # I'll just snag the important stuff and spit it out like my NMEA decoder
    utc = (utchr * 3600.0) + (utcmn * 60.0) + utcsc + (float(utcns) * 0.000000001)
    
    log.msg('utchr, utcmn, utcsc, utcns = ' + repr((utchr, utcmn, utcsc, utcns)), debug=True)
    
    latitude = float(latitude)   * 0.00000180 / math.pi
    longitude = float(longitude) * 0.00000180 / math.pi
    posfix = not (navstatus & 0x001c)
    satellites = nmeasure
    hdop = float(exhposerr) * 0.01
    altitude = float(height) * 0.01, 'M'
    geoid = float(geoidalsep) * 0.01, 'M'
    dgps = None
    return (
      # seconds since 00:00 UTC
      utc,                 
      # latitude (degrees)
      latitude,
      # longitude (degrees)
      longitude,
      # position fix status (invalid = False, valid = True)
      posfix,
      # number of satellites [measurements] used for fix 0 <= satellites <= 12 
      satellites,
      # horizontal dilution of precision
      hdop,
      # (altitude according to WGS-84 ellipsoid, units (always 'M' for meters)) 
      altitude,
      # (geoid separation according to WGS-84 ellipsoid, units (always 'M' for meters))
      geoid,
      # None, for compatibility w/ NMEA code
      dgps,
    )

  def decode_id(self, message):
    assert len(message) == 106, "Receiver ID Message should be 59 words total (106 byte message)"
    ticks, msgseq, channels, software_version, software_date, options_list, reserved = struct.unpack('<Lh20s20s20s20s20s', message)
    channels, software_version, software_date, options_list = map(lambda s: s.split('\0')[0], (channels, software_version, software_date, options_list))
    software_version = float(software_version)
    channels = int(channels) # 0-12 .. but ALWAYS 12, so we ignore.
    options_list = int(options_list[:4], 16) # only two bitflags, others are reserved
    minimize_rom = (options_list & 0x01) > 0
    minimize_ram = (options_list & 0x02) > 0
    # (version info), (options info)
    return ((software_version, software_date), (minimize_rom, minimize_ram))

  def decode_channels(self, message):
    assert len(message) == 90, "Channel Summary Message should be 51 words total (90 byte message)"
    ticks, msgseq, satseq, gpswk, gpsws, gpsns = struct.unpack('<LhhHLL', message[:18])
    channels = []
    message = message[18:]
    for i in range(12):
      flags, prn, cno = struct.unpack('<HHH', message[6 * i:6 * (i + 1)])
      # measurement used, ephemeris available, measurement valid, dgps corrections available
      flags = (flags & 0x01, flags & 0x02, flags & 0x04, flags & 0x08)
      channels.append((flags, prn, cno))
    # ((flags, satellite PRN, C/No in dbHz)) for 12 channels
    # satellite message sequence number
    # gps week number, gps seconds in week (??), gps nanoseconds from Epoch
    return (tuple(channels),) #, satseq, (gpswk, gpsws, gpsns))

  def decode_satellites(self, message):
    assert len(message) == 90, "Visible Satellites Message should be 51 words total (90 byte message)"
    ticks, msgseq, gdop, pdop, hdop, vdop, tdop, numsatellites = struct.unpack('<LhhhhhhH', message[:18])
    gdop, pdop, hdop, vdop, tdop = map(lambda n: float(n) * 0.01, (gdop, pdop, hdop, vdop, tdop))
    satellites = []
    message = message[18:]
    for i in range(numsatellites):
      prn, azi, elev = struct.unpack('<Hhh', message[6 * i:6 * (i + 1)])
      azi, elev = map(lambda n: (float(n) * 0.0180 / math.pi), (azi, elev))
      satellites.push((prn, azi, elev))
    # ((PRN [0, 32], azimuth +=[0.0, 180.0] deg, elevation +-[0.0, 90.0] deg)) satellite info (0-12)
    # (geometric, position, horizontal, vertical, time) dilution of precision 
    return (tuple(satellites), (gdop, pdop, hdop, vdop, tdop))

  def decode_dgps(self, message):
    assert len(message) == 38, "Differential GPS Status Message should be 25 words total (38 byte message)"
    raise NotImplementedError

  def decode_ecef(self, message):
    assert len(message) == 96, "ECEF Position Status Output Message should be 54 words total (96 byte message)"
    raise NotImplementedError

  def decode_channelmeas(self, message):
    assert len(message) == 296, "Channel Measurement Message should be 154 words total (296 byte message)"
    raise NotImplementedError

  def decode_usersettings(self, message):
    assert len(message) == 32, "User-Settings Output Message should be 22 words total (32 byte message)"
    raise NotImplementedError

  def decode_testresults(self, message):
    assert len(message) == 28, "Built-In Test Results Message should be 20 words total (28 byte message)"
    raise NotImplementedError

  def decode_meastimemark(self, message):
    assert len(message) == 494, "Measurement Time Mark Message should be 253 words total (494 byte message)"
    raise NotImplementedError

  def decode_utctimemark(self, message):
    assert len(message) == 28, "UTC Time Mark Pulse Output Message should be 20 words total (28 byte message)"
    raise NotImplementedError

  def decode_serial(self, message):
    assert len(message) == 30, "Serial Port Communication Parameters In Use Message should be 21 words total (30 byte message)"
    raise NotImplementedError

  def decode_eepromupdate(self, message):
    assert len(message) == 8, "EEPROM Update Message should be 10 words total (8 byte message)"
    raise NotImplementedError

  def decode_eepromstatus(self, message):
    assert len(message) == 24, "EEPROM Status Message should be 18 words total (24 byte message)"
    raise NotImplementedError
