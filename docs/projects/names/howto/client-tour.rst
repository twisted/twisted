:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

A Guided Tour of twisted.names.client
=====================================
Twisted Names includes multiple client APIs, at varying levels of abstraction.

In this section:

 - You will learn about the high level client API
 - You will learn about how you can use the client API interactively from the Python shell for DNS debugging and diagnostics
 - You will learn about the IResolverSimple and the IResolver interfaces,
   the implementations of those interfaces and when to use them.
 - You will learn how to customise how the reactor carries out hostname resolution
 - You will also be introduced to some of the low level interfaces

twisted.names.client -- A high level DNS client API
---------------------------------------------------
