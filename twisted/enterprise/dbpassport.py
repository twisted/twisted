
from twisted.enterprise import adbapi
from twisted.internet import passport
import base64
import string

class DatabaseAuthorizer(passport.Authorizer, adbapi.Augmentation):
    """A PyPgSQL authorizer for Twisted Internet Passport
    """
    
    schema = """
    CREATE TABLE twisted_identities
    (
      identity_name     varchar(64) PRIMARY KEY,
      password          varchar(64)
    );
    
    CREATE TABLE twisted_services
    (
      service_name      varchar(64) PRIMARY KEY
    );
    
    CREATE TABLE twisted_perspectives
    (
      identity_name     varchar(64) NOT NULL,
      perspective_name  varchar(64) NOT NULL,
      service_name      varchar(64) NOT NULL,
      perspective_type  varchar(64)
    );
     
    """

    def __init__(self, dbpool):
        self.perspectiveCreators = {}
        adbapi.Augmentation.__init__(self, dbpool)
        
    def addIdentity(self, identity):
        """Create an identity.
        """
        print "Creating identity", identity
        passwd = base64.encodestring(identity.hashedPassword)
        username = identity.name
        createIdentity = "INSERT INTO twisted_identities VALUES ('%s', '%s')" % (adbapi.safe(username), adbapi.safe(passwd) )
        s = [createIdentity]
        for (svcname, pname), one in identity.keyring.items():
            # note, we don't actually know perspective type at this point...
            s.append("INSERT INTO twisted_perspectives VALUES ('%s', '%s', '%s', NULL)" %
                     (adbapi.safe(username), adbapi.safe(pname), adbapi.safe(svcname)) )
        sql = string.join(s, '; \n')
        return self.runOperation(sql)


    def getIdentityRequest(self, name):
        """This name corresponds to the 'source_name' column of the metrics_sources table.
        Check in that table for a corresponding entry.
        """ 
        print "getIdentityRequest for ", name
        sql = """
        SELECT   twisted_identities.identity_name,
                 twisted_identities.password,
                 twisted_perspectives.perspective_name,
                 twisted_perspectives.service_name
        FROM     twisted_identities,
                 twisted_perspectives
        WHERE    twisted_identities.identity_name = twisted_perspectives.identity_name
        AND      twisted_identities.identity_name = '%s'
        """ % adbapi.safe(name)
        return self.runQuery(sql, self.gotIdentityData, self.gotIdentityError)

    def gotIdentityData(self, identData):
        if len(identData) == 0:
            # no rows! User doesnt exist
            raise KeyError("Identity not found")

        realIdentName = identData[0][0]
        base64pass = identData[0][1]
        hashedPass = base64.decodestring(base64pass)
        i = passport.Identity(realIdentName, self.application)
        i.setAlreadyHashedPassword(hashedPass)
        for ign, ign2, pname, sname in identData:
            print "Adding Perspective", realIdentName, pname, sname
            i.addKeyByString(sname, pname)
        return i

    def gotIdentityError(self, err):
        raise Exception("Database Error: "+str(err))

    #################### Web Admin Interface Below ##############################

    def getIdentities(self, callbackIn, errbackIn):
        """Get the identies in the db. Used by web admin interface.
        """
        sql="""SELECT identity_name, password, (SELECT count(*)
                                                FROM twisted_perspectives
                                                WHERE twisted_perspectives.identity_name = twisted_identities.identity_name)
               FROM twisted_identities"""
        return self.runQuery(sql, callbackIn, errbackIn)                             

    def getPerspectives(self, identity_name, callbackIn, errbackIn):
        """Get the perspectives for an identity. Used by the web admin interface.
        """
        sql="""SELECT identity_name, perspective_name, service_name
               FROM twisted_perspectives
               WHERE identity_name = '%s'""" % adbapi.safe(identity_name)
        return self.runQuery(sql, callbackIn, errbackIn)                             

    def getServices(self, callbackIn, errbackIn):
        """Get the known services. Used by the web admin interface.
        """
        sql="""SELECT service_name FROM twisted_services"""
        return self.runQuery(sql, callbackIn, errbackIn)
    
    def addEmptyIdentity(self, identityName, hashedPassword, callback=None, errback=None):
        """Create an empty identity (no perspectives). Used by web admin interface.
        """
        passwd = base64.encodestring(hashedPassword)
        sql = "INSERT INTO twisted_identities VALUES ('%s', '%s')" % (adbapi.safe(identityName), adbapi.safe(passwd))
        return self.runOperation(sql).addCallbacks(callback, errback)

    def addPerspective(self, identityName, perspectiveName, serviceName, callback=None, errback=None):
        """Add a perspective by name to an identity.
        """
        sql = "INSERT INTO twisted_perspectives VALUES ('%s', '%s', '%s', NULL)" %\
                (adbapi.safe(identityName), adbapi.safe(perspectiveName), adbapi.safe(serviceName))
        return self.runOperation(sql).addCallbacks(callback, errback)


    def removeIdentity(self, identityName, callback=None, errback=None):
        """Delete an identity
        """
        sql = """DELETE FROM twisted_identities WHERE identity_name = '%s';
                 DELETE FROM twisted_perspectives WHERE identity_name = '%s'""" %\
                     (adbapi.safe(identityName), adbapi.safe(identityName) )
        return self.runOperation(sql).addCallbacks(callback, errback)

    def removePerspective(self, identityName, perspectiveName, callback=None, errback=None):
        """Delete a perspective for an identity
        """
        sql = """DELETE FROM twisted_perspectives
                 WHERE identity_name = '%s'
                 AND perspective_name = '%s'""" %\
                   (adbapi.safe(identityName), adbapi.safe(perspectiveName))
        return self.runOperation(sql).addCallbacks(callback, errback)

    def changePassword(self, identityName, hashedPassword, callback=None, errback=None):
        passwd = base64.encodestring(hashedPassword)        
        sql = """UPDATE twisted_identities
                 SET password = '%s'
                 WHERE identity_name = '%s'""" %\
                   (adbapi.safe(passwd), adbapi.safe(identityName) )
        return self.runOperation(sql).addCallbacks(callback, errback)
        
        
