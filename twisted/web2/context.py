
import warnings
from twisted.python import components
from twisted.python.reflect import qual

from twisted.web2 import iweb

#try:
#    import nevow
#    from nevow import inevow
#    dataqual = qual(inevow.IData)
#except ImportError:
dataqual = object()

_marker = object()

def megaGetInterfaces(adapter):
    adrs = [qual(x) for x in components.getInterfaces(adapter)]
    ## temporarily turn this off till we need it
    if False: #hasattr(adapter, '_adapterCache'):
        adrs.extend(adapter._adapterCache.keys())
    return adrs


class WebContext(object):
    _remembrances = None
    tag = None
    _slotData = None
    parent = None
    locateHook = None
    
    # XXX: can we get rid of these 5 somehow?
    isAttrib = property(lambda self: False)
    inURL = property(lambda self: False)
    precompile = property(lambda self: False)
    
    def arg(self, get, default=None):
        """Placeholder until I can find Jerub's implementation of this

        Return a single named argument from the request arguments
        """
        req = self.locate(iweb.IRequest)
        return req.args.get(get, [default])[0]
    # ^ XXX
    
    def __init__(self, parent=None, tag=None, remembrances=None):
        self.tag = tag
        sd = getattr(tag, 'slotData', None)
        if sd is not None:
            self._slotData = sd
        self.parent = parent
        self._remembrances = remembrances
    
    def remember(self, adapter, interface=None):
        """Remember an object that implements some interfaces.
        Later, calls to .locate which are passed an interface implemented
        by this object will return this object.
        
        If the 'interface' argument is supplied, this object will only
        be remembered for this interface, and not any of
        the other interfaces it implements.
        """
        if interface is None:
            interfaceList = megaGetInterfaces(adapter)
            if not interfaceList:
                interfaceList = [dataqual]
        else:
            interfaceList = [qual(interface)]
        if self._remembrances is None:
            self._remembrances = {}
        for interface in interfaceList:
            self._remembrances[interface] = adapter
        return self

    def locate(self, interface, depth=1, _default=object()):
        """Locate an object which implements a given interface.
        Objects will be searched through the context stack top
        down.
        """
        key = qual(interface)
        currentContext = self
        while True:
            if depth < 0:
                full = []
                while True:
                    try:
                        full.append(self.locate(interface, len(full)+1))
                    except KeyError:
                        break
                #print "full", full, depth
                if full:
                    return full[depth]
                return None

            # Hook for FactoryContext and other implementations of complex locating
            locateHook = currentContext.locateHook
            if locateHook is not None:
                result = locateHook(interface)
                if result is not None:
                    return result

            _remembrances = currentContext._remembrances
            if _remembrances is not None:
                rememberedValue = _remembrances.get(key, _default)
                if rememberedValue is not _default:
                    depth -= 1
                    if not depth:
                        return rememberedValue

            contextParent = currentContext.parent
            if contextParent is None:
                raise KeyError, "Interface %s was not remembered." % key

            currentContext = contextParent
    
    def chain(self, context):
        """For nevow machinery use only.

        Go to the top of this context's context chain, and make
        the given context the parent, thus continuing the chain
        into the given context's chain.
        """
        top = self
        while top.parent is not None:
            if top.parent.tag is None:
                ## If top.parent.tag is None, that means this context (top)
                ## is just a marker. We want to insert the current context
                ## (context) as the parent of this context (top) to chain properly.
                break
            top = top.parent
            if top is context: # this context is already in the chain; don't create a cycle
                return
        top.parent = context

    def fillSlots(self, name, stan):
        """Set 'stan' as the stan tree to replace all slots with name 'name'.
        """
        if self._slotData is None:
            self._slotData = {}
        self._slotData[name] = stan

    def locateSlotData(self, name):
        """For use by nevow machinery only, or for some fancy cases.

        Find previously remembered slot filler data.
        For use by flatstan.SlotRenderer"""
        if self._slotData:
            data = self._slotData.get(name, _marker)
            if data is not _marker:
                return data
        if self.parent is None:
            raise KeyError, "Slot named '%s' was not filled." % name
        return self.parent.locateSlotData(name)
    
    def clone(self, deep=True, cloneTags=True):
        ## don't clone the tags of parent contexts. I *hope* code won't be
        ## trying to modify parent tags so this should not be necessary.
        ## However, *do* clone the parent contexts themselves.
        ## This is necessary for chain(), as it mutates top-context.parent.
        
        if self.parent:
            parent=self.parent.clone(cloneTags=False)
        else:
            parent=None
        if cloneTags:
            tag = self.tag.clone(deep=deep)
        else:
            tag = self.tag
        if self._remembrances is not None:
            remembrances=self._remembrances.copy()
        else:
            remembrances=None
        return type(self)(
            parent = parent,
            tag = tag,
            remembrances=remembrances,
        )

    def __conform__(self, interface):
        """Support IFoo(ctx) syntax.
        """
        try:
            return self.locate(interface)
        except KeyError:
            return None
        
class FactoryContext(WebContext): 
    """A context which allows adapters to be registered against it so that an object 
    can be lazily created and returned at render time. When ctx.locate is called
    with an interface for which an adapter is registered, that adapter will be used
    and the result returned.
    """
    cache = None
    inLocate = 0
    
    def locateHook(self, interface):
        if self.cache is None:
            self.cache = {}
        else:
            adapter = self.cache.get(interface, None)
            if adapter is not None:
                return adapter

        ## Prevent infinite recursion from interface(self) calling self.__conform__ calling self.locate
        self.inLocate += 1
        adapter = interface(self, None)
        ## Remove shadowing
        self.inLocate -= 1

        if adapter is not None:
            self.cache[interface] = adapter
            return adapter
        return None

    def __conform__(self, interface):
        if self.inLocate:
            return None
        return WebContext.__conform__(self, interface)

class SiteContext(FactoryContext):
    """A SiteContext is created and installed on a NevowSite upon initialization.
    It will always be used as the root context, and can be used as a place to remember
    things sitewide.
    """
    pass


class RequestContext(FactoryContext):
    """A RequestContext has adapters for the following interfaces:
    
    ISession
    IFormDefaults
    IFormErrors
    IHand
    IStatusMessage
    """
    pass

components.registerAdapter(lambda ctx: ctx.tag, RequestContext, iweb.IRequest)
components.registerAdapter(lambda ctx: iweb.IOldRequest(ctx.tag), RequestContext, iweb.IOldRequest)

__all__ = ['WebContext', 'SiteContext', 'RequestContext', 'FactoryContext']
