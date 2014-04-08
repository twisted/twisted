Twisted Positioning
===================

``twisted.positioning``: geolocation in Twisted

Introduction
------------

``twisted.positioning`` is a package for doing geospatial positioning (trying to find where you are on Earth) using Twisted.

High-level overview
-------------------

In ``twisted.positioning``, you write an :api:`twisted.positioning.ipositioning.IPositioningReceiver <IPositioningReceiver>` implementation that will get called whenever some information about your position is known (such as position, altitude, heading...).
The package provides a base class, :api:`twisted.positioning.base.BasePositioningReceiver <BasePositioningReceiver>` you might want to use that implements all of the receiver methods as stubs.

Secondly, you will want a positioning source, which will call your :api:`twisted.positioning.ipositioning.IPositioningReceiver <IPositioningReceiver>`.
Currently, ``twisted.positioning`` provides an NMEA implementation, which is a standard protocol spoken by many positioning devices, usually over a serial port.

Examples
--------

:download:`nmealogger.py <listings/positioning/nmealogger.py>`

.. literalinclude:: listings/positioning/nmealogger.py

- Connects to an NMEA device on a serial port, and reports whenever it receives a position.
