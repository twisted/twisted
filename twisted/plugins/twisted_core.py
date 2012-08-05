# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


from twisted.internet.endpoints import _SystemdParser, _TCP6ServerParser
from twisted.internet.endpoints import _StandardIOParser, _TCP6ClientParser

systemdEndpointParser = _SystemdParser()
tcp6ServerEndpointParser = _TCP6ServerParser()
stdioEndpointParser = _StandardIOParser()
tcp6ClientParser = _TCP6ClientParser()
