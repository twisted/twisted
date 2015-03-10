
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Choosing a Reactor and GUI Toolkit Integration
==============================================






Overview
--------


    
Twisted provides a variety of implementations of the :api:`twisted.internet.reactor <twisted.internet.reactor>` .  The specialized
implementations are suited for different purposes and are
designed to integrate better with particular platforms.

    


The :ref:`epoll()-based reactor <core-howto-choosing-reactor-epoll>` is Twisted's default on
Linux. Other platforms use :ref:`poll() <core-howto-choosing-reactor-poll>` , or the most
cross-platform reactor, :ref:`select() <core-howto-choosing-reactor-select>` .

    


Platform-specific reactor implementations exist for:

    




- :ref:`Poll for Linux <core-howto-choosing-reactor-poll>` 
- :ref:`Epoll for Linux 2.6 <core-howto-choosing-reactor-epoll>` 
- :ref:`WaitForMultipleObjects (WFMO) for Win32 <core-howto-choosing-reactor-win32_wfmo>` 
- :ref:`Input/Output Completion Port (IOCP) for Win32 <core-howto-choosing-reactor-win32_iocp>` 
- :ref:`KQueue for FreeBSD and Mac OS X <core-howto-choosing-reactor-kqueue>` 
- :ref:`CoreFoundation for Mac OS X <core-howto-choosing-reactor-cfreactor>` 


    


The remaining custom reactor implementations provide support
for integrating with the native event loops of various graphical
toolkits.  This lets your Twisted application use all of the
usual Twisted APIs while still being a graphical application.

    


Twisted currently integrates with the following graphical
toolkits:

    




- :ref:`GTK+ 2.0 <core-howto-choosing-reactor-gtk>` 
- :ref:`GTK+ 3.0 and GObject Introspection <core-howto-choosing-reactor-gtk3>` 
- :ref:`Tkinter <core-howto-choosing-reactor-tkinter>` 
- :ref:`wxPython <core-howto-choosing-reactor-wxpython>` 
- :ref:`Win32 <core-howto-choosing-reactor-win32_wfmo>` 
- :ref:`CoreFoundation <core-howto-choosing-reactor-cfreactor>` 
- :ref:`PyUI <core-howto-choosing-reactor-pyui>` 


    


When using applications that are runnable using ``twistd`` , e.g.
TACs or plugins, there is no need to choose a reactor explicitly, since
this can be chosen using ``twistd`` 's -r option.

    


In all cases, the event loop is started by calling ``reactor.run()`` . In all cases, the event loop
should be stopped with ``reactor.stop()`` .

    


**IMPORTANT:** installing a reactor should be the first thing
done in the app, since any code that does
``from twisted.internet import reactor`` will automatically
install the default reactor if the code hasn't already installed one.

    



Reactor Functionality
---------------------


    
+-----------------------------------------------+--------------+-----+-----+-----+-----------+-----------+------------+-------------+
| \                                             | Status       | TCP | SSL | UDP | Threading | Processes | Scheduling | Platforms   |
+===============================================+==============+=====+=====+=====+===========+===========+============+=============+
| select()                                      | Stable       | Y   | Y   | Y   | Y         | Y         | Y          | Unix, Win32 |
+-----------------------------------------------+--------------+-----+-----+-----+-----------+-----------+------------+-------------+
| poll                                          | Stable       | Y   | Y   | Y   | Y         | Y         | Y          | Unix        |
+-----------------------------------------------+--------------+-----+-----+-----+-----------+-----------+------------+-------------+
| WaitForMultipleObjects (WFMO) for Win32       | Experimental | Y   | Y   | Y   | Y         | Y         | Y          | Win32       |
+-----------------------------------------------+--------------+-----+-----+-----+-----------+-----------+------------+-------------+
| Input/Output Completion Port (IOCP) for Win32 | Experimental | Y   | Y   | Y   | Y         | Y         | Y          | Win32       |
+-----------------------------------------------+--------------+-----+-----+-----+-----------+-----------+------------+-------------+
| CoreFoundation                                | Unmaintained | Y   | Y   | Y   | Y         | Y         | Y          | Mac OS X    |
+-----------------------------------------------+--------------+-----+-----+-----+-----------+-----------+------------+-------------+
| epoll                                         | Stable       | Y   | Y   | Y   | Y         | Y         | Y          | Linux 2.6   |
+-----------------------------------------------+--------------+-----+-----+-----+-----------+-----------+------------+-------------+
| GTK+                                          | Stable       | Y   | Y   | Y   | Y         | Y         | Y          | Unix, Win32 |
+-----------------------------------------------+--------------+-----+-----+-----+-----------+-----------+------------+-------------+
| wx                                            | Experimental | Y   | Y   | Y   | Y         | Y         | Y          | Unix, Win32 |
+-----------------------------------------------+--------------+-----+-----+-----+-----------+-----------+------------+-------------+
| kqueue                                        | Stable       | Y   | Y   | Y   | Y         | Y         | Y          | FreeBSD     |
+-----------------------------------------------+--------------+-----+-----+-----+-----------+-----------+------------+-------------+



General Purpose Reactors
------------------------


    

Select()-based Reactor
~~~~~~~~~~~~~~~~~~~~~~
.. _core-howto-choosing-reactor-select:







    
The ``select`` reactor is the default on platforms that don't
provide a better alternative that covers all use cases. If
the ``select`` reactor is desired, it may be installed via:





.. code-block:: python

    
    from twisted.internet import selectreactor
    selectreactor.install()
    
    from twisted.internet import reactor



    

Platform-Specific Reactors
--------------------------


    

Poll-based Reactor
~~~~~~~~~~~~~~~~~~
.. _core-howto-choosing-reactor-poll:







    
The PollReactor will work on any platform that provides ``select.poll`` .  With larger numbers of connected
sockets, it may provide for better performance than the SelectReactor.





.. code-block:: python

    
    from twisted.internet import pollreactor
    pollreactor.install()
    
    from twisted.internet import reactor



    

KQueue
~~~~~~
.. _core-howto-choosing-reactor-kqueue:







    
The KQueue Reactor allows Twisted to use FreeBSD's kqueue mechanism for
event scheduling. See instructions in the :api:`twisted.internet.kqreactor <twisted.internet.kqreactor>` 's
docstring for installation notes.





.. code-block:: python

    
    from twisted.internet import kqreactor
    kqreactor.install()
    
    from twisted.internet import reactor




   

WaitForMultipleObjects (WFMO) for Win32
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
.. _core-howto-choosing-reactor-win32_wfmo:







    
The Win32 reactor is not yet complete and has various limitations
and issues that need to be addressed.  The reactor supports GUI integration
with the win32gui module, so it can be used for native Win32 GUI applications.






.. code-block:: python

    
    from twisted.internet import win32eventreactor
    win32eventreactor.install()
    
    from twisted.internet import reactor



   

Input/Output Completion Port (IOCP) for Win32
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
.. _core-howto-choosing-reactor-win32_iocp:







    

Windows provides a fast, scalable event notification system known as IO
Completion Ports, or IOCP for short.  Twisted includes a reactor based
on IOCP which is nearly complete.






.. code-block:: python

    
    from twisted.internet import iocpreactor
    iocpreactor.install()
    
    from twisted.internet import reactor



    

Epoll-based Reactor
~~~~~~~~~~~~~~~~~~~
.. _core-howto-choosing-reactor-epoll:







    
The EPollReactor will work on any platform that provides
``epoll`` , today only Linux 2.6 and over. The
implementation of the epoll reactor currently uses the Level Triggered
interface, which is basically like poll() but scales much better.





.. code-block:: python

    
    from twisted.internet import epollreactor
    epollreactor.install()
    
    from twisted.internet import reactor



    

GUI Integration Reactors
------------------------


    

GTK+
~~~~
.. _core-howto-choosing-reactor-gtk:







    
Twisted integrates with `PyGTK <http://www.pygtk.org/>`_ version
2.0 using the ``gtk2reactor`` . An example Twisted application that
uses GTK+ can be found
in ``doc/core/examples/pbgtk2.py`` .

    


GTK-2.0 split the event loop out of the GUI toolkit and into a separate
module called "glib" . To run an application using the glib event loop,
use the ``glib2reactor`` . This will be slightly faster
than ``gtk2reactor`` (and does not require a working X display),
but cannot be used to run GUI applications.





.. code-block:: python

    
    from twisted.internet import gtk2reactor # for gtk-2.0
    gtk2reactor.install()
    
    from twisted.internet import reactor





.. code-block:: python

    
    from twisted.internet import glib2reactor # for non-GUI apps
    glib2reactor.install()
    
    from twisted.internet import reactor



    

GTK+ 3.0 and GObject Introspection
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
.. _core-howto-choosing-reactor-gtk3:







    
Twisted integrates with `GTK+ 3 <http://gtk.org>`_ and GObject
through `PyGObject's <http://live.gnome.org/PyGObject>`_ 
introspection using the ``gtk3reactor`` 
and ``gireactor`` reactors.





.. code-block:: python

    
    from twisted.internet import gtk3reactor
    gtk3reactor.install()
    
    from twisted.internet import reactor





.. code-block:: python

    
    from twisted.internet import gireactor # for non-GUI apps
    gireactor.install()
    
    from twisted.internet import reactor



    
GLib 3.0 introduces the concept of ``GApplication`` , a class
that handles application uniqueness in a cross-platform way and provides
its own main loop. Its counterpart ``GtkApplication`` also
handles application lifetime with respect to open windows. Twisted
supports registering these objects with the event loop, which should be
done before running the reactor:





.. code-block:: python

    
    from twisted.internet import gtk3reactor
    gtk3reactor.install()
    
    from gi.repository import Gtk
    app = Gtk.Application(...)
    
    from twisted import reactor
    reactor.registerGApplication(app)
    reactor.run()



    

wxPython
~~~~~~~~
.. _core-howto-choosing-reactor-wxpython:







    
Twisted currently supports two methods of integrating
wxPython. Unfortunately, neither method will work on all wxPython
platforms (such as GTK2 or Windows). It seems that the only
portable way to integrate with wxPython is to run it in a separate
thread. One of these methods may be sufficient if your wx app is
limited to a single platform.

    


As with :ref:`Tkinter <core-howto-choosing-reactor-tkinter>` , the support for integrating
Twisted with a `wxPython <http://www.wxpython.org>`_ 
application uses specialized support code rather than a simple reactor.





.. code-block:: python

    
    from wxPython.wx import *
    from twisted.internet import wxsupport, reactor
    
    myWxAppInstance = wxApp(0)
    wxsupport.install(myWxAppInstance)



    
However, this has issues when running on Windows, so Twisted now
comes with alternative wxPython support using a reactor. Using
this method is probably better. Initialization is done in two
stages. In the first, the reactor is installed:





.. code-block:: python

    
    from twisted.internet import wxreactor
    wxreactor.install()
    
    from twisted.internet import reactor



    
Later, once a ``wxApp`` instance has
been created, but before ``reactor.run()`` 
is called:





.. code-block:: python

    
    from twisted.internet import reactor
    myWxAppInstance = wxApp(0)
    reactor.registerWxApp(myWxAppInstance)



    
An example Twisted application that uses wxPython can be found
in ``doc/core/examples/wxdemo.py`` .

    



CoreFoundation
~~~~~~~~~~~~~~
.. _core-howto-choosing-reactor-cfreactor:







    
Twisted integrates with `PyObjC <http://pyobjc.sf.net/>`_ version 1.0. Sample applications using Cocoa and Twisted
are available in the examples directory under
``doc/core/examples/threadedselect/Cocoa`` .





.. code-block:: python

    
    from twisted.internet import cfreactor
    cfreactor.install()
    
    from twisted.internet import reactor



    

Non-Reactor GUI Integration
---------------------------


    

Tkinter
~~~~~~~
.. _core-howto-choosing-reactor-tkinter:







    
The support for `Tkinter <http://wiki.python.org/moin/TkInter>`_ doesn't use a specialized reactor.  Instead, there is
some specialized support code:





.. code-block:: python

    
    from Tkinter import *
    from twisted.internet import tksupport, reactor
    
    root = Tk()
    
    # Install the Reactor support
    tksupport.install(root)
    
    # at this point build Tk app as usual using the root object,
    # and start the program with "reactor.run()", and stop it
    # with "reactor.stop()".



    

PyUI
~~~~
.. _core-howto-choosing-reactor-pyui:







    
As with :ref:`Tkinter <core-howto-choosing-reactor-tkinter>` , the support for integrating
Twisted with a `PyUI <http://pyui.sourceforge.net>`_ 
application uses specialized support code rather than a simple reactor.





.. code-block:: python

    
    from twisted.internet import pyuisupport, reactor
    
    pyuisupport.install(args=(640, 480), kw={'renderer': 'gl'})



    
An example Twisted application that uses PyUI can be found in ``doc/core/examples/pyuidemo.py`` .

  

