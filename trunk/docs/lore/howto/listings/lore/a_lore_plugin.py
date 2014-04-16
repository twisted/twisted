
from zope.interface import implements

from twisted.plugin import IPlugin
from twisted.lore.scripts.lore import IProcessor

class MyHTML(object):
    implements(IPlugin, IProcessor)

    name = "myhtml"
    moduleName = "myhtml.factory"
