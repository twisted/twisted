from twisted.internet import reactor, protocol
from fusion import creactor
import echo


class PyEcho(echo.Echo):

    def connectionMade(self):
        print "pymade"
        echo.Echo.connectionMade(self)

    def connectionLost(self, reason):
        print "pylost"
        echo.Echo.connectionLost(self, reason)


def main():
    f = protocol.ServerFactory()
    f.buildProtocol = lambda _: PyEcho()
    creactor.listenTCP(1234, f)
    reactor.run()


if __name__ == '__main__':
    main()
