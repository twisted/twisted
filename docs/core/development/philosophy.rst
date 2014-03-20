
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Philosophy
==========






Abstraction Levels
------------------



When implementing interfaces to the operating system or
the network, provide two interfaces:





- One that doesn't hide platform specific or library specific
  functionality.
  For example, you can use file descriptors on Unix, and Win32 events on
  Windows.
- One that provides a high level interface hiding platform specific
  details.
  E.g. process running uses same API on Unix and Windows, although
  the implementation is very different.





Restated in a more general way:





- Provide all low level functionality for your specific domain,
  without limiting the policies and decisions the user can make.
- Provide a high level abstraction on top of the low level
  implementation (or implementations) which implements the
  common use cases and functionality that is used in most cases.






Learning Curves
---------------



Require the minimal amount of work and learning on part of the
user to get started. If this means they have less functionality,
that's OK, when they need it they can learn a bit more. This
will also lead to a cleaner, easier to test design.




For example - using twistd is a great way to deploy applications.
But to get started you don't need to know about it.  Later on you can
start using twistd, but its usage is optional.



