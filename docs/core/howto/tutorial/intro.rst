
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

The Evolution of Finger: building a simple finger service
=========================================================






Introduction
------------



This is the first part of the Twisted tutorial :doc:`Twisted from Scratch, or The Evolution of Finger <index>` .




If you're not familiar with 'finger' it's probably because it's not used as
much nowadays as it used to be. Basically, if you run ``finger nail`` 
or ``finger nail@example.com`` the target computer spits out some
information about the user named ``nail`` . For instance:





.. code-block:: console

    
    Login: nail                           Name: Nail Sharp
    Directory: /home/nail                 Shell: /usr/bin/sh
    Last login Wed Mar 31 18:32 2004 (PST)
    New mail received Thu Apr  1 10:50 2004 (PST)
         Unread since Thu Apr  1 10:50 2004 (PST)
    No Plan.




If the target computer does not have
the ``fingerd`` :ref:`daemon <core-howto-glossary-daemon>` 
running you'll get a "Connection Refused" error. Paranoid sysadmins
keep ``fingerd`` off or limit the output to hinder crackers
and harassers. The above format is the standard ``fingerd`` 
default, but an alternate implementation can output anything it wants,
such as automated responsibility status for everyone in an
organization. You can also define pseudo "users", which are
essentially keywords.




This portion of the tutorial makes use of factories and protocols as
introduced in the :doc:`Writing a TCP Server howto <../servers>` and
deferreds as introduced in :doc:`Using Deferreds <../defer>` 
and :doc:`Generating Deferreds <../gendefer>` . Services and
applications are discussed in :doc:`Using the Twisted Application Framework <../application>` .




By the end of this section of the tutorial, our finger server will answer
TCP finger requests on port 1079, and will read data from the web.





Refuse Connections
------------------




:download:`finger01.py <listings/finger/finger01.py>`

.. literalinclude:: listings/finger/finger01.py


This example only runs the reactor. It will consume almost no CPU
resources. As it is not listening on any port, it can't respond to network
requests — nothing at all will happen until we interrupt the program.  At
this point if you run ``finger nail`` or ``telnet localhost 1079`` , you'll get a "Connection refused" error since there's no daemon
running to respond.  Not very useful, perhaps — but this is the skeleton
inside which the Twisted program will grow.




As implied above, at various points in this tutorial you'll want to
observe the behavior of the server being developed.  Unless you have a
finger program which can use an alternate port, the easiest way to do this
is with a telnet client.  ``telnet localhost 1079`` will connect to
the local host on port 1079, where a finger server will eventually be
listening.





The Reactor
~~~~~~~~~~~



You don't call Twisted, Twisted calls you. The :api:`twisted.internet.reactor <reactor>` is Twisted's main event loop, similar to
the main loop in other toolkits available in Python (Qt, wx, and Gtk). There is
exactly one reactor in any running Twisted application. Once started it loops
over and over again, responding to network events and making scheduled calls to
code.




Note that there are actually several different reactors to choose
from; ``from twisted.internet import reactor`` returns the
current reactor.  If you haven't chosen a reactor class yet, it
automatically chooses the default.  See
the :doc:`Reactor Basics HOWTO <../reactor-basics>` for
more information.





Do Nothing
----------




:download:`finger02.py <listings/finger/finger02.py>`

.. literalinclude:: listings/finger/finger02.py


Here, ``reactor.listenTCP`` opens port 1079. (The number 1079 is a
reminder that eventually we want to run on port 79, the standard port for
finger servers.)  The specified factory, ``FingerFactory`` , is used to
handle incoming requests on that port.  Specifically, for each request, the
reactor calls the factory's ``buildProtocol`` method, which in this
case causes ``FingerProtocol`` to be instantiated. Since the protocol
defined here does not actually respond to any events, connections to 1079 will
be accepted, but the input ignored.




A Factory is the proper place for data that you want to make available to
the protocol instances, since the protocol instances are garbage collected when
the connection is closed.






Drop Connections
----------------




:download:`finger03.py <listings/finger/finger03.py>`

.. literalinclude:: listings/finger/finger03.py


Here we add to the protocol the ability to respond to the event of beginning
a connection — by terminating it.  Perhaps not an interesting behavior,
but it is already close to behaving according to the letter of the standard
finger protocol. After all, there is no requirement to send any data to the
remote connection in the standard.  The only problem, as far as the standard is
concerned, is that we terminate the connection too soon. A client which is slow
enough will see his ``send()`` of the username result in an error.






Read Username, Drop Connections
-------------------------------




:download:`finger04.py <listings/finger/finger04.py>`

.. literalinclude:: listings/finger/finger04.py


Here we make ``FingerProtocol`` inherit from :api:`twisted.protocols.basic.LineReceiver <LineReceiver>` , so that we get data-based
events on a line-by-line basis. We respond to the event of receiving the line
with shutting down the connection.




If you use a telnet client to interact with this server, the result will
look something like this:





.. code-block:: console

    
    $ telnet localhost 1079
    Trying 127.0.0.1...
    Connected to localhost.localdomain.
    alice
    Connection closed by foreign host.




Congratulations, this is the first standard-compliant version of the code.
However, usually people actually expect some data about users to be
transmitted.





Read Username, Output Error, Drop Connections
---------------------------------------------




:download:`finger05.py <listings/finger/finger05.py>`

.. literalinclude:: listings/finger/finger05.py


Finally, a useful version. Granted, the usefulness is somewhat limited by
the fact that this version only prints out a "No such user" message. It
could be used for devastating effect in honey-pots (decoy servers), of
course.






Output From Empty Factory
-------------------------




:download:`finger06.py <listings/finger/finger06.py>`

.. literalinclude:: listings/finger/finger06.py


The same behavior, but finally we see what usefulness the
factory has: as something that does not get constructed for
every connection, it can be in charge of the user database.
In particular, we won't have to change the protocol if
the user database back-end changes.






Output from Non-empty Factory
-----------------------------




:download:`finger07.py <listings/finger/finger07.py>`

.. literalinclude:: listings/finger/finger07.py


Finally, a really useful finger database. While it does not
supply information about logged in users, it could be used to
distribute things like office locations and internal office
numbers. As hinted above, the factory is in charge of keeping
the user database: note that the protocol instance has not
changed. This is starting to look good: we really won't have
to keep tweaking our protocol.






Use Deferreds
-------------




:download:`finger08.py <listings/finger/finger08.py>`

.. literalinclude:: listings/finger/finger08.py


But, here we tweak it just for the hell of it. Yes, while the
previous version worked, it did assume the result of getUser is
always immediately available. But what if instead of an in-memory
database, we would have to fetch the result from a remote Oracle server?  By
allowing getUser to return a Deferred, we make it easier for the data to be
retrieved asynchronously so that the CPU can be used for other tasks in the
meanwhile.




As described in the :doc:`Deferred HOWTO <../defer>` , Deferreds
allow a program to be driven by events.  For instance, if one task in a program
is waiting on data, rather than have the CPU (and the program!) idly waiting
for that data (a process normally called 'blocking'), the program can perform
other operations in the meantime, and waits for some signal that data is ready
to be processed before returning to that process.




In brief, the code in ``FingerFactory`` above creates a
Deferred, to which we start to attach *callbacks* .  The
deferred action in ``FingerFactory`` is actually a
fast-running expression consisting of one dictionary
method, ``get`` . Since this action can execute without
delay, ``FingerFactory.getUser`` 
uses ``defer.succeed`` to create a Deferred which already has
a result, meaning its return value will be passed immediately to the
first callback function, which turns out to
be ``FingerProtocol.writeResponse`` .  We've also defined
an *errback* (appropriately
named ``FingerProtocol.onError`` ) that will be called instead
of ``writeResponse`` if something goes wrong.





Run 'finger' Locally
--------------------




:download:`finger09.py <listings/finger/finger09.py>`

.. literalinclude:: listings/finger/finger09.py


This example also makes use of a
Deferred. ``twisted.internet.utils.getProcessOutput`` is a
non-blocking version of Python's ``commands.getoutput`` : it
runs a shell command (``finger`` , in this case) and captures
its standard output.  However, ``getProcessOutput`` returns a
Deferred instead of the output itself.
Since ``FingerProtocol.lineReceived`` is already expecting a
Deferred to be returned by ``getUser`` , it doesn't need to be
changed, and it returns the standard output as the finger result.




Note that in this case the shell's built-in ``finger`` command is
simply run with whatever arguments it is given. This is probably insecure, so
you probably don't want a real server to do this without a lot more validation
of the user input. This will do exactly what the standard version of the finger
server does.





Read Status from the Web
------------------------



The web. That invention which has infiltrated homes around the
world finally gets through to our invention. In this case we use the
built-in Twisted web client
via ``twisted.web.client.getPage`` , a non-blocking version of
Python's :func:`urllib2.urlopen(URL).read <urllib2.urlopen>` .
Like ``getProcessOutput`` it returns a Deferred which will be
called back with a string, and can thus be used as a drop-in
replacement.




Thus, we have examples of three different database back-ends, none of which
change the protocol class. In fact, we will not have to change the protocol
again until the end of this tutorial: we have achieved, here, one truly usable
class.





:download:`finger10.py <listings/finger/finger10.py>`

.. literalinclude:: listings/finger/finger10.py



Use Application
---------------



Up until now, we faked. We kept using port 1079, because really, who wants to
run a finger server with root privileges? Well, the common solution
is "privilege shedding" : after binding to the network, become a different,
less privileged user. We could have done it ourselves, but Twisted has a
built-in way to do it. We will create a snippet as above, but now we will define
an application object. That object will have ``uid`` 
and ``gid`` attributes. When running it (later we will see how) it will
bind to ports, shed privileges and then run.




Read on to find out how to run this code using the twistd utility.





twistd
------



This is how to run "Twisted Applications" — files which define an
'application'. A daemon is expected to adhere to certain behavioral standards
so that standard tools can stop/start/query them.  If a Twisted application is
run via twistd, the TWISTed Daemonizer, all this behavioral stuff will be
handled for you. twistd does everything a daemon can be expected to —
shuts down stdin/stdout/stderr, disconnects from the terminal and can even
change runtime directory, or even the root filesystems. In short, it does
everything so the Twisted application developer can concentrate on writing his
networking code.





.. code-block:: console

    
    root% twistd -ny finger11.tac # just like before
    root% twistd -y finger11.tac # daemonize, keep pid in twistd.pid
    root% twistd -y finger11.tac --pidfile=finger.pid
    root% twistd -y finger11.tac --rundir=/
    root% twistd -y finger11.tac --chroot=/var
    root% twistd -y finger11.tac -l /var/log/finger.log
    root% twistd -y finger11.tac --syslog # just log to syslog
    root% twistd -y finger11.tac --syslog --prefix=twistedfinger # use given prefix




There are several ways to tell twistd where your application is; here we
show how it is done using the ``application`` global variable in a
Python source file (a :ref:`Twisted Application
Configuration <core-howto-glossary-tac>` file).





:download:`finger11.tac <listings/finger/finger11.tac>`

.. literalinclude:: listings/finger/finger11.tac


Instead of using ``reactor.listenTCP`` as in the above
examples, here we are using its application-aware
counterpart, ``internet.TCPServer`` .  Notice that when it is
instantiated, the application object itself does not reference either
the protocol or the factory.  Any services (such as TCPServer) which
have the application as their parent will be started when the
application is started by twistd.  The application object is more
useful for returning an object that supports the :api:`twisted.application.service.IService <IService>` , :api:`twisted.application.service.IServiceCollection <IServiceCollection>` , :api:`twisted.application.service.IProcess <IProcess>` ,
and :api:`twisted.persisted.sob.IPersistable <sob.IPersistable>` 
interfaces with the given parameters; we'll be seeing these in the
next part of the tutorial. As the parent of the TCPServer we opened,
the application lets us manage the TCPServer.




With the daemon running on the standard finger port, you can test it with
the standard finger command: ``finger moshez`` .



