
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Banana Protocol Specifications
==============================






Introduction
------------

Banana is an efficient, extendable protocol for sending and receiving s-expressions.
A s-expression in this context is a list composed of bytes, integers, large integers, floats and/or s-expressions.
Unicode is not supported (but can be encoded to and decoded from bytes on the way into and out of Banana).
Unsupported types must be converted into a supported type before sending them with Banana.


Banana Encodings
----------------


    

The banana protocol is a stream of data composed of elements. Each element has the
following general structure - first, the length of element encoded in base-128, least significant
bit first. For example length 4674 will be sent as ``0x42 0x24`` . For certain element
types the length will be omitted (e.g. float) or have a different meaning (it is the actual
value of integer elements).


    



Following the length is a delimiter byte, which tells us what kind of element this
is. Depending on the element type, there will then follow the number of bytes specified
in the length. The byte's high-bit will always be set, so that we can differentiate
between it and the length (since the length bytes use 128-base, their high bit will
never be set).


    



Element Types
-------------


    

Given a series of bytes that gave us length N, these are the different delimiter bytes:


    




      
List -- 0x80
      
      
  The following bytes are a list of N elements.  Lists may be nested,
  and a child list counts as only one element to its parent (regardless
  of how many elements the child list contains).

Integer -- 0x81
      
  The value of this element is the positive integer N. Following bytes are not part of this element. Integers can have values of 0 <= N <= 2147483647.

String -- 0x82
      
  The following N bytes are a string element.

Negative Integer -- 0x83
      
  The value of this element is the integer N * -1, i.e. -N. Following bytes are not part of this element. Negative integers can have values of 0 >= -N >= -2147483648.

Float - 0x84
      
  The next 8 bytes are the float encoded in IEEE 754 floating-point "double format" bit layout.
  No length bytes should have been defined.

Large Integer -- 0x85
      
  The value of this element is the positive large integer N. Following bytes are not part of this element. Large integers have no size limitation.

Large Negative Integer -- 0x86
      
  The value of this element is the negative large integer -N. Following bytes are not part of this element. Large integers have no size limitation.



    



Large integers are intended for arbitrary length integers. Regular integers types (positive and negative) are limited to 32-bit values.


    



Examples
~~~~~~~~


    

Here are some examples of elements and their encodings - the type bytes are marked in bold:


    




      
``1`` 
      
  ``0x01 **0x81**``

``-1`` 
      
  ``0x01 **0x83**``

``1.5`` 
      
  ``**0x84**  0x3f 0xf8 0x00 0x00 0x00 0x00 0x00 0x00``

``"hello"`` 
      
  ``0x05 **0x82**  0x68 0x65 0x6c 0x6c 0x6f``

``[]`` 
      
  ``0x00 **0x80**``

``[1, 23]`` 
      
  ``0x02 **0x80**  0x01 **0x81**  0x17 **0x81**``

``123456789123456789`` 
      
  ``0x15 0x3e 0x41 0x66 0x3a 0x69 0x26 0x5b 0x01 **0x85**``

``[1, ["hello"]]`` 
      
  ``0x02 **0x80**  0x01 **0x81**  0x01 **0x80**  0x05 **0x82**  0x68 0x65 0x6c 0x6c 0x6f``



    



Profiles
--------

    
    

The Banana protocol is extendable. Therefore, it supports the concept of profiles. Profiles allow
developers to extend the banana protocol, adding new element types, while still keeping backwards
compatibility with implementations that don't support the extensions. The profile used in each
session is determined at the handshake stage (see below.)


    



A profile is specified by a unique string. This specification defines two profiles
- ``"none"`` and ``"pb"`` . The ``"none"`` profile is the standard
profile that should be supported by all Banana implementations.
Additional profiles may be added in the future.

Extensions defined by a profile may only be used if that profile has been selected by client and server.


The ``"none"``  Profile
~~~~~~~~~~~~~~~~~~~~~~~


    

The ``"none"`` profile is identical to the delimiter types listed above. It is highly recommended
that all Banana clients and servers support the ``"none"`` profile.


    



The ``"pb"``  Profile
~~~~~~~~~~~~~~~~~~~~~


    

The ``"pb"`` profile is intended for use with the Perspective Broker protocol, that runs on top
of Banana. Basically, it converts commonly used PB strings into shorter versions, thus
minimizing bandwidth usage. It starts with a single byte, which tells us to which string element
to convert it, and ends with the delimiter byte, ``0x87`` , which should not be prefixed
by a length.

    
    




      
0x01 
  'None'

0x02 
  'class'

0x03 
  'dereference'

0x04 
  'reference'

0x05 
  'dictionary'

0x06 
  'function'

0x07 
  'instance'

0x08 
  'list'

0x09 
  'module'

0x0a 
  'persistent'

0x0b 
  'tuple'

0x0c 
  'unpersistable'

0x0d 
  'copy'

0x0e 
  'cache'

0x0f 
  'cached'

0x10 
  'remote'

0x11 
  'local'

0x12 
  'lcache'

0x13 
  'version'

0x14 
  'login'

0x15 
  'password'

0x16 
  'challenge'

0x17 
  'logged_in'

0x18 
  'not_logged_in'

0x19 
  'cachemessage'

0x1a 
  'message'

0x1b 
  'answer'

0x1c 
  'error'

0x1d 
  'decref'

0x1e 
  'decache'

0x1f 
  'uncache'



    



Protocol Handshake and Behaviour
--------------------------------


    

The initiating side of the connection will be referred to as "client" , and the other
side as "server" .


    



Upon connection, the server will send the client a list of string elements, signifying
the profiles it supports. It is recommended that ``"none"`` be included in this list. The client
then sends the server a string from this list, telling the server which profile it wants to
use. At this point the whole session will use this profile.

    
    



Once a profile has been established, the two sides may start exchanging elements. There is no
limitation on order or dependencies of messages. Any such limitation (e.g. "server can only send an element to client in response to a request from client" ) is application specific.


    



Upon receiving illegal messages, failed handshakes, etc., a Banana client or server should
close its connection.


  

