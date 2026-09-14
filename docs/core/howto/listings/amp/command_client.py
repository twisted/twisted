if __name__ == "__main__":
    import command_client

    raise SystemExit(command_client.main())

from sys import stdout

from basic_client import connect

from twisted.internet import reactor
from twisted.protocols.amp import Command, Integer, String, Unicode
from twisted.python.log import err, startLogging


class UsernameUnavailable(Exception):
    pass


class RegisterUser(Command):
    arguments = [("username", Unicode()), ("publickey", String())]

    response = [("uid", Integer())]

    errors = {UsernameUnavailable: "username-unavailable"}


def main():
    startLogging(stdout)

    d = connect()

    def connected(protocol):
        return protocol.callRemote(
            RegisterUser,
            username="alice",
            publickey="ssh-rsa AAAAB3NzaC1yc2 alice@actinium",
        )

    d.addCallback(connected)

    def registered(result):
        print("Registration result:", result)

    d.addCallback(registered)

    d.addErrback(err, "Failed to register")

    def finished(ignored):
        reactor.stop()

    d.addCallback(finished)

    reactor.run()
