import os
import copy

from twisted.internet import defer
from twisted.enterprise.reflector import Reflector
from twisted.enterprise.util import _TableInfo

from twisted.persisted import marmalade

class XMLReflector(Reflector):
    """Reflector for twisted.enterprise that uses XML files.

    WARNING: this is an experimental piece of code. this reflector
    does not function completely yet! it is also very very slow.
    """
    
    def __init__(self, baseDir, rowClasses, populatedCallback=None):
        self.baseDir = baseDir
        try:
            os.mkdir(baseDir)
        except OSError, e:
            print "Base Directory %s already exists" % baseDir
        self.tableDirs = {}
        Reflector.__init__(self, rowClasses, populatedCallback)        

    def _really_populate(self):
        """load schema data
        """
        for rc in self.rowClasses:
            newDir = self.baseDir+"/"+rc.rowTableName
            self.tableDirs[rc.rowTableName] = newDir
            try:
                os.mkdir(newDir)
            except OSError, e:
                print "Directory %s already exists." % newDir

            tableInfo = _TableInfo(rc)
            self.populateSchemaFor(tableInfo)

        if self.populatedCallback:
            self.populatedCallback()
        
    def _loader(self, tableName, data, whereClause, parent):
        d = self.tableDirs[ tableName]
        filenames = os.listdir(d)
        results = []
        for filename in filenames:
            f = open(d + "/" + filename, "r")
            obj = marmalade.unjellyFromXML(f)
            f.close()
            # match object with whereClause... NOTE: this is insanely slow..
            # every object in the directory is loaded and checked!
            if whereClause:
                if getattr(obj, whereClause[0]) != whereClause[1]:
                    continue
            results.append(obj)

        if parent:
            if hasattr(parent, "container"):
                parent.container.extend(results)
            else:
                setattr(parent, "container", results)

        # load any child rows
        for newRow in results:
            for relationship in self.schema[ newRow.rowTableName ].childTables:
                # build whereClause
                w = (relationship.childColumns[0][0], getattr(newRow, relationship.parentColumns[0][0]) )
                self._loader(relationship.childTableName, data, w, newRow)

        return results

    def makeFilenameFor(self, rowObject):
        s =""
        keys = rowObject.getKeyTuple()
        for k in keys[1:]:
            s += str(k)
        return self.tableDirs[ rowObject.rowTableName ] + "/" + s + ".xml"            

    ############### public interface  ######################

    def loadObjectsFrom(self, tableName, data = None, whereClause = None, parent = None):
        """The whereClause for XML loading is (columnName, value) tuple
        """
        results = self._loader(tableName, data, whereClause, None)
        return defer.succeed(results)
    
    def updateRow(self, rowObject):
        """update this rowObject to the database.
        """
        # just replace the whole file for now
        return self.insertRow(rowObject)
        
    def insertRow(self, rowObject):
        """insert a new row for this object instance. dont include the "container" attribute.
        """
        temp = copy.copy(rowObject)
        if hasattr(temp, "container"):
            del temp.container

        filename = self.makeFilenameFor(temp)
        f = open(filename,"w")
        marmalade.jellyToXML(temp, f)
        f.close()
        return defer.succeed(1)
        
    def deleteRow(self, rowObject):
        """delete the row for this object from the database.
        """
        filename = self.makeFilenameFor(rowObject)        
        os.remove(filename)
        return defer.succeed(1)

    def selectRow(self, rowObject):
        """load this rows current values from the database.
        """
        filename = self.makeFilenameFor(rowObject)
        f = open(filename, "r")
        obj = marmalade.unjellyFromXML(f)
        f.close()
        return defer.succeed(obj)


