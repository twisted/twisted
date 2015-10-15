
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Security
========





We need to do a full audit of Twisted, module by module.
This document list the sort of things you want to look for
when doing this, or when writing your own code.





Bad input
---------



Any place we receive untrusted data, we need to be careful.
In some cases we are not careful enough. For example, in HTTP
there are many places where strings need to be converted to
ints, so we use ``int()`` . The problem
is that this well accept negative numbers as well, whereas
the protocol should only be accepting positive numbers.





Resource Exhaustion and DoS
---------------------------



Make sure we never allow users to create arbitrarily large
strings or files. Some of the protocols still have issues
like this. Place a limit which allows reasonable use but
will cut off huge requests, and allow changing of this limit.




Another operation to look out for are exceptions. They can fill
up logs and take a lot of CPU time to render in web pages.



