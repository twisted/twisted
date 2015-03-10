
from zope.interface import implements

from twisted.lore.scripts.lore import IProcessor
from twisted.plugin import IPlugin

class _LorePlugin(object):
    implements(IPlugin, IProcessor)

    def __init__(self, name, moduleName, description):
        self.name = name
        self.moduleName = moduleName
        self.description = description

DefaultProcessor = _LorePlugin(
    "lore",
    "twisted.lore.default",
    "Lore format")

MathProcessor = _LorePlugin(
    "mlore",
    "twisted.lore.lmath",
    "Lore format with LaTeX formula")

SlideProcessor = _LorePlugin(
    "lore-slides",
    "twisted.lore.slides",
    "Lore for slides")

ManProcessor = _LorePlugin(
    "man",
    "twisted.lore.man2lore",
    "UNIX Man pages")

NevowProcessor = _LorePlugin(
    "nevow",
    "twisted.lore.nevowlore",
    "Nevow for Lore")
