Twisted Release Process
=======================

This document describes the Twisted release process.
Although it is still incomplete, every effort has been made to ensure that it is accurate and up-to-date.

This process has only been tested on Linux or macOS, so we recommend that you do the release on Linux or macOS.

If you want to make changes to the release process, follow the normal Twisted development process (contribute release automation software that has documentation and unit tests demonstrating that it works).


Outcomes
--------

By the end of a Twisted release we'll have:

- Tarballs for Twisted as a whole, and for each of its sub-projects
- Windows installers for the whole Twisted project
- Updated documentation (API & howtos) on the twistedmatrix.com site
- Updated documentation on Read The Docs
- Updated download links on the twistedmatrix.com site
- Announcement emails sent to major Python lists
- Announcement post on `the Twisted blog <http://labs.twistedmatrix.com>`_
- A tag in our Git repository marking the release


Prerequisites
-------------

To release Twisted, you will need:

- Commit privileges to Twisted
- Access to ``dornkirk.twistedmatrix.com`` as t-web
- Permissions to edit the Downloads wiki page
- Channel operator permissions for ``#twisted``
- Admin privileges for Twisted's PyPI packages
- Contributor status for `the Twisted blog <http://labs.twistedmatrix.com>`_
- Read The Docs access for the Twisted project


Version numbers
---------------

Twisted releases use a time-based numbering scheme.
Releases versions like YY.MM.mm, where YY is the last two digits of the year of the release, MM is the month of release, and mm is the number of the patch release.

For example:

- A release in Jan 2017 is 17.1.0
- A release in Nov 2017 is 17.11.0
- If 17.11.0 has some critical defects, then a patch release would be numbered 17.11.1
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

#. Check the milestone for the upcoming release

   - Get rid of any non-critical bugs
   - Get any critical bugs fixed
   - Check the release manager notes in case anyone has left anything which can only be done during the release.

#. Check for any ​regressions

#. Read through the ``INSTALL.rst`` and ``README.rst`` files to make sure things like the supported Python versions are correct

   - Check the required Python version.
   - Check that the list matches the current set of buildbots.
   - Any mistakes should be fixed in trunk before making the release branch

#. Choose a version number.

#. File a ticket

   - Assign it to the upcoming release milestone
   - Assign it to yourself
   - Call it "Release $RELEASE"

#. Make a branch and attach it to the ticket:

   - ``git fetch origin``
   - ``git checkout origin/trunk``
   - ``git checkout -b release-$RELEASE-4290``


How to do a release candidate
-----------------------------

#. Check ​buildbot to make sure all supported platforms are green (wait for pending builds if necessary).
#. If a previously supported platform does not currently have a buildbot, move from supported platforms to "expected to work" in ``INSTALL.rst``.
#. In your Git repo, fetch and check out the new release branch.
#. Run ``python -m incremental.update Twisted --rc``
#. Commit the changes made by Incremental.
#. Run ``towncrier``.
#. Commit the changes made by towncrier - this automatically removes the NEWS newsfragments.
#. Bump copyright dates in ``LICENSE``, ``twisted/copyright.py``, and ``README.rst`` if required
#. Push the changes up to GitHub.
#. Run ``python setup.py sdist --formats=bztar -d /tmp/twisted-release`` to build the tarballs.
#. Copy ``NEWS.rst`` to ``/tmp/twisted-release/`` for people to view without having to download the tarballs.
   (e.g. ``cp NEWS.rst /tmp/twisted-release/NEWS.rst``)
#. Upload the tarballs to ``twistedmatrix.com/Releases/rc/$RELEASE`` (see #4353)

   - You can use ``rsync --rsh=ssh --partial --progress -av /tmp/twisted-release/ t-web@dornkirk.twistedmatrix.com:/srv/t-web/data/releases/rc/<RELEASE>/`` to do this.
#. Write the release candidate announcement

   - Read through the NEWS file and summarize the interesting changes for the release
   - Get someone else to look over the announcement before doing it
#. Announce the release candidate on

   - the twisted-python mailing list
   - on IRC in the ``#twisted`` topic

Release candidate announcement
------------------------------

The release candidate announcement should mention the important changes since the last release, and exhort readers to test this release candidate.

Here's what the $RELEASErc1 release announcement might look like::

    Live from PyCon Atlanta, I'm pleased to herald the approaching
    footsteps of the $API release.

    Tarballs for the first Twisted $RELEASE release candidate are now available at:
     http://people.canonical.com/~jml/Twisted/

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
#. Run ``python -m incremental.update Twisted``.
#. Revert the release candidate newsfile changes, in order.
#. Run ``towncrier`` to make the final newsfile.
#. Add the quote of the release to the ``README.rst``
#. Make a new quote file for the next version

   - ``git mv docs/fun/Twisted.Quotes docs/historic/Quotes/Twisted-$API; echo '' > docs/fun/Twisted.Quotes; git add docs/fun/Twisted.Quotes``

#. Commit the version and ``README.rst`` changes.
#. Submit the ticket for review
#. Pause until the ticket is reviewed and accepted.
#. Tag the release.

   - ``git tag -s twisted-$RELEASE -m "Tag $RELEASE release"``
   - ``git push --tags``


Cut the tarballs & installers
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

#. Using a checkout of the release branch or the release tag (with no local changes!), build the tarballs:

   - ``python setup.py sdist --formats=bztar -d /tmp/twisted-release``

#. Build Windows wheel

   - Download the latest ``.whl`` files from `Buildbot <https://buildbot.twistedmatrix.com/builds/twisted-packages/>`_ and save them in the staging directory

#. Sign the tarballs and Windows installers.
   (You will need a PGP key for this - use something like Seahorse to generate one, if you don't have one.)

   - MD5: ``md5sum Tw* | gpg -a --clearsign > /tmp/twisted-release/twisted-$RELEASE-md5sums.txt``
   - SHA512: ``shasum -a 512 Tw* | gpg -a --clearsign > /tmp/twisted-release/twisted-$RELEASE-shasums.txt``
   - Compare these to an ​example of ``twisted-$RELEASE-md5sums.txt`` - they should look the same.


Update documentation
~~~~~~~~~~~~~~~~~~~~

#. Get the dependencies

   - PyDoctor (from PyPI)

#. Build the documentation

   - ``./bin/admin/build-docs .``
   - ``cp -R doc /tmp/twisted-release/``

#. Run the build-apidocs script to build the API docs and then upload them (See also #2891).

   - Copy the pydoctor directory from the twisted branch into your Git checkout.
   - ``./bin/admin/build-apidocs . /tmp/twisted-release/api``
   - Documentation will be generated in a directory called ``/tmp/twisted-release/api``

#. Update the Read The Docs default to point to the release branch (via the `dashboard <https://readthedocs.org/projects/twisted/>`_).


Distribute
~~~~~~~~~~

#. Create a tarball with the contents of the release directory: ``cd /tmp/twisted-release; tar -cvjf ../release.tar.bz2 *``

#. Upload to the official upload locations (see #2888)

   - ``cd ~; git clone https://github.com/twisted-infra/braid``
   - ``cd braid``
   - ``virtualenv ~/dev/braid; source ~/dev/braid/bin/activate; cd ~/braid; python setup.py develop;``
   - ``cd ~/braid; fab config.production t-web.uploadRelease:$RELEASE,/tmp/release.tar.bz2``

#. Test the generated docs

   - Browse to ``http://twistedmatrix.com/documents/$RELEASE/``
   - Make sure that there is content in each of the directories and that it looks good
   - Follow each link on `the documentation page <https://twistedmatrix.com/trac/wiki/Documentation>`_, replace current with ``$RELEASE`` (e.g. 10.0.0) and look for any obvious breakage

#. Change the "current" symlink

   - Upload release: ``fab config.production t-web.updateCurrentDocumentation:$RELEASE``


Announce
~~~~~~~~

#. Update Downloads pages

   - The following updates are automatic, due to the use of the ​ProjectVersion wiki macro throughout most of the Downloads page.

     - Text references to the old version to refer to the new version
     - The link to the NEWS file to point to the new version
     - Links and text to the main tarball

   - Add a new md5sum link
   - Add a new shasum link
   - Save the page, check all links

#. Update PyPI records & upload files

   - ``pip install -U twine``
   - ``twine upload /tmp/twisted-release/Twisted-$RELEASE*``

#. Write the release announcement (see below)

#. Announce the release

   - Send a text version of the announcement to: twisted-python@twistedmatrix.com, python-announce-list@python.org, python-list@python.org, twisted-web@twistedmatrix.com
   - ​http://labs.twistedmatrix.com (Post a web version of the announcements, with links instead of literal URLs)
   - Twitter, if you feel like it
   - ``#twisted`` topic on IRC (you'll need ops)

#. Run ``python -m incremental Twisted --dev`` to add a `dev0` postfix.

#. Commit the dev0 update change.

#. Merge the release branch into trunk, closing the release ticket at the same time.

#. Close the release milestone (which should have no tickets in it).

#. Open a milestone for the next release.


Release announcement
~~~~~~~~~~~~~~~~~~~~

The final release announcement should:

- Mention the version number
- Include links to where the release can be downloaded
- Summarize the significant changes in the release
- Consider including the quote of the release
- Thank the contributors to the release

Here's an example::

    On behalf of Twisted Matrix Laboratories, I am honoured to announce
    the release of Twisted 13.2!

    The highlights of this release are:

     * Twisted now includes a HostnameEndpoint implementation which uses
    IPv4 and IPv6 in parallel, speeding up the connection by using
    whichever connects first (the 'Happy Eyeballs'/RFC 6555 algorithm).
    (#4859)

     * Improved support for Cancellable Deferreds by kaizhang, our GSoC
    student. (#4320, #6532, #6572, #6639)

     * Improved Twisted.Mail documentation by shira, our Outreach Program
    for Women intern. (#6649, #6652)

     * twistd now waits for the application to start successfully before
    exiting after daemonization. (#823)

     * SSL server endpoint string descriptions now support the
    specification of chain certificates. (#6499)

     * Over 70 closed tickets since 13.1.0.

    For more information, check the NEWS file (link provided below).

    You can find the downloads at <https://pypi.python.org/pypi/Twisted>
    (or alternatively <http://twistedmatrix.com/trac/wiki/Downloads>) .
    The NEWS file is also available at
    <http://twistedmatrix.com/Releases/Twisted/13.2/NEWS.txt>.

    Many thanks to everyone who had a part in this release - the
    supporters of the Twisted Software Foundation, the developers who
    contributed code as well as documentation, and all the people building
    great things with Twisted!

    Twisted Regards,
    HawkOwl


When things go wrong
--------------------

If you discover a showstopper bug during the release process, you have three options.

1. Abort the release, make a new point release (e.g. abort 10.0.0, make 10.0.1 after the bug is fixed)
2. Abort the release, make a new release candidate (e.g. abort 10.0.0, make 10.0.0pre3 after the bug is fixed)
3. Interrupt the release, fix the bug, then continue with it (e.g. release 10.0.0 with the bug fix)

If you choose the third option, then you should:

- Delete the tag for the release
- Recreate the tag from the release branch once the fix has been applied to that branch


Bug fix releases
----------------

Sometimes, bugs happen, and sometimes these are regressions in the current released version.
This section goes over doing these "point" releases.

1. Ensure all bugfixes are in trunk.

2. Make a branch off the affected version.

3. Cherry-pick the merge commits that merge the bugfixes into trunk, onto the new release branch.

4. Go through the rest of the process for a full release from "How to do a release candidate", merging the release branch into trunk as normal as the end of the process.

   - Instead of just ``--rc`` when running the change-versions script, add the patch flag, making it ``--patch --rc``.
   - Instead of waiting a week, a shorter pause is acceptable for a patch release.


Open questions
--------------

- How do we manage the case where there are untested builds in trunk?

- Should picking a release quote be part of the release or the release candidate?

- What bugs should be considered release blockers?

  - All bugs with a type from the release blocker family
  - Anybody can create/submit a new ticket with a release blocker type
  - Ultimately it's the RM's discretion to accept a ticket as a release blocker

- Should news fragments contain information about who made the changes?
