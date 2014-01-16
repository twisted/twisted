
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

The Basics
==========






Application
-----------



Twisted programs usually work
with :api:`twisted.application.service.Application <twisted.application.service.Application>` .
This class usually holds all persistent configuration of a running
server -- ports to bind to, places where connections to must be kept
or attempted, periodic actions to do and almost everything else. It is
the root object in a tree of services implementing :api:`twisted.application.service.IService <IService>` .




Other HOWTOs describe how to write custom code for Applications,
but this one describes how to use already written code (which can be
part of Twisted or from a third-party Twisted plugin developer).  The
Twisted distribution comes with an important tool to deal with
Applications, ``twistd`` .




``Application`` s are just Python objects, which can
be created and manipulated in the same ways as any other object.





twistd
------
.. _core-howto-basics-twistd:








The Twisted Daemon is a program that knows how to run Applications.
This program
is ``twistd(1)`` .  Strictly
speaking, ``twistd`` is not necessary --
fetching the application, getting the ``IService`` component,
calling ``startService`` , scheduling ``stopService`` when
the reactor shuts down, and then calling ``reactor.run()`` could be
done manually. ``twistd(1)`` , however, supplies 
many options which are highly useful for program set up.




``twistd`` supports choosing a reactor (for more on
reactors, see :doc:`Choosing a Reactor <choosing-reactor>` ), logging
to a logfile, daemonizing and more. ``twistd`` supports all
Applications mentioned above -- and an additional one. Sometimes
it is convenient to write the code for building a class in straight
Python. One big source of such Python files is the ``doc/examples`` 
directory. When a straight Python file which defines an ``Application`` 
object called ``application`` is used, use the ``-y`` 
option.




When ``twistd`` runs, it records its process
id in a ``twistd.pid`` file (this can be configured via a
command line switch). In order to shutdown
the ``twistd`` process, kill that pid (usually
you would do ``kill `cat twistd.pid``` ).




As always, the gory details are in the manual page.





OS Integration
--------------




If you have an Application that runs
with ``twistd`` , you can easily deploy it on
RedHat Linux or Debian GNU/Linux based systems using
the ``tap2deb`` 
or ``tap2rpm`` tools. These take a Twisted
Application file (of any of the supported formats — Python source, XML
or pickle), and build a Debian or RPM package (respectively) that
installs the Application as a system service. The package includes the
Application file, a default ``/etc/init.d/`` script that
starts and stops the process with twistd, and post-installation
scripts that configure the Application to be run in the appropriate
init levels.





..  Is "note" really the right class to be using here? 

.. note::

    ``tap2rpm`` and ``tap2deb`` do not package your entire application and
    dependent code, just the Twisted Application file. You will need to find
    some other way to package your Python code, such as `distutils
    <http://docs.python.org/library/distutils.html>`_ ' ``bdist_rpm`` command.





For more savvy users, these tools also generate the source package, allowing
you to modify and polish things which automated software cannot detect (such as
dependencies or relationships to virtual packages).



