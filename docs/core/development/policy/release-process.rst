Twisted Release Process
=======================

This document describes the Twisted release process.
Although it is still incomplete, every effort has been made to ensure that it is accurate and up-to-date.

If you want to make changes to the release process, follow the normal Twisted development process (contribute release automation software that has documentation and unit tests demonstrating that it works).


Outcomes
--------

By the end of a Twisted release we'll have:

- Wheel and sdist package published on `PyPI Twisted project <https://pypi.org/project/Twisted/>`_.
- Updated documentation (API & howtos) on `Twisted Read The Docs <https://twisted.readthedocs.io/en/latest/>`_
- Announcement email sent to Twisted main list
- A `GitHub Release <https://github.com/twisted/twisted/releases>`_ with the associated tag in our Git repository


Prerequisites
-------------

To release Twisted, you will need:

- Commit privileges to Twisted GitHub repository.


Version numbers
---------------

Twisted releases use a time-based numbering scheme following PEP440 convention.
Releases versions like YY.MM.mm, where YY is the last two digits of the year of the release, MM is the month of release, and mm is the number of the bugfix release.

There are 3 release types:

- Major release when YY.MM is updated.
- Bugfix / patch / point release when the mm number is updated
- Release candidates which are pre-releases as YY.MM.mmrc1

For example:

- A release in Jan 2017 is 17.1.0
- A release in Nov 2017 is 17.11.0
- If 17.11.0 has some critical defects, then a bugfix 17.11.1
- The first release candidate of 17.1.0 is 17.1.0rc1, the second is 17.1.0rc2

Every release of Twisted includes the whole project.

Throughout this document, we'll refer to the version number of the release as $RELEASE. Examples of $RELEASE include 10.0.0, 10.1.0, 10.1.1 etc.

We'll refer to the first two components of the release as $API, since all releases that share those numbers are mutually API compatible.
e.g. for 10.0.0, $API is 10.0; for 10.1.0 and 10.1.1, $API is 10.1.

Incremental automatically picks the correct version number for you.
Please retrieve it after you run it.


Overview
--------

To release Twisted, we

1. Prepare for a release
2. Release one or more release candidates
3. Release the final release


Prepare for a release
---------------------

#. Check for any ​regressions using `Trac regression report <https://twistedmatrix.com/trac/report/26>`_

#. Any regression should be fixed and merged trunk before making the release branch

#. Choose a version number.

#. File a ticket in Trac called "Release $RELEASE" and assign it to yourself.

#. Make a branch for the release and include the ticket number in the name (4290 is Trac ticket ID):

   - ``git fetch origin``
   - ``git checkout origin/trunk``
   - ``git checkout -b release-$RELEASE-4290``


How to do a release candidate
-----------------------------


Prepare the branch
~~~~~~~~~~~~~~~~~~

#. In your Git repo, fetch and check out the new release branch.
#. Run ``python -m incremental.update Twisted --rc``
#. Commit the changes made by Incremental.
#. Run ``tox -e towncrier``.
#. Commit the changes made by towncrier - this automatically removes the newsfragment files.
#. Bump copyright dates in ``LICENSE``, ``twisted/copyright.py``, and ``README.rst`` if required
#. Push the changes up to GitHub and create a new release PR.
#. The GitHub PR is dedicated to the final release and the same PR is used to release the candidate and final version.
#. Use the `GitHub Create Release UI <https://github.com/twisted/twisted/releases/new>`_ the make a new release.
#. Create a tag using the format `twisted-VERSION` based on the latest commit on the release branch that was approved after the review.
#. Use `Twisted VERSION` as the name of the release.
#. Add the release NEWS to GitHub Release page.
#. Make sure 'This is a pre-release` is checked.
#. Github Actions will upload the dist to PyPI when a new tag is pushed to the repo.
#. Read the Docs hooks will publish a new version of the docs.

Announce
~~~~~~~~

#. Write the release announcement

#. Announce the release candidate on

   - the twisted-python mailing list by sending the content of latest release NEWS
   - on IRC in the ``#twisted-dev`` topic by sending the version number

The release candidate announcement might mention the important changes since the last release, and ask readers to test this release candidate.

Here's what the $RELEASErc1 release announcement might look like::

    Live from PyCon Atlanta, I'm pleased to herald the approaching
    footsteps of the $API release.

    Wheels for Twisted $RELEASE release candidate are now available on PyPI.

    Highlights include:

     * Improved documentation, including "Twisted Web in 60 seconds"

     * Faster Perspective Broker applications

     * A new Windows installer that ships without zope.interface

     * Twisted no longer supports Python 2.3

     * Over one hundred closed tickets

    For more information, see the NEWS file.

    Please download the tarballs and test them as much as possible.

    Thanks,
    jml

A week is a generally good length of time to wait before doing the final release.


How to do a final release
-------------------------


Prepare the branch
~~~~~~~~~~~~~~~~~~

#. Have the release branch, previously used to generate a release candidate, checked out
#. Manually update the version and realease date. Commit and push.
#. Submit the ticket for review
#. Pause until the ticket is reviewed and accepted.
#. Use the `GitHub Create Release UI <https://github.com/twisted/twisted/releases/new>`_ the make a new release.
#. Create a tag using the format `twisted-VERSION` based on the latest commit on the release branch that was approved after the review.
#. Use `Twisted VERSION` as the name of the release.
#. Add the release NEWS to GitHub Release page.
#. Make sure 'This is a pre-release` is not checked.
#. Github Actions will upload the dist to PyPI when a new tag is pushed to the repo. PyPI is the only canonical source for Twisted packages.
#. Read the Docs hooks will publish a new version of the docs.


Announce
~~~~~~~~

#. Write the release announcement that should be similar to the release candidate, with the updated version and release date.

#. Announce the release

   - Send a text version of the announcement to: twisted-python@twistedmatrix.com, python-announce-list@python.org, python-list@python.org, twisted-web@twistedmatrix.com
   - ​http://labs.twistedmatrix.com (Post a web version of the announcements, with links instead of literal URLs)
   - Twitter, if you feel like it
   - ``#twisted`` topic on IRC (you'll need ops)


Post release
~~~~~~~~~~~~

#. Run ``python -m incremental Twisted --dev`` to add a `dev0` postfix.

#. Commit the dev0 update change.

#. Merge the release branch into trunk, closing the release ticket at the same time.


When things go wrong
--------------------

If you discover a showstopper bug during the release process, you have three options.

1. Abort the release, make a new point release (e.g. abort 10.0.0, make 10.0.1 after the bug is fixed)
2. Abort the release, make a new release candidate (e.g. abort 10.0.0, make 10.0.0pre3 after the bug is fixed)

Don't delete a tag that was already pushed for a release.
Create a new tag with incremented version.


Bug fix releases
----------------

Sometimes, bugs happen, and sometimes these are regressions in the current released version.
This section goes over doing these "bugfix" releases.

1. Ensure all bugfixes are in trunk.

2. Make a branch off the affected version.

3. Cherry-pick the merge commits that merge the bugfixes into trunk, onto the new release branch.

4. Go through the rest of the process for a full release from "How to do a release candidate", merging the release branch into trunk as normal as the end of the process.

   - Instead of just ``--rc`` when running the change-versions script, add the patch flag, making it ``--patch --rc``.
   - Instead of waiting a week, a shorter pause is acceptable for a patch release.
