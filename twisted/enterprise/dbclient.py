from twisted.internet import tcp, main
from twisted.spread import pb


class DbClient:

    def __init__(self, host, name, password):
        self.host = host
        self.name = name
        self.password = password
        self.player = None
        self.count = 0

    def doLogin(self):
        self.client = pb.Broker()
        self.client.requestPerspective("db", self.name, self.password, None, self.gotConnection)
        tcp.Client(self.host, 8787, self.client)
        
    def gotConnection(self, player):
        print 'connected:', player
        self.player = player
        self.player.request("select * from accounts", pbcallback=self.gotData)


    def gotData(self, data):
        print "got Data back %d  %d rows" % (self.count, len(data))
        self.count = self.count + 1
        # do it again!
        self.player.request("select * from accounts", pbcallback=self.gotData)    
        

def run():
    c = DbClient("localhost", "sean", "test")
    c.doLogin()
    main.run()

    

if __name__ == '__main__':
    run()
