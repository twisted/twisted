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
"""
Database backend for L{twisted.cred}.
This now deprecated, as it implements the old twisted.cred API.
"""

import base64
import string
import warnings

from twisted.enterprise import adbapi, row, reflector
from twisted.cred import authorizer, identity

warnings.warn("This is deprecated. The Cred API has changed.",
              DeprecationWarning)

class IdentityRow(row.RowObject):
    rowColumns     = [
        ("identity_name", "varchar"),
        ("password", "varchar")
        ]
    rowKeyColumns  = [("identity_name", "varchar")]
    rowTableName   = "twisted_identities"

class PerspectiveRow(row.RowObject):
    rowColumns     = [
        ("identity_name",    "varchar"),
        ("perspective_name", "varchar"),
        ("service_name",     "varchar"),
        ("perspective_type", "varchar")
        ]
    rowKeyColumns  = [("identity_name", "varchar"),
                      ("perspective_name","varchar"),
                      ("service_name", "varchar")]
    rowTableName   = "twisted_perspectives"
    rowForeignKeys = [("twisted_identities", [("identity_name","varchar")],[("identity_name","varchar")], None, 1)]

    def __repr__(self):
        return "identity: %s perspective: %s service: %s" % ( self.identity_name, self.perspective_name, self.service_name)

class ReflectorAuthorizer(authorizer.Authorizer):
    """An authorizer that uses a given row reflector.
    """
    def __init__(self, refl, serviceCollection=None):
        authorizer.Authorizer.__init__(self, serviceCollection)
        self.perspectiveCreators = {}
        self.reflector = refl

    def getIdentityRequest(self, name):
        """get the identity from the database with the specified name.
        """
        w=[("identity_name", reflector.EQUAL, name)]
        return self.reflector.loadObjectsFrom(
            "twisted_identities",
            whereClause=w,
            ).addCallbacks(self._cbIdentity, self._ebIdentity)

    def _ebIdentity(self, data):
        print "ERROR:", data
        raise KeyError("Failed to load identity")

    def _cbIdentity(self, newIdentityRows):
        if len(newIdentityRows) == 0:
            # no rows! User doesnt exist
            raise KeyError("Identity not found")

        irow = newIdentityRows[0]
        hashedPass = base64.decodestring(irow.password)

        i = identity.Identity(irow.identity_name, self)
        i.setAlreadyHashedPassword(hashedPass)
        i.rows = [] #keep the rows around for now...
        i.rows.append(irow)

        for prow in irow.childRows:
            i.addKeyByString(prow.service_name, prow.perspective_name)
            i.rows.append(prow) #keep the rows around for now...

        return i

class DatabaseAuthorizer(authorizer.Authorizer, adbapi.Augmentation):
    """A PyPgSQL authorizer for Twisted Cred
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
        """Store an identity in the database.
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
        """get the identity from the database with the specified name.
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
        """Get the identities in the db. Used by web admin interface.
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
