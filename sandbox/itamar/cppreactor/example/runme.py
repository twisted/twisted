from twisted.internet import reactor, protocol
import fusion
import echo
fusion.install()


def main():
    f = protocol.ServerFactory()
    f.buildProtocol = lambda _: echo.Echo()
    reactor.listenTCP(1234, f)
    reactor.run()


if __name__ == '__main__':
    main()
