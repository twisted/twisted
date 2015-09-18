
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

PB Limits
=========





There are a number of limits you might encounter when using Perspective
Broker.  This document is an attempt to prepare you for as many of them as
possible so you can avoid them or at least recognize them when you do run
into them.

  



Banana Limits
-------------


  
Perspective Broker is implemented in terms of a simpler, less
functional protocol called Banana.  Twisted's implementation of Banana
imposes a limit on the length of any sequence-like data type.  This applies
directly to lists and strings and indirectly to dictionaries, instances and
other types.  The purpose of this limit is to put an upper bound on the
amount of memory which will be allocated to handle a message received over
the network.  Without, a malicious peer could easily perform a denial of
service attack resulting in exhaustion of the receiver's memory.  The basic
limit is 640 * 1024 bytes, defined by ``twisted.spread.banana.SIZE_LIMIT`` .
It's possible to raise this limit by changing this value (but take care to
change it on both sides of the connection).

  


Another limit imposed by Twisted's Banana implementation is a limit on
the size of long integers.  The purpose of this limit is the same as the 
``SIZE_LIMIT`` .  By default, only integers between -2 ** 448 and 2
** 448 (exclusive) can be transferred.  This limit can be changed using 
:api:`twisted.spread.banana.setPrefixLimit <twisted.spread.banana.setPrefixLimit>` .

  



Perspective Broker Limits
-------------------------


  
Perspective Broker imposes an additional limit on top of these lower
level limits.  The number of local objects for which remote references may
exist at a single time over a single connection, by default, is limited to
1024, defined by ``twisted.spread.pb.MAX_BROKER_REFS`` .  This limit
also exists to prevent memory exhaustion attacks.



