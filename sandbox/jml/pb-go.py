from twisted.cred import checkers, portal
from twisted.spread import pb

class GoException(Exception):
    """Raised when a violation of the rules of Go is detected."""

class Board:
    """I represent something like a Go board."""

    size = 19
   
    def __init__(self):
        self.board = {}
        self.players = {}

    def addPlayer(self, name):
        if name not in self.players.keys():
            p = Player(name, self)
            self.players[name] = p
            return p

    def getPlayer(self, name):
        return self.players[name]

    def playStone(self, x, y, side):
        if self.board.has_key((x, y)):
            raise GoException(
                   "A stone has already been played at %d, %d" % (x, y))
        if 0 <= x < self.size and 0 <= y < self.size:
            self.board[(x, y)] = side
        else:
            raise ValueError("%d, %d is not a valid position" % (x, y))


class Player(pb.Perspective):
    """A represent a Go player."""
    __implements__ = pb.IPerspective,

    def __init__(self, name, board):
        self.name = name
        self.board = board

    def __repr__(self):
        return "Player(%s)" % (self.name,)
    
    def logout(self):
        print "%r has logged out." % (self,)

    def perspective_move(self, x, y):
        self.board.playStone(x, y, self.name)

    def perspective_getBoard(self):
        return self.board.board

    def perspective_getBoardSize(self):
        return self.board.size


class MyRealm:
    __implements__ = portal.IRealm

    def __init__(self, game):
        self.game = game

    def requestAvatar(self, avatarId, mind, *interfaces):
        if pb.IPerspective in interfaces:
            try:
                player = self.game.getPlayer(avatarId)
            except KeyError:
                player = self.game.addPlayer(avatarId)
            return pb.IPerspective, player, player.logout
        else:
            raise NotImplementedError, "I only do PB"




def main():
    from twisted.internet import reactor
    checker = checkers.InMemoryUsernamePasswordDatabaseDontUse()
    checker.addUser("alice", "pass1")
    checker.addUser("bob", "pass2")

    board = Board()

    myPortal = portal.Portal(MyRealm(board))
    myPortal.registerChecker(checker)

    factory = pb.PBServerFactory(myPortal)
    reactor.listenTCP(8787, factory)
    reactor.run()

if __name__ == '__main__':
    main()
