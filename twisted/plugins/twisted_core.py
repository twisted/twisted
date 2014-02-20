# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


from twisted.internet.endpoints import (_SystemdParser, _TCP6ServerParser, _StandardIOParser,
                                        _TCP4ServerParser, _TCP4ClientParser, _UNIXServerParser,
                                        _UNIXClientParser, _SSL4ServerParser, _SSL4ClientParser)

systemdEndpointParser = _SystemdParser()
tcp4ServerEndpointParser = _TCP4ServerParser()
tcp6ServerEndpointParser = _TCP6ServerParser()
stdioEndpointParser = _StandardIOParser()
tcp4ClientParser = _TCP4ClientParser()
unixServerEndpointParser = _UNIXServerParser()
unixClientEndpointParser = _UNIXClientParser()
ssl4ServerEndpointParser = _SSL4ServerParser()
ssl4ClientEndpointParser = _SSL4ClientParser()

