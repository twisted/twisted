# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
# 
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
# 
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

from twisted.enterprise import adbapi
from twisted.cred import authorizer, identity
import base64
import string

class DatabaseAuthorizer(authorizer.Authorizer, adbapi.Augmentation):
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

    def __init__(self, dbpool, serviceCollection=None):
        authorizer.Authorizer.__init__(self, serviceCollection)
        self.perspectiveCreators = {}
        adbapi.Augmentation.__init__(self, dbpool)

    def addIdentity(self, identity):
        """Create an identity.
        """
        passwd = base64.encodestring(identity.hashedPassword)
        username = identity.name
        createIdentity = "INSERT INTO twisted_identities VALUES ('%s', '%s')" % (adbapi.safe(username), adbapi.safe(passwd) )
        s = [createIdentity]
        for (svcname, pname) in identity.keyring.keys():
            # note, we don't actually know perspective type at this point...
            s.append("INSERT INTO twisted_perspectives VALUES ('%s', '%s', '%s', NULL)" %
                     (adbapi.safe(username), adbapi.safe(pname), adbapi.safe(svcname)) )
        sql = string.join(s, '; \n')
        return self.runOperation(sql)


    def getIdentityRequest(self, name):
        """This name corresponds to the 'source_name' column of the metrics_sources table.
        Check in that table for a corresponding entry.
        """
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
        return self.runQuery(sql).addCallbacks(self._cbIdentity)

    def _cbIdentity(self, identData):
        if len(identData) == 0:
            # no rows! User doesnt exist
            raise KeyError("Identity not found")

        realIdentName = identData[0][0]
        base64pass = identData[0][1]
        hashedPass = base64.decodestring(base64pass)
        i = identity.Identity(realIdentName, self)
        i.setAlreadyHashedPassword(hashedPass)
        for ign, ign2, pname, sname in identData:
            i.addKeyByString(sname, pname)
        return i

    #################### Web Admin Interface Below ##############################

    def getIdentities(self):
        """Get the identies in the db. Used by web admin interface.
        """
        sql="""SELECT identity_name, password, (SELECT count(*)
                                                FROM twisted_perspectives
                                                WHERE twisted_perspectives.identity_name = twisted_identities.identity_name)
               FROM twisted_identities"""
        return self.runQuery(sql)

    def getPerspectives(self, identity_name):
        """Get the perspectives for an identity. Used by the web admin interface.
        """
        sql="""SELECT identity_name, perspective_name, service_name
               FROM twisted_perspectives
               WHERE identity_name = '%s'""" % adbapi.safe(identity_name)
        return self.runQuery(sql)

    def getServices(self):
        """Get the known services. Used by the web admin interface.
        """
        sql="""SELECT service_name FROM twisted_services"""
        return self.runQuery(sql)

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

    def removeIdentity(self, identityName):
        """Delete an identity
        """
        sql = """DELETE FROM twisted_identities WHERE identity_name = '%s';
                 DELETE FROM twisted_perspectives WHERE identity_name = '%s'""" %\
                     (adbapi.safe(identityName), adbapi.safe(identityName) )
        return self.runOperation(sql)

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
