
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

The Twisted Plugin System
=========================





The purpose of this guide is to describe the preferred way to
write extensible Twisted applications (and consequently, also to
describe how to extend applications written in such a way).  This
extensibility is achieved through the definition of one or more
APIs and a mechanism for collecting code plugins which
implement this API to provide some additional functionality.
At the base of this system is the :api:`twisted.plugin <twisted.plugin>` module.

    


Making an application extensible using the plugin system has
several strong advantages over other techniques:

    




- It allows third-party developers to easily enhance your
  software in a way that is loosely coupled: only the plugin API
  is required to remain stable.
- It allows new plugins to be discovered flexibly.  For
  example, plugins can be loaded and saved when a program is first
  run, or re-discovered each time the program starts up, or they
  can be polled for repeatedly at runtime (allowing the discovery
  of new plugins installed after the program has started).


    



Writing Extensible Programs
---------------------------


    
Taking advantage of :api:`twisted.plugin <twisted.plugin>` is
a two step process:

    



#. 
   
   
   Define an interface which plugins will be required to implement.
   This is done using the zope.interface package in the same way one
   would define an interface for any other purpose.
   
   
   
   
   
   
   A convention for defining interfaces is do so in a file named like
   *ProjectName/projectname/iprojectname.py* .  The rest of this
   document will follow that convention: consider the following
   interface definition be in ``Matsim/matsim/imatsim.py`` , an
   interface definition module for a hypothetical material simulation
   package.
   
   
   
#. 
   At one or more places in your program, invoke :api:`twisted.plugin.getPlugins <twisted.plugin.getPlugins>` and iterate over its
   result.




As an example of the first step, consider the following interface
definition for a physical modelling system.


    



.. code-block:: python

    
    from zope.interface import Interface, Attribute
    
    class IMaterial(Interface):
        """
        An object with specific physical properties
        """
        def yieldStress(temperature):
            """
            Returns the pressure this material can support without
            fracturing at the given temperature.
    
            @type temperature: C{float}
            @param temperature: Kelvins
    
            @rtype: C{float}
            @return: Pascals
            """
    
        dielectricConstant = Attribute("""
            @type dielectricConstant: C{complex}
            @ivar dielectricConstant: The relative permittivity, with the
            real part giving reflective surface properties and the
            imaginary part giving the radio absorption coefficient.
            """)
    



    
In another module, we might have a function that operates on
objects providing the ``IMaterial`` interface:

    



.. code-block:: python

    
    def displayMaterial(m):
        print 'A material with yield stress %s at 500 K' % (m.yieldStress(500),)
        print 'Also a dielectric constant of %s.' % (m.dielectricConstant,)



    
The last piece of required code is that which collects
``IMaterial`` providers and passes them to the
``displayMaterial`` function.

    



.. code-block:: python

    
    from twisted.plugin import getPlugins
    from matsim import imatsim
    
    def displayAllKnownMaterials():
        for material in getPlugins(imatsim.IMaterial):
            displayMaterial(material)



    
Third party developers may now contribute different materials
to be used by this modelling system by implementing one or more
plugins for the ``IMaterial`` interface.

    



Extending an Existing Program
-----------------------------


    
The above code demonstrates how an extensible program might be
written using Twisted's plugin system.  How do we write plugins
for it, though?  Essentially, we create objects which provide the
required interface and then make them available at a particular
location.  Consider the following example.

    



.. code-block:: python

    
    from zope.interface import implements
    from twisted.plugin import IPlugin
    from matsim import imatsim
    
    class SimpleMaterial(object):
        implements(IPlugin, imatsim.IMaterial)
    
        def __init__(self, yieldStressFactor, dielectricConstant):
            self._yieldStressFactor = yieldStressFactor
            self.dielectricConstant = dielectricConstant
    
        def yieldStress(self, temperature):
            return self._yieldStressFactor * temperature
    
    steelPlate = SimpleMaterial(2.06842719e11, 2.7 + 0.2j)
    brassPlate = SimpleMaterial(1.03421359e11, 1.4 + 0.5j)



    
``steelPlate`` and ``brassPlate`` now provide both
:api:`twisted.plugin.IPlugin <IPlugin>` and ``IMaterial`` .
All that remains is to make this module available at an appropriate
location. For this, there are two options. The first of these is
primarily useful during development: if a directory which
has been added to ``sys.path`` (typically by adding it to the
``PYTHONPATH`` environment variable) contains a
*directory* named ``twisted/plugins/`` ,
each ``.py`` file in that directory will be loaded
as a source of plugins.  This directory *must not* be a Python
package: including ``__init__.py`` will cause the
directory to be skipped and no plugins loaded from it.  Second, each
module in the installed version of Twisted's ``twisted.plugins`` package will also be loaded as a source of
plugins.

    


Once this plugin is installed in one of these two ways,
``displayAllKnownMaterials`` can be run and we will see
two pairs of output: one for a steel plate and one for a brass
plate.

    



Alternate Plugin Packages
-------------------------


    
:api:`twisted.plugin.getPlugins <getPlugins>` takes one
additional argument not mentioned above.  If passed in, the 2nd argument
should be a module or package to be used instead of
``twisted.plugins`` as the plugin meta-package.  If you
are writing a plugin for a Twisted interface, you should never
need to pass this argument.  However, if you have developed an
interface of your own, you may want to mandate that plugins for it
are installed in your own plugins package, rather than in
Twisted's.

    


You may want to support ``yourproject/plugins/`` 
directories for ease of development.  To do so, you should make ``yourproject/plugins/__init__.py`` contain at least
the following lines.

    



.. code-block:: python

    
    from twisted.plugin import pluginPackagePaths
    __path__.extend(pluginPackagePaths(__name__))
    __all__ = []



    
The key behavior here is that interfaces are essentially paired
with a particular plugin package.  If plugins are installed in a
different package than the one the code which relies on the
interface they provide, they will not be found when the
application goes to load them.

    



Plugin Caching
--------------


    
In the course of using the Twisted plugin system, you may
notice ``dropin.cache`` files appearing at
various locations.  These files are used to cache information
about what plugins are present in the directory which contains
them.  At times, this cached information may become out of date.
Twisted uses the mtimes of various files involved in the plugin
system to determine when this cache may have become invalid.
Twisted will try to re-write the cache each time it tries to use
it but finds it out of date.

    


For a site-wide install, it may not (indeed, should not) be
possible for applications running as normal users to rewrite the
cache file.  While these applications will still run and find
correct plugin information, they may run more slowly than they
would if the cache was up to date, and they may also report
exceptions if certain plugins have been removed but which the
cache still references.  For these reasons, when installing or
removing software which provides Twisted plugins, the site
administrator should be sure the cache is regenerated.
Well-behaved package managers for such software should take this
task upon themselves, since it is trivially automatable.  The
canonical way to regenerate the cache is to run the following
Python code:

    



.. code-block:: python

    
    from twisted.plugin import IPlugin, getPlugins
    list(getPlugins(IPlugin))



    
As mentioned, it is normal for exceptions to be raised
**once** here if plugins have been removed.

    



Further Reading
---------------


    



- :doc:`Components: Interfaces and Adapters <components>` 


  

