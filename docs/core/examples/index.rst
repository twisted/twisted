
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Examples
========

Simple Echo server and client
-----------------------------

- :download:`simpleclient.py` - simple TCP client
- :download:`simpleserv.py` - simple TCP echo server


Chat
----

- :download:`chatserver.py` - shows how to communicate between clients


Echo server & client variants
-----------------------------

- :download:`echoserv.py` - variant on a simple TCP echo server
- :download:`echoclient.py` - variant on a simple TCP client
- :download:`echoserv_udp.py` - simplest possible UDP server
- :download:`echoclient_udp.py` - simple UDP client
- :download:`echoserv_ssl.py` - simple SSL server
- :download:`echoclient_ssl.py` - simple SSL client


AMP server & client variants
----------------------------

- :download:`ampserver.py` - do math using AMP
- :download:`ampclient.py` - do math using AMP


Perspective Broker
------------------

- :download:`pbsimple.py` - simplest possible PB server
- :download:`pbsimpleclient.py` - simplest possible PB client
- :download:`pbbenchclient.py` - benchmarking client
- :download:`pbbenchserver.py` - benchmarking server
- :download:`pbecho.py` - echo server that uses login
- :download:`pbechoclient.py` - echo client using login
- :download:`pb_exceptions.py` - example of exceptions over PB
- :download:`pbgtk2.py` - example of using GTK2 with PB
- :download:`pbinterop.py` - shows off various types supported by PB
- :download:`bananabench.py` - benchmark for banana


Cred
----

- :download:`cred.py` - Authenticate a user with an in-memory username/password database
- :download:`dbcred.py` - Using a database backend to authenticate a user


GUI
---

- :download:`wxdemo.py` - demo of wxPython integration with Twisted
- :download:`pbgtk2.py` - example of using GTK2 with PB
- :download:`pyuidemo.py` - PyUI


FTP examples
------------

- :download:`ftpclient.py` - example of using the FTP client
- :download:`ftpserver.py` - create an FTP server which serves files for anonymous users from the working directory and serves files for authenticated users from ``/home``.


Logging
-------

- :download:`twistd-logging.tac` - logging example using ILogObserver
- :download:`testlogging.py` - use twisted.python.log to log errors to standard out
- :download:`rotatinglog.py` - example of log file rotation


POSIX Specific Tricks
---------------------

- :download:`sendfd.py`, :download:`recvfd.py` - send and receive file descriptors over UNIX domain sockets


Miscellaneous
-------------

- :download:`shaper.py` - example of rate-limiting your web server
- :download:`stdiodemo.py` - example using stdio, Deferreds, LineReceiver and twisted.web.client.
- :download:`mouse.py` - example using MouseMan protocol with the SerialPort transport
- :download:`ptyserv.py` - serve shells in pseudo-terminals over TCP
- :download:`courier.py` - example of interfacing to Courier's mail filter interface
- :download:`longex.py` - example of doing arbitrarily long calculations nicely in Twisted
- :download:`longex2.py` - using generators to do long calculations
- :download:`stdin.py` - reading a line at a time from standard input without blocking the reactor
- :download:`streaming.py` - example of a push producer/consumer system
- :download:`filewatch.py` - write the content of a file to standard out one line at a time
- :download:`shoutcast.py` - example Shoutcast client
- :download:`gpsfix.py` - example using the SerialPort transport and GPS protocols to display fix data as it is received from the device
- :download:`wxacceptance.py` - acceptance tests for wxreactor
- :download:`postfix.py` - test application for PostfixTCPMapServer
- :download:`udpbroadcast.py` - broadcasting using UDP
- :download:`tls_alpn_npn_client.py` - example of TLS next-protocol negotiation on the client side using NPN and ALPN.
- :download:`tls_alpn_npn_server.py` - example of TLS next-protocol negotiation on the server side using NPN and ALPN.
