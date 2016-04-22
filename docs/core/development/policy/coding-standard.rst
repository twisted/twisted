Twisted Coding Standard
=======================

Naming
------

Try to choose names which are both easy to remember and meaningful.
Some silliness is OK at the module naming level (see :api:`twisted.spread <twisted.spread>` ...) but when choosing class names, be as precise as possible.

Try to avoid terms that may have existing definitions or uses.
This rule is often broken, since it is incredibly difficult, as most normal words have already been taken by some other software.
As an example, using the term "reactor" elsewhere in Twisted for something that is not an implementor of ``IReactor`` adds additional meaning to the word and will cause confusion.

More importantly, try to avoid meaningless words.
In particular, words like "handler", "processor", "engine", "manager", and "component" don't really indicate what something does, only that it does *something*.

Use American spelling in both names and docstrings.
For compound technical terms such as 'filesystem', use a non-hyphenated spelling in both docstrings and code in order to avoid unnecessary capitalization.


Testing
-------

Overview
~~~~~~~~

Twisted development should always be `test-driven <http://en.wikipedia.org/wiki/Test-driven_development>`_ .
The complete test suite in the head of the SVN trunk is required to be passing on `supported platforms <http://buildbot.twistedmatrix.com/supported>`_ at all times.
Regressions in the test suite are addressed by reverting whatever revisions introduced them.


Test Suite
~~~~~~~~~~

.. note::

   The :doc:`test standard <test-standard>` contains more in-depth information on this topic.
   What follows is intended to be a synopsis of the most important points.

The Twisted test suite is spread across many subpackages of the ``twisted`` package.
Many older tests are in ``twisted.test`` .
Others can be found at places such as ``twisted.web.test`` (for ``twisted.web`` tests) or ``twisted.internet.test`` (for ``twisted.internet`` tests).
The latter arrangement, ``twisted.somepackage.test``, is preferred for new tests except when a test module already exists in ``twisted.test`` .

Parts of the Twisted test suite may serve as good examples of how to write tests for Twisted or for Twisted-based libraries (newer parts of the test suite are generally better examples than older parts - check when the code you are looking at was written before you use it as an example of what you should write).
The names of test modules must begin with ``test_`` so that they are automatically discoverable by test runners such as Trial.
Twisted's unit tests are written using :api:`twisted.trial <twisted.trial>`, an xUnit library which has been extensively customized for use in testing Twisted and Twisted-based libraries.

Implementation (i.e., non-test) source files should begin with a ``test-case-name`` tag which gives the name of any test modules or packages which exercise them.
This lets tools discover a subset of the entire test suite which they can run first to find tests which might be broken by a particular change.

All unit test methods should have docstrings specifying at a high level the intent of the test.
That is, a description that users of the method would understand.

If you modify, or write a new, HOWTO, please read the :doc:`documentation writing standard <writing-standard>`.


Copyright Header
----------------

Whenever a new file is added to the repository, add the following license header at the top of the file:

.. code-block:: python

    # Copyright (c) Twisted Matrix Laboratories.
    # See LICENSE for details.


When you update existing files, if there is no copyright header, add one.


Whitespace
----------

Indentation is 4 spaces per indent.
Tabs are not allowed.
It is preferred that every block appears on a new line, so that control structure indentation is always visible.

Lines are flowed at 79 columns.
They must not have trailing whitespace.
Long lines must be wrapped using implied line continuation inside parentheses; backslashes aren't allowed.
To handle long import lines, please wrap them inside parentheses:

.. code-block:: python

    from very.long.package import (foo, bar, baz,
                                   qux, quux, quuux)


Top-level classes and functions must be separated with 3 blank lines, and class-level functions with 2 blank lines.
The control-L (i.e. ``^L``) form feed character must not be used.


Modules
-------

Modules must be named in all lower-case, preferably short, single words.
If a module name contains multiple words, they may be separated by underscores or not separated at all.

Modules must have a copyright message, a docstring, and a reference to a test module that contains the bulk of its tests.
New modules must have the ``absolute_import``, ``division``, and optionally the ``print_function`` imports from the ``__future__`` module.

Use this template:

:download:`new_module_template.py <../listings/new_module_template.py>`

.. literalinclude:: ../listings/new_module_template.py


In most cases, modules should contain more than one class, function, or method; if a module contains only one object, consider refactoring to include more related functionality in that module.

Depending on the situation, it is acceptable to have imports that look like this:

.. code-block:: python

    from twisted.internet.defer import Deferred


or like this:

.. code-block:: python

    from twisted.internet import defer


That is, modules should import *modules* or *classes and functions*, but not *packages*.

Wildcard import syntax may not be used by code in Twisted.
These imports lead to code which is difficult to read and maintain by introducing complexity which strains human readers and automated tools alike.
If you find yourself with many imports to make from a single module and wish to save typing, consider importing the module itself, rather than its attributes.

*Relative imports* (or *sibling imports*) may not be used by code in Twisted.
Relative imports allow certain circularities to be introduced which can ultimately lead to unimportable modules or duplicate instances of a single module.
Relative imports also make the task of refactoring more difficult.

In case of local names conflicts due to import, use the ``as`` syntax, for example:

.. code-block:: python

    from twisted.trial import util as trial_util


The encoding must always be ASCII, so no coding cookie is necessary.

Python 3 compatible modules must be listed in the relevant sections of ``twisted.python.dist3``.


Packages
--------

Package names follow the same conventions as module names.
All modules must be encapsulated in some package.
Nested packages may be used to further organize related modules.

``__init__.py`` must never contain anything other than a docstring and (optionally) an ``__all__`` attribute.
Packages are not modules and should be treated differently.
This rule may be broken to preserve backwards compatibility if a module is made into a nested package as part of a refactoring.

If you wish to promote code from a module to a package, for example, to break a large module out into several smaller files, the accepted way to do this is to promote from within the module.
For example,

.. code-block:: python

    # parent/
    # --- __init__.py ---
    import child

    # --- child.py ---
    import parent
    class Foo:
        pass
    parent.Foo = Foo


Packages must not depend circularly upon each other.
To simplify maintaining this state, packages must also not import each other circularly.
While this applies to all packages within Twisted, one ``twisted.python`` deserves particular attention, as it may not depend on any other Twisted package.


Strings
-------

All strings in Twisted which are not interfacing directly with Python (e.g. ``sys.path`` contents, module names, and anything which returns ``str`` on both Python 2 and 3)  should be marked explicitly as "bytestrings" or "text/Unicode strings".
This is done by using the ``b`` (for bytestrings) or ``u`` (for Unicode strings) prefixes when using string literals.
String literals not marked with this are "native/bare strings", and have a different meaning on Python 2 (where a bare string is a bytestring) and Python 3 (where a bare string is a Unicode string).

.. code-block:: python

    u"I am text, also known as a Unicode string!"
    b"I am a bytestring!"
    "I am a native bare string, and therefore may be either!"

Bytestrings and text must not be implicitly concatenated, as this causes an invisible ASCII encode/decode on Python 2, and causes an exception on Python 3.

Use ``+`` to combine bytestrings, not string formatting (either "percent formatting" or ``.format()``).
String formatting is not available on Python 3.3 and 3.4.

.. code-block:: python

    HTTPVersion = b"1.1"
    transport.write(b"HTTP/" + HTTPVersion)


Utilities are available in :api:`twisted.python.compat <twisted.python.compat>` to paper over some use cases where other Python code (especially the standard library) expects a "native string", or provides a native string where a bytestring is actually required (namely :api:`twisted.python.compat <twisted.python.compat.nativeString>` and :api:`twisted.python.compat <twisted.python.compat.networkString>`)


String Formatting Operations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`String formatting operations <https://docs.python.org/2.7/library/stdtypes.html#string-formatting>`_ like ``formatString % values`` should only be used on text strings, not byte strings, as they do not work on Python 3.3 and 3.4.

When using "percent formatting", you should always use a tuple if you're using non-mapping ``values``.
This is to avoid unexpected behavior when you think you're passing in a single value, but the value is unexpectedly a tuple, e.g.:

.. code-block:: python

    def foo(x):
        return "Hi %s\n" % x


The example shows you can pass in ``foo("foo")`` or ``foo(3)`` fine, but if you pass in ``foo((1,2))``, it raises a ``TypeError``.
You should use this instead:

.. code-block:: python

    def foo(x):
        return "Hi %s\n" % (x,)


Docstrings
----------

Docstrings should always be used to describe the purpose of methods, functions, classes, and modules.
Moreover, all methods, functions, classes, and modules must have docstrings.
In addition to documenting the purpose of the object, the docstring must document all of parameters or attributes of the object.

When documenting a class with one or more attributes which are initialized directly from the value of a ``__init__`` argument by
the same name (or differing only in that the attribute is private), it is sufficient to document the ``__init__`` parameter (in the ``__init__`` docstring).
For example:

.. code-block:: python

    class Ninja(object):
        """
        @ivar speed: See L{__init__}
        @ivar _stealth: See C{stealth} parameter of L{__init__}
        """
        def __init__(self, speed, stealth):
            """
            @param speed: The maximum rate at which this ninja can travel (m/s)
            @type speed: L{int} or L{float}

            @param stealth: This ninja's ability to avoid being noticed in its
                activities, as a percentage modifier.
            @type: L{int}
            """
            self.speed = speed
            self._stealth = stealth


It is not necessary to have a second copy of the documentation for the attribute in the class docstring, only a reference to the method (typically ``__init__`` which does document the attribute's meaning).
Of course, if there is any interesting additional behavior about the attribute that does not apply to the ``__init__`` argument, that behavior should be documented in the class docstring.

Docstrings are *never* to be used to provide semantic information about an object; this rule may be violated if the code in question is to be used in a system where this is a requirement (such as Zope).

Docstrings should be indented to the level of the code they are documenting.

Docstrings must be triple-quoted, with opening and the closing of the docstrings being on a line by themselves.
For example:

.. code-block:: python

    class Ninja(object):
        """
        A L{Ninja} is a warrior specializing in various unorthodox arts of war.
        """
        def attack(self, someone):
            """
            Attack C{someone} with this L{Ninja}'s shuriken.
            """


Docstrings are written in epytext format; more documentation is available in the `Epytext Markup Language documentation <http://epydoc.sourceforge.net/manual-epytext.html>`_.
Please note that pydoctor, the software we use to generate the documentation, links to the Python standard library if you use ``L{}`` with standard Python types (e.g. ``L{str}``).

Additionally, to accommodate emacs users, single quotes of the type of the docstring's triple-quote should be escaped.
This will prevent font-lock from accidentally fontifying large portions of the file as a string.

For example,

.. code-block:: python

    def foo2bar(f):
        """
        Convert L{foo}s to L{bar}s.

        A function that should be used when you have a C{foo} but you want a
        C{bar}; note that this is a non-destructive operation.  If this method
        can't convert the C{foo} to a C{bar} it will raise a L{FooException}.

        @param f: C{foo}
        @type f: L{str}

        For example::

            import wombat
            def sample(something):
                f = something.getFoo()
                f.doFooThing()
                b = wombat.foo2bar(f)
                b.doBarThing()
                return b

        """
        # Optionally, actual code can go here.


Comments
--------

Start by reading the `PEP8 Comments section <http://www.python.org/dev/peps/pep-0008/#comments>`_.
Ignore `Documentation Strings` section from PEP8 as Twisted uses a different docstring standard.

`FIXME/TODO` comments must have an associated ticket and contain a reference to it in the form of a full URL to the ticket.
A brief amount of text should provide info about why the FIXME was added.
It does not have to be the full ticket description, just enough to help readers decide if their next step should be reading the ticket or continue reading the code.

.. code-block:: python

    # FIXME: https://twistedmatrix.com/trac/ticket/1235
    # Threads that have died before calling stop() are not joined.
    for thread in threads:
        thread.join()


Versioning
----------

The API documentation should be marked up with version information.
When a new API is added the class should be marked with the epytext ``@since:`` field including the version number when the change was introduced.
This version number should be in the form ``x.y`` (for example, ``@since: 15.1``).


Scripts
-------

For each "script" , that is, a program you expect a Twisted user to run from the command-line, the following things must be done:

#. Write a module in :api:`twisted.scripts <twisted.scripts>` which contains a callable global named ``run``.
   This will be called by the command line part with no arguments (it will usually read ``sys.argv`` ).
   Feel free to write more functions or classes in this module, if you feel they are useful to others.
#. Create a file which contains a shebang line for Python.
   This file should be placed in the ``bin/`` directory; for example, ``bin/twistd``.

   .. code-block:: python

       #!/usr/bin/env python


To make sure that the script is portable across different UNIX like operating systems we use the ``/usr/bin/env`` command.
The env command allows you to run a program in a modified environment.
That way you don't have to search for a program via the ``PATH`` environment variable.
This makes the script more portable but note that it is not a foolproof method.
Always make sure that ``/usr/bin/env`` exists or use a softlink/symbolic link to point it to the correct path.
Python's distutils will rewrite the shebang line upon installation so this policy only covers the source files in version control.

#. For core scripts, add this Twisted running-from-SVN header:

   .. code-block:: python

       import sys
       try:
           import _preamble
       except ImportError:
           sys.clear_exc()


   Or for sub-project scripts, add a modified version which also adjusts ``sys.path``:

   .. code-block:: python

       import sys, os
       extra = os.path.dirname(os.path.dirname(sys.argv[0]))
       sys.path.insert(0, extra)
       try:
           import _preamble
       except ImportError:
           sys.clear_exc()
       sys.path.remove(extra)


#. And end with:

   .. code-block:: python

       from twisted.scripts.yourmodule import run
       run()


#. Write a manpage and add it to the ``man`` folder of a subproject's ``doc`` folder.
   On Debian systems you can find a skeleton example of a manpage in ``/usr/share/doc/man-db/examples/manpage.example``.

This will ensure your program will work correctly for users of SVN, Windows releases and Debian packages.


Examples
--------

For example scripts you expect a Twisted user to run from the command-line, add this Python shebang line at the top of the file:

.. code-block:: python

    #!/usr/bin/env python


Standard Library Extension Modules
----------------------------------

When using the extension version of a module for which there is also a Python version, place the import statement inside a try/except block, and import the Python version if the import fails.
This allows code to work on platforms where the extension version is not available.
For example:

.. code-block:: python

    try:
        import cPickle as pickle
    except ImportError:
        import pickle


Use the "as" syntax of the import statement as well, to set the name of the extension module to the name of the Python module.

Some modules don't exist across all supported Python versions.
For example, Python 2.3's ``sets`` module was deprecated in Python 2.6 in favor of the ``set`` and ``frozenset`` builtins.
:api:`twisted.python.compat <twisted.python.compat>` would be the place to add ``set`` and ``frozenset`` implementations that work across Python versions.


Classes
-------

Classes are to be named in mixed case, with the first letter capitalized; each word separated by having its first letter capitalized.
Acronyms should be capitalized in their entirety.
Class names should not be prefixed with the name of the module they are in.
Examples of classes meeting this criteria:

- ``twisted.spread.pb.ViewPoint``
- ``twisted.parser.patterns.Pattern``

Examples of classes **not** meeting this criteria:

- ``event.EventHandler``
- ``main.MainGadget``

An effort should be made to prevent class names from clashing with each other between modules, to reduce the need for qualification when importing.
For example, a Service subclass for Forums might be named ``twisted.forum.service.ForumService``, and a Service subclass for Words might be ``twisted.words.service.WordsService``.
Since neither of these modules are volatile *(see above)* the classes may be imported directly into the user's namespace and not cause confusion.


New-style Classes
~~~~~~~~~~~~~~~~~

Classes and instances in Python come in two flavors: old-style or classic, and new-style.
Up to Python 2.1, old-style classes were the only flavour available to the user, new-style classes were introduced in Python 2.2 to unify classes and types.
All classes added to Twisted must be written as new-style classes.
If ``x`` is an instance of a new-style class, then ``type(x)`` is the same as ``x.__class__``.


Methods
-------

Methods should be in mixed case, with the first letter lower case, each word separated by having its first letter capitalized.
For example, ``someMethodName``, ``method``.

Sometimes, a class will dispatch to a specialized sort of method using its name; for example, ``twisted.reflect.Accessor``.
In those cases, the type of method should be a prefix in all lower-case with a trailing underscore, so method names will have an underscore in them.
For example, ``get_someAttribute``.
Underscores in method names in twisted code are therefore expected to have some semantic associated with them.

Some methods, in particular ``addCallback`` and its cousins return self to allow for chaining calls.
In this case, wrap the chain in parenthesis, and start each chained call on a separate line, for example:

.. code-block:: python

    return (foo()
            .addCallback(bar)
            .addCallback(thud)
            .addCallback(wozers))


Using the Global Reactor
------------------------

Even though it may be convenient, module-level imports of the global Twisted reactor (``from twisted.internet import reactor``) should be avoided.
Importing the reactor at the module level means that reactor selection occurs on initial import, and not at the request of the code that originally imported the module.
Applications may wish to import their own reactor, or otherwise use a reactor different than Twisted's default (for example, using the experimental cfreactor on OS X); importing at the module level means they would have to monkeypatch in the different reactor, or use similar hacks.
This is especially apparent in Twisted's own test suite; many tests wish to provide their own reactor which controls the passage of time and simulates timeouts.

Below is an example of the pattern for accepting the user's choice of reactor -- importing the global one if none is specified -- taken (and trimmed for brevity) from existing Twisted source code.

.. code-block:: python

    class Session(object):
        """
        A user's session with a system.

        @ivar _reactor: An object providing L{IReactorTime} to use for scheduling
            expiration.
        """
        def __init__(self, site, uid, reactor=None):
            """
            Initialize a session with a unique ID for that session.
            """
            if reactor is None:
                from twisted.internet import reactor
            self._reactor = reactor

            # ... other code ...


The reactor attribute should be private by default, but if it is useful to the users of the code, there is no reason why it can not be public.


Callback Arguments
------------------

There are several methods whose purpose is to help the user set up callback functions, for example :api:`twisted.internet.defer.Deferred.addCallback <Deferred.addCallback>` or the reactor's :api:`twisted.internet.base.ReactorBase.callLater <callLater>` method.
To make access to the callback as transparent as possible, most of these methods use ``**kwargs`` to capture arbitrary arguments that are destined for the user's callback.
This allows the call to the setup function to look very much like the eventual call to the target callback function.

In these methods, take care to not have other argument names that will "steal" the user's callback's arguments.
When sensible, prefix these "internal" argument names with an underscore.
For example, :api:`twisted.spread.pb.RemoteReference.callRemote <RemoteReference.callRemote>` is meant to be called like this:

.. code-block:: python

    myref.callRemote("addUser", "bob", "555-1212")

    # on the remote end, the following method is invoked:
    def addUser(name, phone):
        ...


where "addUser" is the remote method name.
The user might also choose to call it with named parameters like this:

.. code-block:: python

    myref.callRemote("addUser", name="bob", phone="555-1212")


In this case, ``callRemote`` (and any code that uses the ``**kwargs`` syntax) must be careful to not use "name", "phone", or any other name that might overlap with a user-provided named parameter.
Therefore, ``callRemote`` is implemented with the following signature:

.. code-block:: python

    class SomeClass(object):
        def callRemote(self, _name, *args, **kw):
            ...


Do whatever you can to reduce user confusion.
It may also be appropriate to ``assert`` that the kwargs dictionary does not contain parameters with names that will eventually cause problems.


Special Methods
---------------

The augmented assignment protocol, defined by ``__iadd__`` and other similarly named methods, can be used to allow objects to be modified in place or to rebind names if an object is immutable -- both through use of the same operator.
This can lead to confusing code, which in turn leads to buggy code.
For this reason, methods of the augmented assignment protocol should not be used in Twisted.


Functions
---------

Functions should be named similarly to methods.

Functions or methods which are responding to events to complete a callback or errback should be named ``_cbMethodName`` or ``_ebMethodName``, in order to distinguish them from normal methods.


Attributes
----------

Attributes should be named similarly to functions and methods.
Attributes should be named descriptively; attribute names like ``mode``, ``type``, and ``buf`` are generally discouraged.
Instead, use ``displayMode``, ``playerType``, or ``inputBuffer``.

Do not use Python's "private" attribute syntax; prefix non-public attributes with a single leading underscore.
Since several classes have the same name in Twisted, and they are distinguished by which package they come from, Python's double-underscore name mangling will not work reliably in some cases.
Also, name-mangled private variables are more difficult to address when unit testing or persisting a class.

An attribute (or function, method or class) should be considered private when one or more of the following conditions are true:

- The attribute represents intermediate state which is not always kept up-to-date.
- Referring to the contents of the attribute or otherwise maintaining a reference to it may cause resources to leak.
- Assigning to the attribute will break internal assumptions.
- The attribute is part of a known-to-be-sub-optimal interface and will certainly be removed in a future release.


Python 3
--------

Twisted is being ported to Python 3, targeting Python 3.3+.
Please see :doc:`Porting to Python 3 </core/howto/python3>` for details.


Database
--------

Database tables will be named with plural nouns.

Database columns will be named with underscores between words, all lower case, since most databases do not distinguish between case.

Any attribute, method argument, or method name that corresponds *directly* to a column in the database will be named exactly the same as that column, regardless of other coding conventions surrounding that circumstance.

All SQL keywords should be in upper case.


C Code
------

C code must be optional, and work across multiple platforms (MSVC++9/10/14 for Pythons 2.7, 3.3/3.4, and 3.5 on Windows, as well as recent GCCs and Clangs for Linux, OS X, and FreeBSD).

C code should be kept in external bindings packages which Twisted depends on.
If creating new C extension modules, using `cffi <https://cffi.readthedocs.org/en/latest/>`_ is highly encouraged, as it will perform well on PyPy and CPython, and be easier to use on Python 2 and 3.
Consider optimizing for `PyPy <http://pypy.org/performance.html>`_ instead of creating bespoke C code.


Commit Messages
---------------

The commit messages are being distributed in a myriad of ways.
Because of that, you need to observe a few simple rules when writing a commit message.

The first line of the message is being used as both the subject of the commit email and the announcement on #twisted.
Therefore, it should be short (aim for < 80 characters) and descriptive -- and must be able to stand alone (it is best if it is a complete sentence).
The rest of the e-mail should be separated with *hard line breaks* into short lines (< 70 characters).
This is free-format, so you can do whatever you like here.

Commit messages should be about *what*, not *how*: we can get how from SVN diff.
Explain reasons for commits, and what they affect.

Each commit should be a single logical change, which is internally consistent.
If you can't summarize your changes in one short line, this is probably a sign that they should be broken into multiple checkins.


Source Control
--------------

Twisted currently uses Subversion for source control.
All development must occur using branches; when a task is considered complete another Twisted developer may review it and if no problems are found, it may be merged into trunk.
The Twisted wiki has `a start <http://twistedmatrix.com/trac/wiki/TwistedDevelopment>`_.
Branches can be managed using `Combinator <http://divmod.org/trac/wiki/DivmodCombinator>`_ for interfacing with the SVN repo, or using `twisted-dev-tools <https://github.com/twisted/twisted-dev-tools>`_ if interacting with the Git mirror.

Certain features of Subversion should be avoided.

- Do not set the ``svn:ignore`` property on any file or directory.
  What you wish to ignore, others may wish to examine.
  What others may wish you ignore, *you* may wish you examine.
  ``svn:ignore`` will affect everyone who uses the repository, and so it is not the right mechanism to express personal preferences.

  If you wish to ignore certain files use the ``global-ignores`` feature of ``~/.subversion/config``, for example:

  .. code-block:: console

      [miscellany]
      global-ignores = dropin.cache *.pyc *.pyo *.o *.lo *.la #*# .*.rej *.rej .*~


Fallback
--------

In case of conventions not enforced in this document, the reference documents to use in fallback is `PEP 8 <http://www.python.org/dev/peps/pep-0008/>`_ for Python code and `PEP 7 <http://www.python.org/dev/peps/pep-0007/>`_ for C code.
For example, the paragraph **Whitespace in Expressions and Statements** in PEP 8 describes what should be done in Twisted code.


Recommendations
---------------

These things aren't necessarily standardizeable (in that code can't be easily checked for compliance) but are a good idea to keep in mind while working on Twisted.

If you're going to work on a fragment of the Twisted codebase, please consider finding a way that you would *use* such a fragment in daily life.
Using a Twisted Web server on your website encourages you to actively maintain and improve your code, as the little everyday issues with using it become apparent.
Twisted is a **big** codebase!
If you're refactoring something, please make sure to recursively grep for the names of functions you're changing.
You may be surprised to learn where something is called.
Especially if you are moving or renaming a function, class, method, or module, make sure that it won't instantly break other code.
