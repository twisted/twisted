Porting to Python 3
===================

Introduction
------------

Twisted is currently being ported to work with Python 3.5+.
This document covers Twisted-specific issues in porting your code to Python 3.

Most, but not all, of Twisted has been ported, and therefore only a subset of modules are installed under Python 3.
You can see the remaining modules that need to be ported at :api:`twisted.python._setup.notPortedModules <twisted.python._setup.notPortedModules>`, if it is not listed there, then most of all of that module will be ported.


API Differences
---------------




twisted.python.failure
~~~~~~~~~~~~~~~~~~~~~~



:api:`twisted.python.failure.Failure.trap <Failure.trap>`
raises itself (i.e. a :api:`twisted.python.failure.Failure <Failure>` ) in Python 2. In Python 3,
the wrapped exception will be re-raised.





Byte Strings and Text Strings
-----------------------------



Several APIs which on Python 2 accepted or produced byte strings
(instances of ``str`` , sometimes just called *bytes* ) have
changed to accept or produce text strings (instances of ``str`` ,
sometimes just called *text* or *unicode* ) on Python 3.




From ``twisted.internet.address`` , the ``IPv4Address``
and ``IPv6Address`` classes have had two attributes change from
byte strings to text strings: ``type`` and ``host`` .




``twisted.python.log`` has shifted significantly towards text
strings from byte strings.  Logging events, particular those produced by a
call like ``msg("foo")`` , must now be text strings.  Consequently,
on Python 3, event dictionaries passed to log observes will contain text
strings where they previously contained byte strings.




``twisted.python.runtime.platformType`` and the return value
from ``twisted.python.runtime.Platform.getType`` are now both text
strings.




``twisted.python.filepath.FilePath`` has *not* changed.
It supports only byte strings.  This will probably require applications to
update their usage of ``FilePath`` , at least to pass explicit byte
string literals rather than "native" string literals (which are text on
Python 3).




``reactor.addSystemEventTrigger`` arguments that were
previously byte strings are now native strings.




``twisted.names.dns`` deals with strings with a wide range of
meanings, often several for each DNS record type.  Most of these strings
have remained as byte strings, which will probably require application
updates (for the reason given in the ``FilePath`` section above).
Some strings have changed to text strings, though.  Any string representing
a human readable address (for
example, ``Record_A`` 's ``address`` parameter) is now a
text string.  Additionally, time-to-live (ttl) values given as strings must
now be given as text strings.




``twisted.web.resource.IResource`` continues to deal with URLs
and all URL-derived values as byte strings.




``twisted.web.resource.ErrorPage`` has several string attributes
(``template`` , ``brief`` , and ``detail`` ) which
were previously byte strings.  On Python 3 only, these must now be text
strings.
