:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Components: Interfaces and Adapters
===================================

Object oriented programming languages allow programmers to reuse portions of existing code by creating new "classes" of objects which subclass another class.
When a class subclasses another, it is said to *inherit* all of its behaviour.
The subclass can then "override" and "extend" the behavior provided to it by the superclass.
Inheritance is very useful in many situations, but because it is so convenient to use, often becomes abused in large software systems, especially when multiple inheritance is involved.
One solution is to use *delegation* instead of "inheritance" where appropriate.
Delegation is simply the act of asking *another* object to perform a task for an object.
To support this design pattern, which is often referred to as the *components* pattern because it involves many small interacting components, *interfaces* and *adapters* were created by the Zope 3 team.

"Interfaces" are simply markers which objects can use to say "I implement this interface".
Other objects may then make requests like "Please give me an object which implements interface X for object type Y".
Objects which implement an interface for another object type are called "adapters".

The superclass-subclass relationship is said to be an *is-a* relationship.
When designing object hierarchies, object modellers use subclassing when they can say that the subclass *is* the same class as the superclass.
For example:

.. code-block:: python

    class Shape:
        sideLength = 0
        def getSideLength(self):
            return self.sideLength

        def setSideLength(self, sideLength):
            self.sideLength = sideLength

        def area(self):
            raise NotImplementedError, "Subclasses must implement area"

    class Triangle(Shape):
        def area(self):
            return (self.sideLength * self.sideLength) / 2

    class Square(Shape):
        def area(self):
            return self.sideLength * self.sideLength

In the above example, a Triangle *is-a* Shape, so it subclasses Shape, and a Square *is-a* Shape, so it also subclasses Shape.

However, subclassing can get complicated, especially when Multiple Inheritance enters the picture.
Multiple Inheritance allows a class to inherit from more than one base class.
Software which relies heavily on inheritance often ends up having both very wide and very deep inheritance trees, meaning that one class inherits from many superclasses spread throughout the system.
Since subclassing with Multiple Inheritance means *implementation inheritance*, locating a method's actual implementation and ensuring the correct method is actually being invoked becomes a challenge.
For example:

.. code-block:: python

    class Area:
        sideLength = 0
        def getSideLength(self):
            return self.sideLength

        def setSideLength(self, sideLength):
            self.sideLength = sideLength

        def area(self):
            raise NotImplementedError, "Subclasses must implement area"

    class Color:
        color = None
        def setColor(self, color):
          self.color = color

        def getColor(self):
          return self.color

    class Square(Area, Color):
        def area(self):
            return self.sideLength * self.sideLength


The reason programmers like using implementation inheritance is because it makes code easier to read since the implementation details of Area are in a separate place than the implementation details of Color.
This is nice, because conceivably an object could have a color but not an area, or an area but not a color.
The problem, though, is that Square is not really an Area or a Color, but has an area and color.
Thus, we should really be using another object oriented technique called *composition*, which relies on delegation rather than inheritance to break code into small reusable chunks.
Let us continue with the Multiple Inheritance example, though, because it is often used in practice.

What if both the Color and the Area base class defined the same method, perhaps ``calculate``?
Where would the implementation come from?
The implementation that is located for ``Square().calculate()`` depends on the method resolution order, or MRO, and can change when programmers change seemingly unrelated things by refactoring classes in other parts of the system, causing obscure bugs.
Our first thought might be to change the calculate method name to avoid name clashes, to perhaps ``calculateArea`` and ``calculateColor``.
While explicit, this change could potentially require a large number of changes throughout a system, and is error-prone, especially when attempting to integrate two systems which you didn't write.

Let's imagine another example. We have an electric appliance, say a hair dryer.
The hair dryer is American voltage.
We have two electric sockets, one of them an American 120 Volt socket, and one of them a United Kingdom 240 Volt socket.
If we plug the hair dryer into the 240 Volt socket, it is going to expect 120 Volt current and errors will result.
Going back and changing the hair dryer to support both ``plug120Volt`` and ``plug240Volt`` methods would be tedious, and what if we decided we needed to plug the hair dryer into yet another type of socket?
For example:

.. code-block:: python

    class HairDryer:
        def plug(self, socket):
            if socket.voltage() == 120:
                print "I was plugged in properly and am operating."
            else:
                print "I was plugged in improperly and "
                print "now you have no hair dryer any more."

    class AmericanSocket:
        def voltage(self):
            return 120

    class UKSocket:
        def voltage(self):
            return 240


Given these classes, the following operations can be performed:

.. code-block:: pycon

    >>> hd = HairDryer()
    >>> am = AmericanSocket()
    >>> hd.plug(am)
    I was plugged in properly and am operating.
    >>> uk = UKSocket()
    >>> hd.plug(uk)
    I was plugged in improperly and
    now you have no hair dryer any more.


We are going to attempt to solve this problem by writing an Adapter for the ``UKSocket`` which converts the voltage for use with an American hair dryer.
An Adapter is a class which is constructed with one and only one argument, the "adaptee" or "original" object.
In this example, we will show all code involved for clarity:

.. code-block:: python

    class AdaptToAmericanSocket:
        def __init__(self, original):
            self.original = original

        def voltage(self):
            return self.original.voltage() / 2


Now, we can use it as so:

.. code-block:: pycon

    >>> hd = HairDryer()
    >>> uk = UKSocket()
    >>> adapted = AdaptToAmericanSocket(uk)
    >>> hd.plug(adapted)
    I was plugged in properly and am operating.


So, as you can see, an adapter can 'override' the original implementation.
It can also 'extend' the interface of the original object by providing methods the original object did not have.
Note that an Adapter must explicitly delegate any method calls it does not wish to modify to the original, otherwise the Adapter cannot be used in places where the original is expected.
Usually this is not a problem, as an Adapter is created to conform an object to a particular interface and then discarded.


Interfaces and Components in Twisted code
-----------------------------------------

Adapters are a useful way of using multiple classes to factor code into discrete chunks.
However, they are not very interesting without some more infrastructure.
If each piece of code which wished to use an adapted object had to explicitly construct the adapter itself, the coupling between components would be too tight.
We would like to achieve "loose coupling", and this is where :api:`twisted.python.components <twisted.python.components>` comes in.

First, we need to discuss Interfaces in more detail.
As we mentioned earlier, an Interface is nothing more than a class which is used as a marker.
Interfaces should be subclasses of ``zope.interface.Interface``, and have a very odd look to python programmers not used to them:

.. code-block:: python

    from zope.interface import Interface

    class IAmericanSocket(Interface):
        def voltage():
          """
          Return the voltage produced by this socket object, as an integer.
          """


Notice how it looks just like a regular class definition, other than inheriting from ``Interface``?
However, the method definitions inside the class block do not have any method body!
Since Python does not have any native language-level support for Interfaces like Java does, this is what distinguishes an Interface definition from a Class.

Now that we have a defined Interface, we can talk about objects using terms like this:
"The ``AmericanSocket`` class implements the ``IAmericanSocket`` interface" and "Please give me an object which adapts ``UKSocket`` to the ``IAmericanSocket`` interface".
We can make *declarations* about what interfaces a certain class implements, and we can request adapters which implement a certain interface for a specific class.

Let's look at how we declare that a class implements an interface:

.. code-block:: python

    from zope.interface import implementer

    @implementer(IAmericanSocket)
    class AmericanSocket:
        def voltage(self):
            return 120

So, to declare that a class implements an interface, we simply decorate it with ``zope.interface.implementer``.

Now, let's say we want to rewrite the ``AdaptToAmericanSocket`` class as a real adapter.
In this case we also specify it as implementing ``IAmericanSocket``:

.. code-block:: python

    from zope.interface import implementer

    @implementer(IAmericanSocket)
    class AdaptToAmericanSocket:
        def __init__(self, original):
            """
            Pass the original UKSocket object as original
            """
            self.original = original

        def voltage(self):
            return self.original.voltage() / 2


Notice how we placed the implements declaration on this adapter class.
So far, we have not achieved anything by using components other than requiring us to type more.
In order for components to be useful, we must use the *component registry*.
Since ``AdaptToAmericanSocket`` implements ``IAmericanSocket`` and regulates the voltage of a ``UKSocket`` object, we can register ``AdaptToAmericanSocket`` as an ``IAmericanSocket`` adapter for the ``UKSocket`` class.
It is easier to see how this is done in code than to describe it:

.. code-block:: python

    from zope.interface import Interface, implementer
    from twisted.python import components

    class IAmericanSocket(Interface):
        def voltage():
          """
          Return the voltage produced by this socket object, as an integer.
          """

    @implementer(IAmericanSocket)
    class AmericanSocket:
        def voltage(self):
            return 120

    class UKSocket:
        def voltage(self):
            return 240

    @implementer(IAmericanSocket)
    class AdaptToAmericanSocket:
        def __init__(self, original):
            self.original = original

        def voltage(self):
            return self.original.voltage() / 2

    components.registerAdapter(
        AdaptToAmericanSocket,
        UKSocket,
        IAmericanSocket)


Now, if we run this script in the interactive interpreter, we can discover a little more about how to use components.
The first thing we can do is discover whether an object implements an interface or not:

.. code-block:: pycon

    >>> IAmericanSocket.implementedBy(AmericanSocket)
    True
    >>> IAmericanSocket.implementedBy(UKSocket)
    False
    >>> am = AmericanSocket()
    >>> uk = UKSocket()
    >>> IAmericanSocket.providedBy(am)
    True
    >>> IAmericanSocket.providedBy(uk)
    False


As you can see, the ``AmericanSocket`` instance claims to implement ``IAmericanSocket``, but the ``UKSocket`` does not.
If we wanted to use the ``HairDryer`` with the ``AmericanSocket``, we could know that it would be safe to do so by checking whether it implements ``IAmericanSocket``.
However, if we decide we want to use ``HairDryer`` with a ``UKSocket`` instance, we must *adapt* it to ``IAmericanSocket`` before doing so.
We use the interface object to do this:

.. code-block:: pycon

    >>> IAmericanSocket(uk)
    <__main__.AdaptToAmericanSocket instance at 0x1a5120>


When calling an interface with an object as an argument, the interface looks in the adapter registry for an adapter which implements the interface for the given instance's class.
If it finds one, it constructs an instance of the Adapter class, passing the constructor the original instance, and returns it.
Now the ``HairDryer`` can safely be used with the adapted  ``UKSocket`` .
But what happens if we attempt to adapt an object which already implements ``IAmericanSocket``?
We simply get back the original instance:

.. code-block:: pycon

    >>> IAmericanSocket(am)
    <__main__.AmericanSocket instance at 0x36bff0>


So, we could write a new "smart" ``HairDryer`` which automatically looked up an adapter for the socket you tried to plug it into:

.. code-block:: python

    class HairDryer:
        def plug(self, socket):
            adapted = IAmericanSocket(socket)
            assert adapted.voltage() == 120, "BOOM"
            print "I was plugged in properly and am operating"

Now, if we create an instance of our new "smart" ``HairDryer`` and attempt to plug it in to various sockets, the ``HairDryer`` will adapt itself automatically depending on the type of socket it is plugged in to:

.. code-block:: pycon

    >>> am = AmericanSocket()
    >>> uk = UKSocket()
    >>> hd = HairDryer()
    >>> hd.plug(am)
    I was plugged in properly and am operating
    >>> hd.plug(uk)
    I was plugged in properly and am operating


Voila; the magic of components.


Components and Inheritance
~~~~~~~~~~~~~~~~~~~~~~~~~~

If you inherit from a class which implements some interface, and your new subclass declares that it implements another interface, the implements will be inherited by default.

For example, :api:`twisted.spread.pb.Root <pb.Root>` is a class which implements :api:`twisted.spread.pb.IPBRoot <IPBRoot>`.
This interface indicates that an object has remotely-invokable methods and can be used as the initial object served by a new Broker instance.
It has an ``implements`` setting like:

.. code-block:: python

    from zope.interface import implementer

    @implementer(IPBRoot)
    class Root(Referenceable):
        pass


Suppose you have your own class which implements your ``IMyInterface`` interface:

.. code-block:: python

    from zope.interface import implementer, Interface

    class IMyInterface(Interface):
        pass

    @implementer(IMyInterface)
    class MyThing:
        pass


Now if you want to make this class inherit from ``pb.Root``, the interfaces code will automatically determine that it also implements ``IPBRoot``:

.. code-block:: python

    from twisted.spread import pb
    from zope.interface import implementer, Interface

    class IMyInterface(Interface):
        pass

    @implementer(IMyInterface)
    class MyThing(pb.Root):
        pass


.. code-block:: pycon

    >>> from twisted.spread.flavors import IPBRoot
    >>> IPBRoot.implementedBy(MyThing)
    True


If you want ``MyThing`` to inherit from ``pb.Root`` but *not* implement ``IPBRoot`` like ``pb.Root`` does, use ``@implementer_only``:

.. code-block:: python

    from twisted.spread import pb
    from zope.interface import implementer_only, Interface

    class IMyInterface(Interface):
        pass

    @implementer_only(IMyInterface)
    class MyThing(pb.Root):
        pass


.. code-block:: pycon

    >>> from twisted.spread.pb import IPBRoot
    >>> IPBRoot.implementedBy(MyThing)
    False
