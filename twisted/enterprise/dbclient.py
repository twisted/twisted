from twisted.internet import tcp, main
from twisted.spread import pb


class clientCollector(pb.Referenced):

    def __init__(self, player):
        self.player = player
        self.count = 0

    def remote_gotData(self, data):
        print "Got some data:" , self.count
        self.player.request("select * from accounts", self)
        self.count = self.count + 1

class DbClient:

    def __init__(self, host, name, password):
        self.host = host
        self.name = name
        self.password = password
        self.player = None
        self.count = 0

    def doLogin(self):
        self.client = pb.Broker()
        tcp.Client(self.host, 27777, self.client)
        
        self.client.requestIdentity("twisted",  # username
                                    "matrix",  # password
                                    callback = self.preConnected,
                                    errback  = self.couldntConnect)

    def couldntConnect(self, arg):
        print "Could not connect.", arg

    def preConnected(self, identity):
        identity.attach("twisted.enterprise.db", None, pbcallback=self.gotConnection, pberrback=self.couldntConnect)

    def gotConnection(self, player):
        print 'connected:', player
        self.player = player
	self.collector = clientCollector(player)
        self.player.request("select * from accounts", self.collector)



def run():
    c = DbClient("localhost", "twisted", "matrix")
    c.doLogin()
    main.run()

    

if __name__ == '__main__':
    run()


