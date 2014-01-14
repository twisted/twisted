
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Twisted Mail Tutorial: Building an SMTP Client from Scratch
===========================================================






Introduction
------------



This tutorial will walk you through the creation of an extremely
simple SMTP client application.  By the time the tutorial is complete,
you will understand how to create and start a TCP client speaking the
SMTP protocol, have it connect to an appropriate mail exchange server,
and transmit a message for delivery.




For the majority of this tutorial, ``twistd`` will be used
to launch the application.  Near the end we will explore other
possibilities for starting a Twisted application.  Until then, make
sure that you have ``twistd`` installed and conveniently
accessible for use in running each of the example ``.tac``
files.





SMTP Client 1
~~~~~~~~~~~~~



The first step is to create :download:`smtpclient-1.tac` possible for use by ``twistd`` .





.. code-block:: python


    from twisted.application import service




The first line of the ``.tac`` file
imports ``twisted.application.service`` , a module which
contains many of the basic *service* classes and helper
functions available in Twisted.  In particular, we will be using
the ``Application`` function to create a new *application service* .  An *application service* simply acts as a
central object on which to store certain kinds of deployment
configuration.





.. code-block:: python


    application = service.Application("SMTP Client Tutorial")




The second line of the ``.tac`` file creates a
new *application service* and binds it to the local
name ``application`` .  ``twistd`` requires this
local name in each ``.tac`` file it runs.  It uses various
pieces of configuration on the object to determine its behavior.  For
example, ``"SMTP Client Tutorial"`` will be used as the name
of the ``.tap`` file into which to serialize application
state, should it be necessary to do so.




That does it for the first example.  We now have enough of
a ``.tac`` file to pass to ``twistd`` .  If we
run :download:`smtpclient-1.tac` using
the ``twistd`` command line:





.. code-block:: python


    twistd -ny smtpclient-1.tac




we are rewarded with the following output:





.. code-block:: console


    exarkun@boson:~/mail/tutorial/smtpclient$ twistd -ny smtpclient-1.tac
    18:31 EST [-] Log opened.
    18:31 EST [-] twistd 2.0.0 (/usr/bin/python2.4 2.4.1) starting up
    18:31 EST [-] reactor class: twisted.internet.selectreactor.SelectReactor
    18:31 EST [-] Loading smtpclient-1.tac...
    18:31 EST [-] Loaded.




As we expected, not much is going on.  We can shutdown this server
by issuing ``^C`` :





.. code-block:: console


    18:34 EST [-] Received SIGINT, shutting down.
    18:34 EST [-] Main loop terminated.
    18:34 EST [-] Server Shut Down.
    exarkun@boson:~/mail/tutorial/smtpclient$





SMTP Client 2
~~~~~~~~~~~~~



The first version of our SMTP client wasn't very interesting.  It
didn't even establish any TCP connections!  The :download:`smtpclient-2.tac` will come a little bit
closer to that level of complexity.  First, we need to import a few
more things:





.. code-block:: python


    from twisted.application import internet
    from twisted.internet import protocol




``twisted.application.internet`` is
another *application service* module.  It provides services for
establishing outgoing connections (as well as creating network
servers, though we are not interested in those parts for the
moment). ``twisted.internet.protocol`` provides base
implementations of many of the core Twisted concepts, such
as *factories* and *protocols* .




The next line of :download:`smtpclient-2.tac`
instantiates a new *client factory* .





.. code-block:: python


    smtpClientFactory = protocol.ClientFactory()




*Client factories* are responsible for
constructing *protocol instances* whenever connections are
established.  They may be required to create just one instance, or
many instances if many different connections are established, or they
may never be required to create one at all, if no connection ever
manages to be established.




Now that we have a client factory, we'll need to hook it up to the
network somehow.  The next line of ``smtpclient-2.tac`` does
just that:





.. code-block:: python


    smtpClientService = internet.TCPClient(None, None, smtpClientFactory)




We'll ignore the first two arguments
to ``internet.TCPClient`` for the moment and instead focus on
the third.  ``TCPClient`` is one of those *application service* classes.  It creates TCP connections to a specified
address and then uses its third argument, a *client factory* ,
to get a *protocol instance* .  It then associates the TCP
connection with the protocol instance and gets out of the way.




We can try to run ``smtpclient-2.tac`` the same way we
ran ``smtpclient-1.tac`` , but the results might be a little
disappointing:





.. code-block:: console


    exarkun@boson:~/mail/tutorial/smtpclient$ twistd -ny smtpclient-2.tac
    18:55 EST [-] Log opened.
    18:55 EST [-] twistd SVN-Trunk (/usr/bin/python2.4 2.4.1) starting up
    18:55 EST [-] reactor class: twisted.internet.selectreactor.SelectReactor
    18:55 EST [-] Loading smtpclient-2.tac...
    18:55 EST [-] Loaded.
    18:55 EST [-] Starting factory <twisted.internet.protocol.ClientFactory
                  instance at 0xb791e46c>
    18:55 EST [-] Traceback (most recent call last):
              File "twisted/scripts/twistd.py", line 187, in runApp
                app.runReactorWithLogging(config, oldstdout, oldstderr)
              File "twisted/application/app.py", line 128, in runReactorWithLogging
                reactor.run()
              File "twisted/internet/posixbase.py", line 200, in run
                self.mainLoop()
              File "twisted/internet/posixbase.py", line 208, in mainLoop
                self.runUntilCurrent()
            --- <exception caught here> ---
              File "twisted/internet/base.py", line 533, in runUntilCurrent
                call.func(*call.args, **call.kw)
              File "twisted/internet/tcp.py", line 489, in resolveAddress
                if abstract.isIPAddress(self.addr[0]):
              File "twisted/internet/abstract.py", line 315, in isIPAddress
                parts = string.split(addr, '.')
              File "/usr/lib/python2.4/string.py", line 292, in split
                return s.split(sep, maxsplit)
            exceptions.AttributeError: 'NoneType' object has no attribute 'split'

    18:55 EST [-] Received SIGINT, shutting down.
    18:55 EST [-] Main loop terminated.
    18:55 EST [-] Server Shut Down.
    exarkun@boson:~/mail/tutorial/smtpclient$




What happened?  Those first two arguments to ``TCPClient``
turned out to be important after all.  We'll get to them in the next
example.





SMTP Client 3
~~~~~~~~~~~~~



Version three of our SMTP client only changes one thing.  The line
from version two:





.. code-block:: python


    smtpClientService = internet.TCPClient(None, None, smtpClientFactory)




has its first two arguments changed from ``None`` to
something with a bit more meaning:





.. code-block:: python


    smtpClientService = internet.TCPClient('localhost', 25, smtpClientFactory)




This directs the client to connect to *localhost* on
port *25* .  This isn't the address we want ultimately, but it's
a good place-holder for the time being.  We can
run :download:`smtpclient-3.tac` and see what this
change gets us:





.. code-block:: console


    exarkun@boson:~/mail/tutorial/smtpclient$ twistd -ny smtpclient-3.tac
    19:10 EST [-] Log opened.
    19:10 EST [-] twistd SVN-Trunk (/usr/bin/python2.4 2.4.1) starting up
    19:10 EST [-] reactor class: twisted.internet.selectreactor.SelectReactor
    19:10 EST [-] Loading smtpclient-3.tac...
    19:10 EST [-] Loaded.
    19:10 EST [-] Starting factory <twisted.internet.protocol.ClientFactory
                  instance at 0xb791e48c>
    19:10 EST [-] Enabling Multithreading.
    19:10 EST [Uninitialized] Traceback (most recent call last):
              File "twisted/python/log.py", line 56, in callWithLogger
                return callWithContext({"system": lp}, func, *args, **kw)
              File "twisted/python/log.py", line 41, in callWithContext
                return context.call({ILogContext: newCtx}, func, *args, **kw)
              File "twisted/python/context.py", line 52, in callWithContext
                return self.currentContext().callWithContext(ctx, func, *args, **kw)
              File "twisted/python/context.py", line 31, in callWithContext
                return func(*args,**kw)
            --- <exception caught here> ---
              File "twisted/internet/selectreactor.py", line 139, in _doReadOrWrite
                why = getattr(selectable, method)()
              File "twisted/internet/tcp.py", line 543, in doConnect
                self._connectDone()
              File "twisted/internet/tcp.py", line 546, in _connectDone
                self.protocol = self.connector.buildProtocol(self.getPeer())
              File "twisted/internet/base.py", line 641, in buildProtocol
                return self.factory.buildProtocol(addr)
              File "twisted/internet/protocol.py", line 99, in buildProtocol
                p = self.protocol()
            exceptions.TypeError: 'NoneType' object is not callable

    19:10 EST [Uninitialized] Stopping factory
              <twisted.internet.protocol.ClientFactory instance at
              0xb791e48c>
    19:10 EST [-] Received SIGINT, shutting down.
    19:10 EST [-] Main loop terminated.
    19:10 EST [-] Server Shut Down.
    exarkun@boson:~/mail/tutorial/smtpclient$




A meagre amount of progress, but the service still raises an
exception.  This time, it's because we haven't specified
a *protocol class* for the factory to use.  We'll do that in
the next example.





SMTP Client 4
~~~~~~~~~~~~~



In the previous example, we ran into a problem because we hadn't
set up our *client factory's* *protocol* attribute
correctly (or at all).  ``ClientFactory.buildProtocol`` is
the method responsible for creating a *protocol instance* .  The
default implementation calls the factory's ``protocol`` attribute,
adds itself as an attribute named ``factory`` to the
resulting instance, and returns it.  In :download:`smtpclient-4.tac` , we'll correct the
oversight that caused the traceback in smtpclient-3.tac:





.. code-block:: python


    smtpClientFactory.protocol = protocol.Protocol




Running this version of the client, we can see the output is once
again traceback free:





.. code-block:: console


    exarkun@boson:~/doc/mail/tutorial/smtpclient$ twistd -ny smtpclient-4.tac
    19:29 EST [-] Log opened.
    19:29 EST [-] twistd SVN-Trunk (/usr/bin/python2.4 2.4.1) starting up
    19:29 EST [-] reactor class: twisted.internet.selectreactor.SelectReactor
    19:29 EST [-] Loading smtpclient-4.tac...
    19:29 EST [-] Loaded.
    19:29 EST [-] Starting factory <twisted.internet.protocol.ClientFactory
                  instance at 0xb791e4ac>
    19:29 EST [-] Enabling Multithreading.
    19:29 EST [-] Received SIGINT, shutting down.
    19:29 EST [Protocol,client] Stopping factory
              <twisted.internet.protocol.ClientFactory instance at
              0xb791e4ac>
    19:29 EST [-] Main loop terminated.
    19:29 EST [-] Server Shut Down.
    exarkun@boson:~/doc/mail/tutorial/smtpclient$




But what does this
mean? ``twisted.internet.protocol.Protocol`` is the
base *protocol* implementation.  For those familiar with the
classic UNIX network services, it is equivalent to
the *discard* service.  It never produces any output and it
discards all its input.  Not terribly useful, and certainly nothing
like an SMTP client.  Let's see how we can improve this in the next
example.





SMTP Client 5
~~~~~~~~~~~~~



In :download:`smtpclient-5.tac` , we will begin
to use Twisted's SMTP protocol implementation for the first time.
We'll make the obvious change, simply swapping
out ``twisted.internet.protocol.Protocol`` in favor
of ``twisted.mail.smtp.ESMTPClient`` .  Don't worry about
the *E* in *ESMTP* .  It indicates we're actually using a
newer version of the SMTP protocol.  There is
an ``SMTPClient`` in Twisted, but there's essentially no
reason to ever use it.




smtpclient-5.tac adds a new import:





.. code-block:: python


    from twisted.mail import smtp




All of the mail related code in Twisted exists beneath
the ``twisted.mail`` package.  More specifically, everything
having to do with the SMTP protocol implementation is defined in
the ``twisted.mail.smtp`` module.




Next we remove a line we added in smtpclient-4.tac:





.. code-block:: python


    smtpClientFactory.protocol = protocol.Protocol




And add a similar one in its place:





.. code-block:: python


    smtpClientFactory.protocol = smtp.ESMTPClient




Our client factory is now using a protocol implementation which
behaves as an SMTP client.  What happens when we try to run this
version?





.. code-block:: console


    exarkun@boson:~/doc/mail/tutorial/smtpclient$ twistd -ny smtpclient-5.tac
    19:42 EST [-] Log opened.
    19:42 EST [-] twistd SVN-Trunk (/usr/bin/python2.4 2.4.1) starting up
    19:42 EST [-] reactor class: twisted.internet.selectreactor.SelectReactor
    19:42 EST [-] Loading smtpclient-5.tac...
    19:42 EST [-] Loaded.
    19:42 EST [-] Starting factory <twisted.internet.protocol.ClientFactory
                  instance at 0xb791e54c>
    19:42 EST [-] Enabling Multithreading.
    19:42 EST [Uninitialized] Traceback (most recent call last):
              File "twisted/python/log.py", line 56, in callWithLogger
                return callWithContext({"system": lp}, func, *args, **kw)
              File "twisted/python/log.py", line 41, in callWithContext
                return context.call({ILogContext: newCtx}, func, *args, **kw)
              File "twisted/python/context.py", line 52, in callWithContext
                return self.currentContext().callWithContext(ctx, func, *args, **kw)
              File "twisted/python/context.py", line 31, in callWithContext
                return func(*args,**kw)
            --- <exception caught here> ---
              File "twisted/internet/selectreactor.py", line 139, in _doReadOrWrite
                why = getattr(selectable, method)()
              File "twisted/internet/tcp.py", line 543, in doConnect
                self._connectDone()
              File "twisted/internet/tcp.py", line 546, in _connectDone
                self.protocol = self.connector.buildProtocol(self.getPeer())
              File "twisted/internet/base.py", line 641, in buildProtocol
                return self.factory.buildProtocol(addr)
              File "twisted/internet/protocol.py", line 99, in buildProtocol
                p = self.protocol()
            exceptions.TypeError: __init__() takes at least 2 arguments (1 given)

    19:42 EST [Uninitialized] Stopping factory
              <twisted.internet.protocol.ClientFactory instance at
              0xb791e54c>
    19:43 EST [-] Received SIGINT, shutting down.
    19:43 EST [-] Main loop terminated.
    19:43 EST [-] Server Shut Down.
    exarkun@boson:~/doc/mail/tutorial/smtpclient$





Oops, back to getting a traceback.  This time, the default
implementation of ``buildProtocol`` seems no longer to be
sufficient.  It instantiates the protocol with no arguments,
but ``ESMTPClient`` wants at least one argument.  In the next
version of the client, we'll override ``buildProtocol`` to
fix this problem.





SMTP Client 6
~~~~~~~~~~~~~



:download:`smtpclient-6.tac` introduces
a ``twisted.internet.protocol.ClientFactory`` subclass with
an overridden ``buildProtocol`` method to overcome the
problem encountered in the previous example.





.. code-block:: python


    class SMTPClientFactory(protocol.ClientFactory):
        protocol = smtp.ESMTPClient

        def buildProtocol(self, addr):
            return self.protocol(secret=None, identity='example.com')




The overridden method does almost the same thing as the base
implementation: the only change is that it passes values for two
arguments to ``twisted.mail.smtp.ESMTPClient`` 's initializer.
The ``secret`` argument is used for SMTP authentication
(which we will not attempt yet).  The ``identity`` argument
is used as a to identify ourselves Another minor change to note is
that the ``protocol`` attribute is now defined in the class
definition, rather than tacked onto an instance after one is created.
This means it is a class attribute, rather than an instance attribute,
now, which makes no difference as far as this example is concerned.
There are circumstances in which the difference is important: be sure
you understand the implications of each approach when creating your
own factories.




One other change is required: instead of
instantiating ``twisted.internet.protocol.ClientFactory`` , we
will now instantiate ``SMTPClientFactory`` :





.. code-block:: python


    smtpClientFactory = SMTPClientFactory()




Running this version of the code, we observe that the
code **still** isn't quite traceback-free.





.. code-block:: console


    exarkun@boson:~/doc/mail/tutorial/smtpclient$ twistd -ny smtpclient-6.tac
    21:17 EST [-] Log opened.
    21:17 EST [-] twistd SVN-Trunk (/usr/bin/python2.4 2.4.1) starting up
    21:17 EST [-] reactor class: twisted.internet.selectreactor.SelectReactor
    21:17 EST [-] Loading smtpclient-6.tac...
    21:17 EST [-] Loaded.
    21:17 EST [-] Starting factory <__builtin__.SMTPClientFactory instance
                  at 0xb77fd68c>
    21:17 EST [-] Enabling Multithreading.
    21:17 EST [ESMTPClient,client] Traceback (most recent call last):
              File "twisted/python/log.py", line 56, in callWithLogger
                return callWithContext({"system": lp}, func, *args, **kw)
              File "twisted/python/log.py", line 41, in callWithContext
                return context.call({ILogContext: newCtx}, func, *args, **kw)
              File "twisted/python/context.py", line 52, in callWithContext
                return self.currentContext().callWithContext(ctx, func, *args, **kw)
              File "twisted/python/context.py", line 31, in callWithContext
                return func(*args,**kw)
            --- <exception caught here> ---
              File "twisted/internet/selectreactor.py", line 139, in _doReadOrWrite
                why = getattr(selectable, method)()
              File "twisted/internet/tcp.py", line 351, in doRead
                return self.protocol.dataReceived(data)
              File "twisted/protocols/basic.py", line 221, in dataReceived
                why = self.lineReceived(line)
              File "twisted/mail/smtp.py", line 1039, in lineReceived
                why = self._okresponse(self.code,'\n'.join(self.resp))
              File "twisted/mail/smtp.py", line 1281, in esmtpState_serverConfig
                self.tryTLS(code, resp, items)
              File "twisted/mail/smtp.py", line 1294, in tryTLS
                self.authenticate(code, resp, items)
              File "twisted/mail/smtp.py", line 1343, in authenticate
                self.smtpState_from(code, resp)
              File "twisted/mail/smtp.py", line 1062, in smtpState_from
                self._from = self.getMailFrom()
              File "twisted/mail/smtp.py", line 1137, in getMailFrom
                raise NotImplementedError
            exceptions.NotImplementedError:

    21:17 EST [ESMTPClient,client] Stopping factory
              <__builtin__.SMTPClientFactory instance at 0xb77fd68c>
    21:17 EST [-] Received SIGINT, shutting down.
    21:17 EST [-] Main loop terminated.
    21:17 EST [-] Server Shut Down.
    exarkun@boson:~/doc/mail/tutorial/smtpclient$




What we have accomplished with this iteration of the example is to
navigate far enough into an SMTP transaction that Twisted is now
interested in calling back to application-level code to determine what
its next step should be.  In the next example, we'll see how to
provide that information to it.





SMTP Client 7
~~~~~~~~~~~~~



SMTP Client 7 is the first version of our SMTP client which
actually includes message data to transmit.  For simplicity's sake,
the message is defined as part of a new class.  In a useful program
which sent email, message data might be pulled in from the filesystem,
a database, or be generated based on
user-input.  :download:`smtpclient-7.tac` , however,
defines a new class, ``SMTPTutorialClient`` , with three class
attributes (``mailFrom`` , ``mailTo`` ,
and ``mailData`` ):





.. code-block:: python


    class SMTPTutorialClient(smtp.ESMTPClient):
        mailFrom = "tutorial_sender@example.com"
        mailTo = "tutorial_recipient@example.net"
        mailData = '''\
    Date: Fri, 6 Feb 2004 10:14:39 -0800
    From: Tutorial Guy <tutorial_sender@example.com>
    To: Tutorial Gal <tutorial_recipient@example.net>
    Subject: Tutorate!

    Hello, how are you, goodbye.
    '''




This statically defined data is accessed later in the class
definition by three of the methods which are part of the
*SMTPClient callback API* .  Twisted expects each of the three
methods below to be defined and to return an object with a particular
meaning.  First, ``getMailFrom`` :





.. code-block:: python


    def getMailFrom(self):
        result = self.mailFrom
        self.mailFrom = None
        return result




This method is called to determine the *reverse-path* ,
otherwise known as the *envelope from* , of the message.  This
value will be used when sending the ``MAIL FROM`` SMTP
command.  The method must return a string which conforms to the `RFC 2821 <http://www.faqs.org/rfcs/rfc2821.html>`_ definition
of a *reverse-path* .  In simpler terms, it should be a string
like ``"alice@example.com"`` .  Only one *envelope from* is allowed by the SMTP protocol, so it cannot be a list of
strings or a comma separated list of addresses.  Our implementation
of ``getMailFrom`` does a little bit more than just return a
string; we'll get back to this in a little bit.




The next method is ``getMailTo`` :





.. code-block:: python


    def getMailTo(self):
        return [self.mailTo]




``getMailTo`` is similar to ``getMailFrom`` .  It
returns one or more RFC 2821 addresses (this time a
*forward-path* , or *envelope to* ).  Since SMTP allows
multiple recipients, ``getMailTo`` returns a list of these
addresses.  The list must contain at least one address, and even if
there is exactly one recipient, it must still be in a list.




The final callback we will define to provide information to
Twisted is ``getMailData`` :





.. code-block:: python


    def getMailData(self):
        return StringIO.StringIO(self.mailData)




This one is quite simple as well: it returns a file or a file-like
object which contains the message contents.  In our case, we return
a ``StringIO`` since we already have a string containing our
message.  If the contents of the file returned
by ``getMailData`` span multiple lines (as email messages
often do), the lines should be ``\n`` delimited (as they
would be when opening a text file in the ``"rt"`` mode):
necessary newline translation will be performed
by ``SMTPClient`` automatically.




There is one more new callback method defined in smtpclient-7.tac.
This one isn't for providing information about the messages to
Twisted, but for Twisted to provide information about the success or
failure of the message transmission to the application:





.. code-block:: python


    def sentMail(self, code, resp, numOk, addresses, log):
        print 'Sent', numOk, 'messages'




Each of the arguments to ``sentMail`` provides some
information about the success or failure of the message transmission
transaction.  ``code`` is the response code from the ultimate
command.  For successful transactions, it will be 250.  For transient
failures (those which should be retried), it will be between 400 and
499, inclusive.  For permanent failures (this which will never work,
no matter how many times you retry them), it will be between 500 and
599.





SMTP Client 8
~~~~~~~~~~~~~



Thus far we have succeeded in creating a Twisted client application
which starts up, connects to a (possibly) remote host, transmits some
data, and disconnects.  Notably missing, however, is application
shutdown.  Hitting ^C is fine during development, but it's not exactly
a long-term solution.  Fortunately, programmatic shutdown is extremely
simple.  :download:`smtpclient-8.tac`
extends ``sentMail`` with these two lines:





.. code-block:: python


    from twisted.internet import reactor
    reactor.stop()




The ``stop`` method of the reactor causes the main event
loop to exit, allowing a Twisted server to shut down.  With this
version of the example, we see that the program actually terminates
after sending the message, without user-intervention:





.. code-block:: console


    exarkun@boson:~/doc/mail/tutorial/smtpclient$ twistd -ny smtpclient-8.tac
    19:52 EST [-] Log opened.
    19:52 EST [-] twistd SVN-Trunk (/usr/bin/python2.4 2.4.1) starting up
    19:52 EST [-] reactor class: twisted.internet.selectreactor.SelectReactor
    19:52 EST [-] Loading smtpclient-8.tac...
    19:52 EST [-] Loaded.
    19:52 EST [-] Starting factory <__builtin__.SMTPClientFactory instance
                  at 0xb791beec>
    19:52 EST [-] Enabling Multithreading.
    19:52 EST [SMTPTutorialClient,client] Sent 1 messages
    19:52 EST [SMTPTutorialClient,client] Stopping factory
              <__builtin__.SMTPClientFactory instance at 0xb791beec>
    19:52 EST [-] Main loop terminated.
    19:52 EST [-] Server Shut Down.
    exarkun@boson:~/doc/mail/tutorial/smtpclient$





SMTP Client 9
~~~~~~~~~~~~~



One task remains to be completed in this tutorial SMTP client:
instead of always sending mail through a well-known host, we will look
up the mail exchange server for the recipient address and try to
deliver the message to that host.




In :download:`smtpclient-9.tac` , we'll take the
first step towards this feature by defining a function which returns
the mail exchange host for a particular domain:





.. code-block:: python


    def getMailExchange(host):
        return 'localhost'




Obviously this doesn't return the correct mail exchange host yet
(in fact, it returns the exact same host we have been using all
along), but pulling out the logic for determining which host to
connect to into a function like this is the first step towards our
ultimate goal.  Now that we have ``getMailExchange`` , we'll
call it when constructing our ``TCPClient`` service:





.. code-block:: python


    smtpClientService = internet.TCPClient(
        getMailExchange('example.net'), 25, smtpClientFactory)




We'll expand on the definition of ``getMailExchange`` in
the next example.





SMTP Client 10
~~~~~~~~~~~~~~



In the previous example we defined ``getMailExchange`` to
return a string representing the mail exchange host for a particular
domain.  While this was a step in the right direction, it turns out
not to be a very big one.  Determining the mail exchange host for a
particular domain is going to involve network traffic (specifically,
some DNS requests).  These might take an arbitrarily large amount of
time, so we need to introduce a ``Deferred`` to represent the
result of ``getMailExchange`` .  :download:`smtpclient-10.tac` redefines it
thusly:





.. code-block:: python


    def getMailExchange(host):
        return defer.succeed('localhost')




``defer.succeed`` is a function which creates a
new ``Deferred`` which already has a result, in this
case ``'localhost'`` .  Now we need to adjust
our ``TCPClient`` -constructing code to expect and properly
handle this ``Deferred`` :





.. code-block:: python


    def cbMailExchange(exchange):
        smtpClientFactory = SMTPClientFactory()

        smtpClientService = internet.TCPClient(exchange, 25, smtpClientFactory)
        smtpClientService.setServiceParent(application)

    getMailExchange('example.net').addCallback(cbMailExchange)




An in-depth exploration of ``Deferred`` s is beyond the
scope of this document.  For such a look, see
the `Deferred Reference <../../../core/howto/defer.html>`_ ``TCPClient`` until the ``Deferred``
returned by ``getMailExchange`` fires.  Once it does, we
proceed normally through the creation of
our ``SMTPClientFactory`` and ``TCPClient`` , as well
as set the ``TCPClient`` 's service parent, just as we did in
the previous examples.





SMTP Client 11
~~~~~~~~~~~~~~



At last we're ready to perform the mail exchange lookup.  We do
this by calling on an object provided specifically for this
task, ``twisted.mail.relaymanager.MXCalculator`` :





.. code-block:: python


    def getMailExchange(host):
        def cbMX(mxRecord):
            return str(mxRecord.name)
        return relaymanager.MXCalculator().getMX(host).addCallback(cbMX)




Because ``getMX`` returns a ``Record_MX`` object
rather than a string, we do a little bit of post-processing to get the
results we want.  We have already converted the rest of the tutorial
application to expect a ``Deferred``
from ``getMailExchange`` , so no further changes are
required.  :download:`smtpclient-11.tac` completes
this tutorial by being able to both look up the mail exchange host for
the recipient domain, connect to it, complete an SMTP transaction,
report its results, and finally shut down the reactor.





..  TODO: write a conclusion to wrap it up

