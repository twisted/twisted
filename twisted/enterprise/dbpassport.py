
from twisted.enterprise import adbapi
from twisted.internet import passport
import base64
import string

class DatabaseAuthorizer(passport.Authorizer, adbapi.Augmentation):
    """A PyPgSQL authorizer for Twisted Internet Passport
    """
    
    schema = """
    CREATE TABLE identities (identity_name varchar(64) PRIMARY KEY,
                             password      varchar(64));
    CREATE TABLE services (service_name varchar(64) PRIMARY KEY);
    CREATE TABLE perspectives (identity_name varchar(64) NOT NULL,
                               perspective_name varchar(64) NOT NULL,
                               service_name varchar(64) NOT NULL,
                               perspective_type varchar(64));
    """

    def addIdentity(self, identity, callback=None, errback=None):
        """Create an identity.
        """
        passwd = base64.encodestring(identity.hashedPassword)
        usernm = identity.name
        createIdentity = "INSERT INTO identities VALUES ('%s', '%s')" % (usernm, passwd)
        s = [createIdentity]
        for (svcname, pname), one in identity.keyring.items():
            # note, we don't actually know perspective type at this point...
            s.append("INSERT INTO perspectives VALUES ('%s', '%s', '%s', NULL)" % (usernm, pname, svcname))
        sql = string.join(s, '; \n')
        return self.runOperation(sql, callback, errback)

    def removeIdentity(self, identityName):
        """Identities should not be removed through this interface!
        """
        raise NotImplementedError()

    def getIdentityRequest(self, name):
        """This name corresponds to the 'source_name' column of the metrics_sources table.
        Check in that table for a corresponding entry.
        """ 
        print "getIdentityRequest for ", name
        sql = """
        SELECT identities.identity_name, identities.password, perspectives.perspective_name, perspectives.service_name
        FROM identities, perspectives
        WHERE identities.identity_name = perspectives.identity_name
              AND identities.identity_name = '%s'
        """ % name
        return self.runQuery(sql, self.gotIdentityData, self.gotIdentityError)

    def gotIdentityData(self, identData):
        realIdentName = identData[0][0]
        base64pass = identData[0][1]
        hashedPass = base64.decodestring(base64pass)
        i = passport.Identity(realIdentName, self.application)
        i.setAlreadyHashedPassword(hashedPass)
        for ign, ign2, pname, sname in identData:
            i.addKeyByString(pname, sname)
        return i

    def gotIdentityError(self, err):
        raise Exception("Database Error: "+str(err))

