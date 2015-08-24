# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


from twisted.internet.endpoints import (
    _SystemdParser, _TCP6ServerParser, _StandardIOParser,
    _TLSClientEndpointParser, _TLSWrapperClientEndpointParser)

systemdEndpointParser = _SystemdParser()
tcp6ServerEndpointParser = _TCP6ServerParser()
stdioEndpointParser = _StandardIOParser()
tlsClientEndpointParser = _TLSClientEndpointParser()
tlsWrapperClientEndpointParser = _TLSWrapperClientEndpointParser()
