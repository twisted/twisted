import quoteproto, quoters
from twisted.coil import coil
from twisted.python import components

import types


# QOTDFactory configuration

class FactoryConfigurator(coil.Configurator):
    """Configurator for QOTD Factory."""
    
    __implements__ = (coil.IConfigurator, coil.IStaticCollection)
    
    configurableClass = quoteproto.QOTDFactory
    
    configTypes = {'quoter': [quoters.IQuoter, "Quote Source", "The source for the quotes."],
                   }
    
    configName = 'Quote of the Day'
    
    def listStaticEntities(self):
        return [['quoter', self.instance.quoter]]

    def listStaticNames(self):
        return ['quoter']
    
    def getStaticEntity(self, name):
        if name == 'quoter':
            return self.instance.quoter
    

def qotdFactory(container, name):
    default = "An apple a day keeps the doctor away."
    f = quoteproto.QOTDFactory(quoters.StaticQuoter(default))
    return f

components.registerAdapter(FactoryConfigurator, quoteproto.QOTDFactory, coil.ICollection)
coil.registerConfigurator(FactoryConfigurator, qotdFactory)


# Configuration for quote sources

class StaticConfigurator(coil.Configurator):

    configurableClass = quoters.StaticQuoter
    
    configTypes = {'quote': [types.StringType, "Quote", "The quote to return."],
                   }
    
    configName = 'Static Quoter'

def staticFactory(container, name):
    default = "An apple a day keeps the doctor away."
    return quoters.StaticQuoter(default)

coil.registerConfigurator(StaticConfigurator, staticFactory)


class FortuneConfigurator(coil.ConfigCollection, coil.Configurator):

    __implements__ = coil.IConfigCollection, coil.IConfigurator
    
    entityType = types.StringType
    configurableClass = quoters.FortuneQuoter
    configName = "Fortune Quoter"
    
    def __init__(self, instance):
        self.d = {}
        for filename in instance.filenames: self.d[filename] = ""
        coil.Configurator.__init__(self, instance)
        coil.ConfigCollection.__init__(self, self.d)

    def reallyPutEntity(self, name, value):
        self.d[name] = value
        if not name in self.instance.filenames: self.instance.filenames.append(name)

    def delEntity(self, name):
        try:
            self.instance.filenames.remove(name)
        except ValueError:
            raise KeyError

def fortuneFactory(container, name):
    return quoters.FortuneQuoter([])

components.registerAdapter(FortuneConfigurator, quoters.FortuneQuoter, coil.ICollection)
coil.registerConfigurator(FortuneConfigurator, fortuneFactory)    
    

