
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Overview of Twisted Internet
============================





Twisted Internet is a collection of compatible event-loops for Python.
It contains the code to dispatch events to interested observers and a portable
API so that observers need not care about which event loop is running. Thus,
it is possible to use the same code for different loops, from Twisted's basic,
yet portable, ``select`` -based loop to the loops of various GUI
toolkits like GTK+ or Tk.




Twisted Internet contains the various interfaces to the reactor
API, whose usage is documented in the low-level chapter. Those APIs
are :py:class:`IReactorCore <twisted.internet.interfaces.IReactorCore>` , 
:py:class:`IReactorTCP <twisted.internet.interfaces.IReactorTCP>` , 
:py:class:`IReactorSSL <twisted.internet.interfaces.IReactorSSL>` , 
:py:class:`IReactorUNIX <twisted.internet.interfaces.IReactorUNIX>` , 
:py:class:`IReactorUDP <twisted.internet.interfaces.IReactorUDP>` , 
:py:class:`IReactorTime <twisted.internet.interfaces.IReactorTime>` , 
:py:class:`IReactorProcess <twisted.internet.interfaces.IReactorProcess>` , 
:py:class:`IReactorMulticast <twisted.internet.interfaces.IReactorMulticast>` 
and :py:class:`IReactorThreads <twisted.internet.interfaces.IReactorThreads>` .
The reactor APIs allow non-persistent calls to be made.




Twisted Internet also covers the interfaces for the various transports,
in :py:class:`ITransport <twisted.internet.interfaces.ITransport>` 
and friends. These interfaces allow Twisted network code to be written without
regard to the underlying implementation of the transport.




The :py:class:`IProtocolFactory <twisted.internet.interfaces.IProtocolFactory>` 
dictates how factories, which are usually a large part of third party code, are
written.



