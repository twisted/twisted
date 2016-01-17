"""
Tests for L{twisted.internet.serialport}.
"""

from twisted.trial import unittest
from twisted.internet.protocol import Protocol
from twisted.python.runtime import platform

try:
    from twisted.internet import serialport
    import serial

except ImportError as e:
    serialport = None
    serial = None

class FakeSerialBase(object):
    def __init__(self, *args, **kwargs):
        # Capture for unit test
        self.captured_args = args
        self.captured_kwargs = kwargs

    def flushInput(self):
        # Avoid calling the real method; it invokes Win32 system calls.
        pass

    def flushOutput(self):
        # Avoid calling the real method; it invokes Win32 system calls.
        pass

class FakeSerial2x(FakeSerialBase):
    """
    Fake Serial class emulating pyserial 2.x behavior.
    """
    def __init__(self, *args, **kwargs):
        super(FakeSerial2x, self).__init__(*args, **kwargs)
        self.hComPort = 25

class FakeSerial3x(FakeSerialBase):
    """
    Fake Serial class emulating pyserial 3.x behavior.
    """
    def __init__(self, *args, **kwargs):
        super(FakeSerial3x, self).__init__(*args, **kwargs)
        self._port_handle = 35

class FakeReactor(object):
    def addEvent(self, a, b, c):
        # This is the only method called on the reactor by SerialPort in the
        # real class.
        pass

if serialport is not None:
    class TestableSerialPortBase(serialport.SerialPort):
        """
        Base testable version of Windows C{twisted.internet.serialport.SerialPort}.
        """
        # Fake this out; it calls into win32 library.
        def _finishPortSetup(self):
            pass

    class TestableSerialPort2x(TestableSerialPortBase):
        """
        Testable version of Windows C{twisted.internet.serialport.SerialPort} that
        uses a fake pyserial 2.x Serial class.
        """
        _serialFactory = FakeSerial2x

    class TestableSerialPort3x(TestableSerialPortBase):
        """
        Testable version of Windows C{twisted.internet.serialport.SerialPort} that
        uses a fake pyserial 3.x Serial class.
        """
        _serialFactory = FakeSerial3x


class Win32SerialPortTests(unittest.TestCase):
    """
    Minimal testing for Twisted's Win32 serial port support.
    """

    if not platform.isWindows():
        skip = "This test must run on Windows."

    elif not serialport:
        skip = "Windows serial port support is not available."

    def setUp(self):
        # Re-usable protocol and reactor
        self.protocol = Protocol()
        self.reactor = FakeReactor()

    def test_serial_port_default_args(self):
        """
        Test correct positional and keyword arguments have been
        passed to the C{serial.Serial} object.
        """
        port = TestableSerialPort2x(self.protocol, "COM3", self.reactor)
        # Validate args
        self.assertEqual(("COM3",), port._serial.captured_args)
        # Validate kwargs
        self.assertEqual(9600,                port._serial.captured_kwargs["baudrate"])
        self.assertEqual(serial.EIGHTBITS,    port._serial.captured_kwargs["bytesize"])
        self.assertEqual(serial.PARITY_NONE,  port._serial.captured_kwargs["parity"])
        self.assertEqual(serial.STOPBITS_ONE, port._serial.captured_kwargs["stopbits"])
        self.assertEqual(0,                   port._serial.captured_kwargs["xonxoff"])
        self.assertEqual(0,                   port._serial.captured_kwargs["rtscts"])
        self.assertEqual(None,                port._serial.captured_kwargs["timeout"])

    def test_serial_port_initially_connected(self):
        """
        Test the port is connected at initialization time, and C{Protocol.makeConnection} has been
        called on the desired protocol.
        """
        self.assertEqual(0,    self.protocol.connected)

        port = TestableSerialPort2x(self.protocol, "COM3", self.reactor)
        self.assertEqual(1, port.connected)
        self.assertEqual(1, self.protocol.connected)
        self.assertEqual(port, self.protocol.transport)

    def test_serial_port_pyserial_2x_windows_handle(self):
        """
        Test correct attribute in the C{serial.Serial} instance has been captured
        for the serial port's Windows HANDLE, for the pyserial 2.x library.
        """
        port = TestableSerialPort2x(self.protocol, "COM3", self.reactor)
        self.assertEqual(25, port._serialHandle)

    def test_serial_port_pyserial_3x_windows_handle(self):
        """
        Test correct attribute in the C{serial.Serial} instance has been captured
        for the serial port's Windows HANDLE, for the pyserial 3.x library.
        """
        port = TestableSerialPort3x(self.protocol, "COM3", self.reactor)
        self.assertEqual(35, port._serialHandle)
