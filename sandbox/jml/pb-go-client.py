import sys, random
from twisted.cred import credentials
from twisted.spread import pb

class RandomPlayer:
    def __init__(self, name):
        self.name = name

    def login(self, host, port, pword):
        self.factory = pb.PBClientFactory()
        d = self.factory.login(credentials.UsernamePassword(self.name, pword))
        d.addCallbacks(self.loggedIn, disaster)

        from twisted.internet import reactor
        reactor.connectTCP(host, int(port), self.factory)

    def loggedIn(self, perspective):
        self.perspective = perspective
        d = self.perspective.callRemote('getBoardSize')
        d.addCallbacks(self.gotSize, disaster)
        return d

    def gotSize(self, size):
        self.boardSize = size
        x = random.randrange(size)
        y = random.randrange(size)
        d = self.perspective.callRemote('move', x, y)
        d.addCallbacks(self.madeMove, disaster)
        return d

    def madeMove(self, ignored):
        d = self.perspective.callRemote('getBoard')
        d.addCallbacks(self.displayBoard, disaster)
        d.addCallbacks(self.quit, disaster)
        return d

    def displayBoard(self, board):
        print board

    def quit(self, ignored):
        from twisted.internet import reactor
        self.factory.disconnect()
        reactor.stop()
        
        

def disaster(failing):
    print failing
    sys.exit(-1)

def main(host, port, username, password):
    from twisted.internet import reactor
    player = RandomPlayer(username)
    player.login(host, int(port), password)
    reactor.run()

if __name__ == '__main__':
    main(*(sys.argv[1:5]))
    
