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

import os

from twisted.internet import defer
from twisted.enterprise import reflector
from twisted.enterprise.util import _TableInfo

from twisted.persisted import marmalade


class XMLRowProxy:
    """Used to persist Row Objects as XML.
    """
    def __init__(self, rowObject):
        self.kw = {}
        for columnName, type  in rowObject.rowColumns:
            self.kw[columnName] = getattr(rowObject, columnName)

class XMLReflector(reflector.Reflector):
    """Reflector for twisted.enterprise that uses XML files.

    WARNING: this is an experimental piece of code. this reflector
    does not function completely yet! it is also very very slow.
    """

    extension = ".xml"
    
    def __init__(self, baseDir, rowClasses):
        self.baseDir = baseDir
        try:
            os.mkdir(baseDir)
        except OSError, e:
            #print "Base Directory %s already exists" % baseDir
            pass
        self.tableDirs = {}
        reflector.Reflector.__init__(self, rowClasses)        

    def _populate(self):
        """load schema data
        """
        for rc in self.rowClasses:
            newDir = self.baseDir+"/"+rc.rowTableName
            self.tableDirs[rc.rowTableName] = newDir
            try:
                os.mkdir(newDir)
            except OSError, e:
                #print "Directory %s already exists." % newDir
                pass

            tableInfo = _TableInfo(rc)
            self.populateSchemaFor(tableInfo)

    def _rowLoader(self, tableName, parentRow, data,
                   whereClause, forceChildren):
        d = self.tableDirs[ tableName]
        tableInfo = self.schema[tableName]
        filenames = os.listdir(d)
        results = []
        newRows = []
        for filename in filenames:
            if (filename.find(self.extension) !=
                len(filename) - len(self.extension)):
                continue
            f = open(d + "/" + filename, "r")
            proxy = marmalade.unjellyFromXML(f)
            f.close()
            # match object with whereClause... NOTE: this is insanely slow..
            # every object in the directory is loaded and checked!
            stop = 0
            if whereClause:
                for item in whereClause:
                    (columnName, cond, value) = item
                    #TODO: just do EQUAL for now
                    if proxy.kw[columnName] != value:
                        stop = 1
            if stop:
                continue
            # find the row in the cache or add it
            resultObject = self.findInCache(tableInfo.rowClass, proxy.kw)
            if not resultObject:
                resultObject = tableInfo.rowFactoryMethod[0](
                                       tableInfo.rowClass, data, proxy.kw)
                self.addToCache(resultObject)
                newRows.append(resultObject)
            results.append(resultObject)

        # add these rows to the parentRow if required
        if parentRow:
            self.addToParent(parentRow, newRows, tableName)

        # load children or each of these rows if required
        for relationship in tableInfo.relationships:
            if not forceChildren and not relationship.autoLoad:
                continue
            for row in results:
                # build where clause
                childWhereClause = self.buildWhereClause(relationship, row)             
                # load the children immediately, but do nothing with them
                self._rowLoader(relationship.childRowClass.rowTableName, row, data, childWhereClause, forceChildren)

        return results

    def makeFilenameFor(self, rowObject):
        s =""
        keys = rowObject.getKeyTuple()
        for k in keys[1:]:
            s += str(k)
        return self.tableDirs[ rowObject.rowTableName ] + "/" + s + ".xml"            

    ############### public interface  ######################

    def loadObjectsFrom(self, tableName, parentRow = None, data = None, whereClause = None, forceChildren = 1):
        """The whereClause for XML loading is [(columnName, operation, value)] list of tuples
        """
        if parentRow and whereClause:
            raise DBError("Must specify one of parentRow _OR_ whereClause")
        if parentRow:
            info = self.getTableInfo(parentRow)
            relationship = info.getRelationshipFor(tableName)
            whereClause = self.buildWhereClause(relationship, parentRow)
        elif whereClause:
            pass
        else:
            whereClause = []
        results = self._rowLoader(tableName, parentRow, data,
                                  whereClause, forceChildren)
        return defer.succeed(results)

    def updateRow(self, rowObject):
        """update this rowObject to the database.
        """
        # just replace the whole file for now
        return self.insertRow(rowObject)

    def insertRow(self, rowObject):
        """insert a new row for this object instance. do not include the "container" attribute.
        """
        proxy = XMLRowProxy(rowObject)
        filename = self.makeFilenameFor(rowObject)
        f = open(filename,"w")
        marmalade.jellyToXML(proxy, f)
        f.close()
        return defer.succeed(1)

    def deleteRow(self, rowObject):
        """delete the row for this object from the database.
        """
        filename = self.makeFilenameFor(rowObject)        
        os.remove(filename)
        return defer.succeed(1)
