
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
are :api:`twisted.internet.interfaces.IReactorCore <IReactorCore>` , 
:api:`twisted.internet.interfaces.IReactorTCP <IReactorTCP>` , 
:api:`twisted.internet.interfaces.IReactorSSL <IReactorSSL>` , 
:api:`twisted.internet.interfaces.IReactorUNIX <IReactorUNIX>` , 
:api:`twisted.internet.interfaces.IReactorUDP <IReactorUDP>` , 
:api:`twisted.internet.interfaces.IReactorTime <IReactorTime>` , 
:api:`twisted.internet.interfaces.IReactorProcess <IReactorProcess>` , 
:api:`twisted.internet.interfaces.IReactorMulticast <IReactorMulticast>` 
and :api:`twisted.internet.interfaces.IReactorThreads <IReactorThreads>` .
The reactor APIs allow non-persistent calls to be made.




Twisted Internet also covers the interfaces for the various transports,
in :api:`twisted.internet.interfaces.ITransport <ITransport>` 
and friends. These interfaces allow Twisted network code to be written without
regard to the underlying implementation of the transport.




The :api:`twisted.internet.interfaces.IProtocolFactory <IProtocolFactory>` 
dictates how factories, which are usually a large part of third party code, are
written.



