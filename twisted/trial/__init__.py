"""Unit testing framework."""

try:
    from zope.interface import interface, declarations
    from zope.interface.adapter import AdapterRegistry
except ImportError:
    raise ImportError, "you need zope.interface installed (http://zope.org/Products/ZopeInterface/)"

_globalRegistry = AdapterRegistry()

# we define a private adapter registry here to avoid conflicts and
# have a bit more control

def registerAdapter(adapterFactory, origInterface, *interfaceClasses):
    self = _globalRegistry
    assert interfaceClasses, "You need to pass an Interface"

    if not isinstance(origInterface, interface.InterfaceClass):
        origInterface = declarations.implementedBy(origInterface)

    for interfaceClass in interfaceClasses:
        factory = self.get(origInterface).selfImplied.get(interfaceClass, {}).get('')
        if factory and adapterFactory is not None: 
            raise ValueError("an adapter (%s) was already registered." % (factory, ))

    for interfaceClass in interfaceClasses:
        self.register([origInterface], interfaceClass, '', adapterFactory)


def adaptWithDefault(iface, orig, default=None):
    # GUH! zi sucks
    face = default
    try:
        face = iface(orig)
    except TypeError, e:
        if e.args[0] == 'Could not adapt':
            pass
        else:
            raise
    return face


# add global adapter lookup hook for our newly created registry
def _hook(iface, ob, lookup=_globalRegistry.lookup1):
    factory = lookup(declarations.providedBy(ob), iface)
    if factory is None:
        return None
    else:
        return factory(ob)
interface.adapter_hooks.append(_hook)


del _hook, AdapterRegistry

__all__ = ['registerAdapter', 'adaptWithDefault']
