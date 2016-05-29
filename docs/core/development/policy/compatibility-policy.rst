Twisted Compatibility Policy
============================

Motivation
----------

The Twisted project has a small development team, and we cannot afford to provide anything but critical bug-fix support for multiple version branches of Twisted.
However, we all want Twisted to provide a positive experience during development, deployment, and usage.
Therefore we need to provide the most trouble-free upgrade process possible, so that Twisted application developers will not shy away from upgrades that include necessary bugfixes and feature enhancements.

Twisted is used by a wide variety of applications, many of which are proprietary or otherwise inaccessible to the Twisted development team.
Each of these applications is developed against a particular version of Twisted.
The most important compatibility to preserve is at the Python API level.
Python does not provide us with a strict way to partition **public** and **private** objects (methods, classes, modules), so it is unfortunately quite likely that many of those applications are using arbitrary parts of Twisted.
Our compatibility strategy needs to take this into account, and be comprehensive across our entire codebase.

Exceptions can be made for modules aggressively marked **unstable** or **experimental**, but even experimental modules will start being used in production code if they have been around for long enough.

The purpose of this document is to to lay out rules for Twisted application developers who wish to weather the changes when Twisted upgrades, and procedures for Twisted engine developers - both contributors and core team members - to follow when who want to make changes which may be incompatible to Twisted itself.


Defining Compatibility
----------------------

The word "compatibility" is itself difficult to define.
While comprehensive compatibility is good, total compatibility is neither feasible nor desirable.
Total compatibility requires that nothing ever change, since any change to Python code is detectable by a sufficiently determined program.
There is some folk knowledge around which kind of changes **obviously** won't break other programs, but this knowledge is spotty and inconsistent.
Rather than attempt to disallow specific kinds of changes, here we will lay out a list of changes which are considered compatible.

Throughout this document, **compatible** changes are those which meet these specific criteria.
Although a change may be broadly considered backward compatible, as long as it does not meet this official standard, it will be officially deemed **incompatible** and put through the process for incompatible changes.

The compatibility policy described here is 99% about changes to **interface**,
not changes to functionality.

..  note::
    Ultimately we want to make the user happy but we cannot put every possible thing that will make every possible user happy into this policy.


Brief notes for developers
--------------------------

Here is a summary of the things that need to be done for deprecating code.
This is not an exhaustive read and beside this list you should continue reading the rest of this document:

* Do not change the function's behavior as part of the deprecation process.

* Cause imports or usage of the class/function/method to emit a DeprecationWarning either call warnings.warn or use one of the helper APIs

* The warning text must include the version of Twisted in which the function is first deprecated (which will always be a version in the future)

* The warning text should recommend a replacement, if one exists.

* The warning must "point to" the code which called the function. For example, in the normal case, this means stacklevel=2 passed to warnings.warn.

* There must be a unit test which verifies the deprecation warning.

* A .removal news fragment must be added to announce the deprecation.


Procedure for Incompatible Changes
----------------------------------

Any change specifically described in the next section as **compatible** may be made at any time, in any release.


The First One's Always Free
^^^^^^^^^^^^^^^^^^^^^^^^^^^

The general purpose of this document is to provide a pleasant upgrade experience for Twisted application developers and users.

The specific purpose of this procedure is to achieve that experience by making sure that any application which runs without warnings may be upgraded one minor version of twisted (y to y+1 in x.y.z) or from the last minor revision of a major release to the first minor revision of the next major release (x to x + 1 in x.y.z to x.0.z, when there will be no x.y+1.z).

In other words, any application which runs its tests without triggering any warnings from Twisted should be able to have its Twisted version upgraded at least once with no ill effects except the possible production of new warnings.


Incompatible Changes
^^^^^^^^^^^^^^^^^^^^

Any change which is not specifically described as **compatible** must be made in 2 phases.
If a change is made in release R, the timeline is:

1. Release R: New functionality is added and old functionality is deprecated with a DeprecationWarning.

2. At the earliest, release R+2 and one year after release R, but often much later: Old functionality is completely removed.

Removal should happen once the deprecated API becomes an additional maintenance burden.

For example, if it makes implementation of a new feature more difficult, if it makes documentation of non-deprecated APIs more confusing, or if its unit tests become an undue burden on the continuous integration system.

Removal should not be undertaken just to follow a timeline. Twisted should strive, as much as practical, not to break applications relying on it.


Procedure for Exceptions to this Policy
---------------------------------------

**Every change is unique.**

Sometimes, we'll want to make a change that fits with this spirit of this document (keeping Twisted working for applications which rely upon it) but may not fit with the letter of the procedure described above (the change modifies behavior of an existing API sufficiently that something might break).
Generally, the reason that one would want to do this is to give applications a performance enhancement or bug fix that could break behavior that unanticipated, hypothetical uses of an existing API, but we don't want well-behaved applications to pay the penalty of a deprecation/adopt-a-new-API/removal cycle in order to get the benefits of the improvement if they don't need to.

If this is the case for your change, it's possible to make such a modification without a deprecation/removal cycle.
However, we must give users an opportunity to discover whether a particular incompatible change affects them: we should not trust our own assessments of how code uses the API.
In order to propose an incompatible change, start a discussion on the mailing list.
Make sure that it is eye-catching so those who don't read all list messages in depth will notice it, by prefixing the subject with **INCOMPATIBLE CHANGE:** (capitalized like so).
Always include a link to the ticket, and branch (if relevant).

In order to **conclude** such a discussion, there must be a branch available so that developers can run their unit tests against it to mechanically verify that their understanding of their own code is correct.
If nobody can produce a failing test or broken application within **a week's time** from such a branch being both 1. available and 2. announced, and at least **three committers** agree that the change is worthwhile, then the branch can be considered approved for the incompatible change in question.

Since some codebases that use Twisted are presumably proprietary and confidential, there should be a good-faith presumption if someone says they have broken tests but cannot immediately produce code to share.

The branch must be available for one week's time.

..  note::
    The announcement forum for incompatible changes and the waiting period required are subject to change as we discover how effective this method is; the important aspect of this policy is that users have some way of finding out in advance about changes which might affect them.


Compatible Changes. Changed not Covered by the Compatibility Policy
-------------------------------------------------------------------

Here is a non-exhaustive list of changes which are not covered by the compatibility policy.
These changes can be made without having to worry about the compatibility policy.


Test Changes
^^^^^^^^^^^^

No code or data in a test package should be imported or used by a non-test package within Twisted.
By doing so, there's no chance anything could access these objects by going through the public API.

Test code and test helpers are considered private API and it should be imported outside
of the Twisted testing infrastructure.


Private Changes
^^^^^^^^^^^^^^^

Code is considered *private* if the user would have to type a leading underscore to access it.
In other words, a function, module, method, attribute or class whose name begins with an underscore may be arbitrarily changed.


Bug Fixes and Gross Violation of Specifications
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If Twisted documents an object as complying with a published specification, and there are inputs which can cause Twisted to behave in obvious violation of that specification, then changes may be made to correct the behavior in the face of those inputs.

If application code must support multiple versions of Twisted, and work around violations of such specifications, then it must test for the presence of such a bug before compensating for it.

For example, Twisted supplies a DOM implementation in twisted.web.microdom.
If an issue were discovered where parsing the string `<xml>Hello</xml>` and then serializing it again resulted in `>xml<Hello>/xml<`, that would grossly violate the XML specification for well-formedness.
Such code could be fixed with no warning other than release notes detailing that this error is now fixed.


Raw Source Code
^^^^^^^^^^^^^^^

The most basic thing that can happen between Twisted versions, of course, is that the code may change.
That means that no application may ever rely on, for example, the value of any **func_code** object's **co_code** attribute remaining stable, or the **checksum** of a .py file remaining stable.

**Docstrings** may also change at any time.
No application code may expect any Twisted class, module, or method's __doc__ attribute to remain the same.


New Attributes
^^^^^^^^^^^^^^

New code may also be added.
No application may ever rely on the output of the ``dir()`` function on any object remaining stable, nor on any object's ``__all__`` attribute, nor on any object's ``__dict__`` not having new keys added to it.
These may happen in any maintenance or bugfix release, no matter how minor.


Pickling
^^^^^^^^

Even though Python objects can be pickled and unpickled without explicit support for this, whether a particular pickled object can be unpickled after any particular change to the implementation of that object is less certain.
Because of this, no application may depend on any object defined by Twisted to provide pickle compatibility between any release unless the object explicitly documents this as a feature it has.


Changes Covered by the Compatibility Policy
-------------------------------------------

Here is a non-exhaustive list of changes which are not covered by the compatibility policy.

Some changes appear to be in keeping with the above rules describing what is compatible, but are in fact not.


Interface Changes
^^^^^^^^^^^^^^^^^

Although methods may be added to implementations, adding those methods to interfaces may introduce an unexpected requirement in user code.

..  note::
    There is currently no way to express, in zope.interface, that an interface may optionally provide certain features which need to be tested for. Although we can add new code, we can't add new requirements on user code to implement new methods.

    This is easier to deal with in a system which uses abstract base classes because new requirements can provide default implementations which provide warnings.
    Something could also be put in place to do the same with interfaces, since they already install a metaclass, but this is tricky territory. The only example I'm aware of here is the Microsoft tradition of ISomeInterfaceN where N is a monotonically ascending number for each release.


Private Objects Available via Public Entry Points
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If a **public** entry point returns a **private** object, that **private** object must preserve its **public** attributes.

In the following example, ``_ProtectedClass`` can no longer be arbitrarily changed.
Specifically, ``getUsers()`` is now a public method, thanks to ``get_users_database()`` exposing it.
However, ``_checkPassword()`` can still be arbitrarily changed or removed.

For example:

.. code-block:: python

    class _ProtectedClass:
        """
        A private class which is initialized only by an entry point.
        """
        def getUsers(self):
            """
            A public method covered by the compatibility policy.
            """
            return []

        def _checkPassword(self):
            """
            A private method not covered by the compatibility policy.
            """
            return False



    def get_users_database():
        """
        A method guarding the initialization of the private class.

        Since the method is public and it returns an instance of the
        C{_ProtectedClass}, this makes the _ProtectedClass a public class.
        """
        return _ProtectedClass()


Private Class Inherited by Public Subclass
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

A **private** class which is inherited or exposed in any way by **public** subclass will make
the inherited class **public**.

The **private**  is still protected against direct instantiation.

.. code-block:: python

    class _Base(object):
        """
        A class which should not be directly instantiated.
        """
        def getActiveUsers(self):
            return []

        def getExpiredusers(self):
            return []

    class Users(_Base):
        """
        Public class inheriting from a private class.
        """
        pass


In the following example ``_Base`` is effectively **public**, since ``getActiveUsers()`` and ``getExpiredusers()`` are both exposed via the **public** ``Users`` class.


Documented and Tested Gross Violation of Specifications
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If the behaviour of a what was later found as a bug was documented, or fixing it caused existing tests to break, then the change should be considered incompatible, regardless of how gross its violation.
It may be that such violations are introduced specifically to deal with other grossly non-compliant implementations of said specification.
If it is determined that those reasons are invalid or ought to be exposed through a different API, the change is compatible.


Application Developer Upgrade Procedure
---------------------------------------

When an application wants to be upgraded to a new version of Twisted, it can do so immediately.

However, if the application wants to get the same **for free** behavior for the next upgrade, the application's tests should be run treating warnings as errors, and fixed.


Supporting and de-supporting Python versions
--------------------------------------------

Twisted does not have a formal policy around supporting new versions of Python or de-supporting old versions of Python.
We strive to support Twisted on any version of Python that is the default Python for a vendor-supported release from a major platform, namely Debian, Ubuntu, the latest release of Windows, or the latest release of OS X.
The versions of Python currently supported are listed in the ​INSTALL file for each release.

A distribution release + Python version is only considered supported when a `buidlbot builder <http://buildbot.twistedmatrix.com>`_ exists for it.

Removing support for a Python version will be announced at least 1 release prior to the removal.


How to deprecate APIs
---------------------


Classes
^^^^^^^

Classes are deprecated by raising an warning when they are access from withing their module, using the :api:`twisted.python.deprecate.deprecatedModuleAttribute <deprecatedModuleAttribute>` helper.

.. code-block:: python

    class SSLContextFactory:
        """
        An SSL context factory.
        """
        deprecatedModuleAttribute(
            Version("Twisted", 12, 2, 0),
            "Use twisted.internet.ssl.DefaultOpenSSLContextFactory instead.",
            "twisted.mail.protocols", "SSLContextFactory")


Functions and methods
^^^^^^^^^^^^^^^^^^^^^

To deprecate a function or a method, add a call to warnings.warn to the beginning of the implementation of that method.
The warning should be of type ``DeprecationWarning`` and the stack level should be set so that the warning refers to the code which is invoking the deprecated function or method.
The deprecation message must include the name of the function which is deprecated, the version of Twisted in which it was first deprecated, and a suggestion for a replacement.
If the API provides functionality which it is determined is beyond the scope of Twisted or it has no replacement, then it may be deprecated without a replacement.

There is also a :api:`twisted.python.deprecate.deprecated <deprecated>` decorator which works for new-style classes.

For example:

.. code-block:: python

    import warnings

    from twisted.python.deprecate import deprecated
    from twisted.python.versions import Version


    @deprecated(Version("Twisted", 1, 2, 0), "twisted.baz")
    def some_function(bar):
        """
        Function deprecated using a decorator.
        """
        return bar * 3



    @deprecated(Version("Twisted", 1, 2, 0))
    def some_function(bar):
        """
        Function deprecated using a decorator and which has no replacement.
        """
        return bar * 3



    def some_function(bar):
        """
        Function with a direct call to warnings.
        """
        warnings.warn(
            'some_function is deprecated since Twisted 1.2.0. '
            'Use twisted.baz instead.',
            category=DeprecationWarning,
            stacklevel=2)
        return bar * 3


Instance attributes
^^^^^^^^^^^^^^^^^^^

To deprecate an attribute on instances of a new-type class, make the attribute into a property and call ``warnings.warn`` from the getter and/or setter function for that property.
You can also use the :api:`twisted.python.deprecate.deprecatedProperty <deprecatedProperty>` decorator which works for new-style classes.

.. code-block:: python

    from twisted.python.deprecate import deprecated
    from twisted.python.versions import Version


    class SomeThing(object):
        """
        A class for which the C{user} ivar is not yet deprecated.
        """

        def __init__(self, user):
            self.user = user



    class SomeThingWithDeprecation(object):
        """
        A class for which the C{user} ivar is now deprecated.
        """

        def __init__(self, user=None):
            self._user = user


        @deprecatedProperty(Version("Twisted", 1, 2, 0))
        def user(self):
            return self._user


        @user.setter
        def user(self, value):
            self._user = value


Module attributes
^^^^^^^^^^^^^^^^^

Modules cannot have properties, so module attributes should be deprecated using the :api:`twisted.python.deprecate.deprecatedModuleAttribute <deprecatedModuleAttribute>` helper.

.. code-block:: python

    from twisted.python import _textattributes
    from twisted.python.deprecate import deprecatedModuleAttribute
    from twisted.python.versions import Version

    flatten = _textattributes.flatten

    deprecatedModuleAttribute(
        Version('Twisted', 13, 1, 0),
        'Use twisted.conch.insults.text.assembleFormattedText instead.',
        'twisted.conch.insults.text',
        'flatten')


Modules
^^^^^^^

To deprecate an entire module, :api:`twisted.python.deprecate.deprecatedModuleAttribute <deprecatedModuleAttribute>` can be used on the parent package's ``__init__.py``.

There are two other options:

* Put a warnings.warn() call into the top-level code of the module.
* Deprecate all of the attributes of the module.


Testing Deprecation Code
------------------------

Like all changes in Twisted, deprecations must come with associated automated tested.
There are several options for checking that a code is deprecated and that using it raises a ``DeprecationWarning``.

In order of decreasing preference:

* :api:`twisted.trial.unittest.SynchronousTestCase.flushWarnings <flushWarnings>`
* :api:`twisted.trial.unittest.SynchronousTestCase.assertWarns <assertWarns>`
* :api:`twisted.trial.unittest.SynchronousTestCase.callDeprecated <callDeprecated>`


.. code-block:: python

    from twisted.trial import unittest


    class DeprecationTests(unittest.TestCase):
        """
        Tests for deprecated code.
        """


        def test_deprecationUsingFlushWarnings(self):
            """
            flushWarnings() is the recommended way of checking for deprecations.
            Make sure you only flushWarning from the targeted code, and not all
            warnings.
            """
            db.getUser('some-user')

            message = (
                'twisted.Identity.getUser was deprecated in Twisted 15.0.0: '
                'Use twisted.get_user instead.'
                )
            warnings = self.flushWarnings(
                [self.test_deprecationUsingFlushWarnings])
            self.assertEqual(1, len(warnings))
            self.assertEqual(DeprecationWarning, warnings[0]['category'])
            self.assertEqual(message, warnings[0]['message'])


        def test_deprecationUsingAssertWarns(self):
            """
            assertWarns() is designed as a general helper to check any
            type of warnings and can be used for DeprecationsWarnings.
            """
            self.assertWarns(
                DeprecationWarning,
                'twisted.Identity.getUser was deprecated in Twisted 15.0.0 '
                'Use twisted.get_user instead.',
                __file__,
                db.getUser, 'some-user')


        def test_deprecationUsingCallDeprecated(self):
            """
            Avoid using self.callDeprecated() just to check the deprecation
            call.
            """
            self.callDeprecated(
                Version("Twisted", 1, 2, 0), db.getUser, 'some-user')


When code is deprecated, all previous tests in which the code is called and tested will now raise ``DeprecationWarning``\ s.
Making calls to the deprecated code without raising these warnings can be done using the :api:`twisted.trial.unittest.TestCase.callDeprecated <callDeprecated>` helper.

.. code-block:: python

    from twisted.trial import unittest


    class IdentityTests(unittest.TestCase):
        """
        Tests for our Identity behavior.
        """

        def test_getUserHomePath(self):
            """
            This is a test in which we check the returned value of C{getUser}
            but we also explicitly handle the deprecations warnings emitted
            during its execution.
            """
            user = self.callDeprecated(
                Version("Twisted", 1, 2, 0), db.getUser, 'some-user')

            self.assertEqual('some-value', user.homePath)


Due to a bug in Trial (`#6348 <https://twistedmatrix.com/trac/ticket/6348>`_), unhandled deprecation warnings will not cause test failures or show in test results.

While the Trial bug is not fixed, to trigger test failures on unhandled deprecation warnings use:

.. code-block:: console

    python -Werror::DeprecationWarning ./bin/trial twisted.conch
