
from twisted.spread import pb
from twisted.python import delay, authenticator
import string

class dbService(pb.Service):
    def __init__(self, dbManager):
        self.dbManager = dbManager

    def getPerspectiveNamed(self, name):
        # TODO - player checking
        print "Player %s connecting" % name
        newUser = self.dbManager.loginUser(name)
        return newUser

    def getPassword(self, name):
        """Asks the dbManager to look up this username in the database and find the
        password. If the user does not exist, the password will be None and we raise
        an exception.
        """
        password = self.dbManager.getPassword(name)
        if password:
            print "Password for '%s' is '%s' " %( name, password)
            return password
        else:
            raise KeyError("Bad Login")


