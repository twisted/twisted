#! /usr/bin/python

from twisted.internet.protocol import Protocol, Factory

class OneTimeKey(Protocol):
    def connectionMade(self):
        key = self.factory.nextkey
        print "giving key", key
        self.factory.nextkey += 1
        self.transport.write("%d\n" % key)
        self.transport.loseConnection()

def main():
    # namespaces are weird. if we used OneTimeKey directly, it would
    # pickle the instance as __main__.OneTimeKey, since we run this
    # module directly. So we reimport this module so the pickle refers
    # to it by its real name.
    import app3
    from twisted.internet.app import Application
    f = Factory()
    f.protocol = app3.OneTimeKey
    f.nextkey = 0
    app = Application("otk")
    app.listenTCP(8123, f)
    app.save("start")


if __name__ == '__main__':
    main()
    
