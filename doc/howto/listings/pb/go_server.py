#! /usr/bin/python

import twisted.internet.app
from twisted.cred.authorizer import DefaultAuthorizer
from twisted.spread import pb
from twisted.internet import defer

class GoGameError(pb.Error):
    """Something went wrong in the GoGame"""
    pass

class GoGame:
    def __init__(self):
        self.board = {}
        self.numPlayers = 0
    def addPlayer(self):
        self.numPlayers += 1
    def haveQuorum(self):
        if self.numPlayers == 2:
            return 1
        return 0
    def getBoard(self):
        return self.board # a dict, with the state of the board
    def moveIsLegal(self, x, y, player):
        return 1 # yeah, sure, why not
    def gameIsOver(self):
        return 0 # no, not yet
    def move(self, x, y, playerName):
        if not self.haveQuorum():
            raise GoGameError("NeedMorePlayers")
        if self.moveIsLegal(x, y, playerName):
            self.board[x,y] = playerName
            if self.gameIsOver():
                return "game over"
            else:
                return "ok"
        else:
            raise GoGameError("IllegalMove")
        

class Player(pb.Perspective):
    def __init__(self, perspectiveName, identityName="Nobody"):
        pb.Perspective.__init__(self, perspectiveName, identityName)
    def setGame(self, game):
        self.game = game

    def attached(self, clientref, identity):
        print "player '%s' joining game on side '%s'" % \
              (identity.name, self.perspectiveName)
        self.identity = identity
        self.game.addPlayer()
        return self
    def detached(self, clientref, identity):
        return self
    
    def perspective_getBoard(self):
        return self.game.getBoard()
    def perspective_makeMove(self, x, y):
        print "player '%s' [%s] moving at %d,%d" % (self.identity.name,
                                                    self.perspectiveName,
                                                    x, y)
        return self.game.move(self.perspectiveName, x, y)
    

class GoService(pb.Service):
    def __init__(self, serviceName, serviceParent=None, authorizer=None,
                 application=None):
        pb.Service.__init__(self, serviceName, serviceParent, authorizer,
                            application)
        self.sides = { 'black': None, 'white': None }
        self.game = GoGame()
        
    def getPerspectiveRequest(self, name):
        # players are allowed to to choose any side that hasn't already been
        # taken
        if name not in ('black', 'white'):
            return defer.fail(GoGameError("No such side '%s'" % name))
        if self.sides[name]:
            return defer.fail(GoGameError("That side is already taken"))
        player = Player(name)
        player.setGame(self.game)
        self.sides[name] = player
        return defer.succeed(player)

def setup_players(auth, players):
    for (name, pw) in players:
        i = auth.createIdentity(name)
        i.setPassword(pw)
        i.addKeyByString("goservice", "black")
        i.addKeyByString("goservice", "white")
        i.addKeyByString("goservice", "bogus")
        auth.addIdentity(i)
        

def main():
    app = twisted.internet.app.Application("go_server")
    auth = DefaultAuthorizer(app)
    service = GoService("goservice", app, auth)
    players = [["alice", "sekrit"],
               ["bob", "b0b"],
               ["charlie", "chuck"],
               ["david", "password"],
               ]
    setup_players(auth, players)

    # start the application
    app.listenTCP(8800, pb.BrokerFactory(pb.AuthRoot(auth)))
    app.run()

if __name__ == '__main__':
    main()
