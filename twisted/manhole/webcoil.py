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

import types
import sys
import string

from twisted.web import widgets
from twisted.python import roots
from twisted.python.plugin import getPlugIns
from twisted.web import widgets, html
from twisted.protocols import protocol, http

import coil

class ConfigRoot(widgets.Gadget, widgets.Widget):
    def __init__(self, application):
        widgets.Gadget.__init__(self)
        self.putWidget("config", Configurator(application))
        self.putWidget('plugin', PluginLoader())
        self.addFile("images")

    def display(self, request):
        request.setResponseCode(http.FOUND)
        request.setHeader("location",
                          request.prePathURL() + 'config')
        return ['no content']


class PluginLoader(widgets.Form):
    def getFormFields(self, request):
        plugins = getPlugIns("coil")
        mnuList = []
        for plugin in plugins:
            if not plugin.isLoaded():
                mnuList.append([plugin.module, plugin.name])
            else:
                mnuList.append([plugin.module, plugin.name + ' (already loaded)'])
        return [['menu', 'Plugin to load?', 'pluginToLoad', mnuList]]

    def process(self, write, request, submit, pluginToLoad):
        plugins = getPlugIns('coil')
        for plugin in plugins:
            print plugin.module
            if plugin.module == pluginToLoad:
                write( 'loaded ' + plugin.module + '('+pluginToLoad+')' )
                plugin.load()
                break
        else:
            write( 'could not load' + plugin.module )

class Configurator(widgets.Presentation):
    """A web configuration interface for Twisted.

    This configures the toplevel application.
    """
    def __init__(self, app):
        widgets.Presentation.__init__(self)
        self.app = app
        # mapping of config class names to lists of tuples of (callable
        # object that can create the class, descriptive string)
        self.dispensers = {}
        self.dispenseMethods = {}

    template = '''
    <center>
    <table width="95%">
    <tr><td width="20%" valign="top">%%%%self.streamCall(self.displayTree, request)%%%%</td>
    <td width="80%" valign="top">%%%%self.configd%%%%</td></tr>
    </table>
    </center>
    '''
    isLeaf = 1
    
    def displayTree(self, write, request):
        self.displayTreeElement(write,
                                str(self.app),
                                "config",
                                self.app)

    def displayTreeElement(self, write, inName, inPath, collection, indentLevel=0):
        subIndent = indentLevel + 1
        for name, entity in collection.listStaticEntities():
            if isinstance(entity, roots.Collection):
                write('%s + <a href="%s/%s">%s</a> <br>' %
                      (indentLevel * '&nbsp;', inPath, name, name))
                self.displayTreeElement(write, name, '%s/%s' % (inPath, name), entity, subIndent)
            else:
                write("%s. %s <br>" % (subIndent * '&nbsp;', name))

    def prePresent(self, request):
        self.configd = self.configWidget(request)

    def configWidget(self, request):
        # displaying the widget
        path = request.postpath
        if path:
            obj = self.app
            for elem in path:
                if elem:                # '' doesn't count
                    obj = obj.getStaticEntity(elem)
                    if obj is None:
                        request.setResponseCode(http.MOVED_PERMANENTLY)
                        request.setHeader('location', request.prePathURL())
                        return ['Redirecting...']
        else:
            obj = self.app
        ret = []
        linkfrom = string.join(['config']+request.postpath, '/') + '/'
        if isinstance(obj, coil.Configurable) and obj.configTypes:
            ret.extend(widgets.TitleBox("Configuration", ConfigForm(self, obj, linkfrom)).display(request))
        if isinstance(obj, roots.Homogenous): # and isinstance(obj.entityType, coil.Configurable):
            ret.extend(widgets.TitleBox("Listing", CollectionForm(self, obj, linkfrom)).display(request))
        ret.append(html.PRE(str(obj)))
        return ret

    def makeConfigMenu(self, cfgType):
        l = []
        for claz in coil.theClassHierarchy.getSubClasses(cfgType, 1):
            if issubclass(claz, coil.Configurable) and claz.configCreatable:
                nm = getattr(claz, 'configName', None) or str(claz)
                l.append(['new '+str(claz), 'new '+nm])
        for methId, desc in self.dispensers.get(cfgType, []):
            l.append(['dis '+str(methId), desc])
        return l

    def makeConfigurable(self, cfgInfo, container, name):
        cmd, args = string.split(cfgInfo, ' ', 1)
        if cmd == "new": # create
            obj = coil.createConfigurable(coil.getClass(args), container, name)
        elif cmd == "dis": # dispense
            methodId = int(args)
            obj = self.dispenseMethods[methodId]()
        if isinstance(obj, coil.Configurable):
            for methodName, klass, desc in obj.configDispensers:
                supclas = coil.theClassHierarchy.getSuperClasses(klass, 1) + (klass,)
                for k in supclas:
                    if not self.dispensers.has_key(k):
                        self.dispensers[k] = []
                    meth = getattr(obj, methodName)
                    self.dispensers[k].append([id(meth), desc])
                    self.dispenseMethods[id(meth)] = meth
        return obj

class ConfigForm(widgets.Form):
    def __init__(self, configurator, cfgr, linkfrom):
        self.configurator = configurator
        self.cfgr = cfgr
        self.linkfrom = linkfrom
    
    submitNames = ['Configure']
    
    def getFormFields(self, request):
        existing = self.cfgr.getConfiguration()
        allowed = self.cfgr.configTypes
        myFields = []
        for name, cfgType in allowed.items():
            current = existing.get(name)
            if isinstance(cfgType, types.ClassType):
                inputType = 'menu'
                inputValue = self.configurator.makeConfigMenu(cfgType)
                if current:
                    inputValue.insert(0, ['current', "Current Object"])
            elif cfgType == types.StringType:
                inputType = 'string'
                inputValue = current or ''
            elif cfgType == types.IntType:
                inputType = 'int'
                inputValue = str(current) or '0'
            elif cfgType == 'boolean':
                inputType = 'checkbox'
                inputValue = current
            else:
                inputType = 'string'
                inputValue = "<UNKNOWN>"
            # TODO: real display name
            myFields.append([inputType, name, name, inputValue])
        return myFields

    def process(self, write, request, submit, **values):
        existing = self.cfgr.getConfiguration()
        allowed = self.cfgr.configTypes
        created = {}
        for name, cfgInfo in values.items():
            write(str((name, cfgInfo)) + "<br>")
            if isinstance(allowed[name], types.ClassType):
                if cfgInfo == 'current':
                    continue
                created[name] = self.configurator.makeConfigurable(cfgInfo, self.cfgr, name)
                print 'instantiated', created[name]
            else:
                created[name] = cfgInfo
        try:
            self.cfgr.configure(created)
            self.format(self.getFormFields(request), write, request)
        except coil.InvalidConfiguration, ic:
            raise widgets.FormInputError(ic)


class CollectionForm(widgets.Form):
    def __init__(self, configurator, coll, linkfrom):
        self.configurator = configurator
        self.coll = coll
        self.linkfrom = linkfrom

    submitNames = ['Insert', 'Delete']

    def getFormFields(self, request):
        itemlst = []
        for name, val in self.coll.listStaticEntities():
            itemlst.append([name, '%s: <a href="%s">%s</a>' %
                            (name, self.linkfrom+name,
                             html.escape(repr(val))), 0])
        result = []
        if itemlst:
            result.append(['checkgroup', 'Items in Set<br>(Select to Delete)',
                           'items', itemlst])
        result.append(['string', "%s to Insert" %
                       self.coll.getNameType(), "name", ""])
        result.append(['menu', "%s to Insert" % self.coll.getEntityType(), "type", self.configurator.makeConfigMenu(self.coll.entityType)])
        return widgets.Form.getFormFields(self, request, result)

    def process(self, write, request, submit, name, type, items=()):
        # write(str(('YAY', name, type)))
        # TODO: validation on the name?
        if submit == 'Delete':
            try:
                for item in items:
                    self.coll.delEntity(item)
            except:
                raise widgets.FormInputError(str(sys.exc_info()[1]))
            write("<b>Items Deleted.</b><br>(%s)<br>" % html.escape(repr(items)))
        else:
            try:
                obj = self.configurator.makeConfigurable(type, self.coll, name)
                self.coll.putEntity(name, obj)
            except:
                raise widgets.FormInputError(str(sys.exc_info()[1]))
            write("<b>%s created!</b>" % type)
        self.format(self.getFormFields(request), write, request)

