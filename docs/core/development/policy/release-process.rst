Twisted Release Process
=======================

This document describes the Twisted release process.
Although it is still incomplete, every effort has been made to ensure that it is accurate and up-to-date.

This process has only been tested on Linux or OS X, so we recommend that you do the release on Linux or OS X.

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
- Announcement post on ​http://labs.twistedmatrix.com
- A tag in our Subversion repository marking the release


Prerequisites
-------------

To release Twisted, you will need:

- Commit privileges to Twisted
- Access to dornkirk.twistedmatrix.com as t-web
- Permissions to edit the Downloads wiki page
- Channel operator permissions for ``#twisted``
- Admin privileges for Twisted's PyPI packages
- Contributor status for ​http://labs.twistedmatrix.com
- Read The Docs access for the Twisted project


Version numbers
---------------

Twisted releases use a time-based numbering scheme.
Releases versions like YY.MM.mm, where YY is the last two digits of the year of the release, MM is the number of the release in the year, and mm is the number of the patch release.

For example:

- The first release of 2010 is 10.0.0
- The second release of 2010 is 10.1.0
- If 10.1.0 has some critical defects, then a patch release would be numbered 10.1.1
- The first pre-release of 10.0.0 is 10.0.0pre1, the second is 10.0.0pre2

Every release of Twisted includes the whole project, the core and all sub-projects. Each of these has the same number.

Throughout this document, we'll refer to the version number of the release as $RELEASE. Examples of $RELEASE include 10.0.0, 10.1.0, 10.1.1 etc.

We'll refer to the first two components of the release as $API, since all releases that share those numbers are mutually API compatible.
e.g. for 10.0.0, $API is 10.0; for 10.1.0 and 10.1.1, $API is 10.1.

The change-versions script automatically picks the right number for you.
Please retrieve it after you run it.


Overview
--------

To release Twisted, we

1. Prepare for a release
2. Release N pre-releases
3. Release the final release


Prepare for a release
---------------------

1. Check the milestone for the upcoming release

  - Get rid of any non-critical bugs
  - Get any critical bugs fixed
  - Check the release manager notes in case anyone has left anything which can only be done during the release.

2. Check for any ​regressions
3. Read through the ``INSTALL`` and ``README`` files to make sure things like the supported Python versions are correct

  - Check the required Python version.
  - Check that the list matches the current set of buildbots.
  - Any mistakes should be fixed in trunk before making the release branch

4. Choose a version number.
5. File a ticket

  - Assign it to the upcoming release milestone
  - Assign it to yourself
  - Call it "Release $RELEASE"

6. Make a branch (``mkbranch release-$RELEASE-4290``, using ``mkbranch`` from ``twisted-dev-tools``)

How to do a pre-release
-----------------------

1. Check ​buildbot to make sure all supported platforms are green (wait for pending builds if necessary).
2. If a previously supported platform does not currently have a buildbot, move from supported platforms to "expected to work" in ``INSTALL``. (Pending #1305)
3. In your Git-SVN-enabled Git repo, fetch and check out the new release branch.
4. Run ``./bin/admin/change-versions --prerelease``
5. Commit the changes made by change-versions
6. Run ``./bin/admin/build-news .``
7. Commit the changes made by build-news - this automatically removes the NEWS topfiles (see #4315)
8. Bump copyright dates in ``LICENSE``, ``twisted/copyright.py``, and ``README`` if required
9. ``git svn dcommit --dry`` to make sure everything looks fine, and then ``git svn dcommit`` to push up the changes.
10. Run ``python setup.py sdist -d /tmp/twisted-release`` to build the tarballs.
11. Copy ``NEWS`` to ``/tmp/twisted-release/`` as ``NEWS.txt`` for people to view without having to download the tarballs.
    (e.g. ``cp NEWS /tmp/twisted-release/NEWS.txt``)
12. Upload the tarballs to ``twistedmatrix.com/Releases/pre/$RELEASE`` (see #4353)

  - You can use ``rsync --rsh=ssh --partial --progress -av /tmp/twisted-release/ t-web@dornkirk.twistedmatrix.com:/srv/t-web/data/releases/pre/<RELEASE>/`` to do this.

13. Write the pre-release announcement

  - Read through the NEWS file and summarize the interesting changes for the release
  - Get someone else to look over the announcement before doing it

14. Announce the pre-release on

  - the twisted-python mailing list
  - on IRC in the ``#twisted`` topic
  - in a blog post, ideally labs.twistedmatrix.com


Pre-release announcement
------------------------

The pre-release announcement should mention the important changes since the last release, and exhort readers to test this pre-release.

Here's what the $RELEASEpre1 release announcement might look like::

    Live from PyCon Atlanta, I'm pleased to herald the approaching
    footsteps of the $API release.

    Tarballs for the first Twisted $RELEASE pre-release are now available at:
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

1. Have the release branch, previously used to generate a pre-release, checked out
2. Run ``./bin/admin/change-versions``
3. Add the quote of the release to the ``README``
4. Make a new quote file for the next version

   - ``git mv docs/fun/Twisted.Quotes docs/historic/Quotes/Twisted-$API; echo '' > docs/fun/Twisted.Quotes; git add docs/fun/Twisted.Quotes``

5. Commit the version and ``README`` changes.
6. Submit the ticket for review
7. Pause until the ticket is reviewed and accepted.
8.  Tag the release

  - e.g. ``svn cp svn+ssh://svn.twistedmatrix.com/svn/Twisted/branches/releases/release-$RELEASE-4290 svn+ssh://svn.twistedmatrix.com/svn/Twisted/tags/releases/twisted-$RELEASE``
  - A good commit message to use is something like "Tag $RELEASE release"


Cut the tarballs & installers
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. Using a checkout of the release branch or the release tag (with no local changes!), run ``python setup.py sdist -d /tmp/twisted-release`` to build the tarballs.
2. Build Windows MSI

  - ​http://buildbot.twistedmatrix.com/builders/windows7-64-py2.7-msi
  - For "Branch" specify the release branch, e.g. "branches/releases/release-$RELEASE-4290"
  - Download the latest .whl files from from ​http://buildbot.twistedmatrix.com/builds/twisted-packages/ and save them in the staging directory

3. Sign the tarballs and Windows installers.
   (You will need a PGP key for this - use something like Seahorse to generate one, if you don't have one.)

  - MD5: ``md5sum Tw* | gpg -a --clearsign > /tmp/twisted-release/twisted-$RELEASE-md5sums.txt``
  - SHA512: ``shasum -a 512 Tw* | gpg -a --clearsign > /tmp/twisted-release/twisted-$RELEASE-shasums.txt``
  - Compare these to an ​example of ``twisted-$RELEASE-md5sums.txt`` - they should look the same.


Update documentation
~~~~~~~~~~~~~~~~~~~~

1. Get the dependencies

  - Pydoctor (use the branch "twisted" from ​https://github.com/twisted/pydoctor)
  - Epydoc (python-epydoc in Debian)

2. Build the documentation

  - ``./bin/admin/build-docs .``
  - ``cp -R doc /tmp/twisted-release/``

3. Run the build-apidocs script to build the API docs and then upload them (See also APIDocs and #2891).

  - Copy the pydoctor directory from the twisted branch into your Git checkout.
  - ``./bin/admin/build-apidocs . /tmp/twisted-release/api``
  - Documentation will be generated in a directory called ``/tmp/twisted-release/api``

4. Update the Read The Docs default to point to the release branch (via the `dashboard <https://readthedocs.org/projects/twisted/>`_).


Distribute
~~~~~~~~~~

1. Create a tarball with the contents of the release directory: ``cd /tmp/twisted-release; tar -cvjf ../release.tar.bz2 *``
2. Upload to the official upload locations (see #2888)

  - ``cd ~; git clone https://github.com/twisted-infra/braid``
  - ``cd braid``;
  - ``virtualenv ~/dev/braid; source ~/dev/braid/bin/activate; cd ~/braid; python setup.py develop;``
  - ``cd ~/braid; fab config.production t-web.uploadRelease:$RELEASE,/tmp/release.tar.bz2``

3. Test the generated docs

  - Browse to ​``http://twistedmatrix.com/documents/$RELEASE/``
  - Make sure that there is content in each of the directories and that it looks good
  - Follow each link on ​http://twistedmatrix.com/trac/wiki/Documentation, replace current with $RELEASE (e.g. 10.0.0) and look for any obvious breakage

4. Change the "current" symlink

   - Upload release: ``fab config.production t-web.updateCurrentDocumentation:$RELEASE``


Announce
~~~~~~~~

1. Update Downloads pages

  - The following updates are automatic, due to the use of the ​ProjectVersion wiki macro throughout most of the Downloads page.

    - Text references to the old version to refer to the new version
    - The link to the NEWS file to point to the new version
    - Links and text to the main tarball

  - Add a new md5sum link
  - Add a new shasum link
  - Save the page, check all links

2. Update PyPI records & upload files

  - ​http://pypi.python.org/pypi/Twisted/

    - Edit the version. *Make sure you do this first.*
    - Upload tarball, MSIs and wheels

3. Write the release announcement (see below)
4. Announce the release

  - Send a text version of the announcement to: twisted-python@twistedmatrix.com, python-announce-list@python.org, python-list@python.org, twisted-web@twistedmatrix.com
  - ​http://labs.twistedmatrix.com (Post a web version of the announcements, with links instead of literal URLs)
  - Twitter, if you feel like it
  - ``#twisted`` topic on IRC (you'll need ops)

5. Merge the release branch into trunk, closing the release ticket at the same time.

  - For now you need to add a ``.misc`` NEWS fragment to merge the branch.

6. Close the release milestone (which should have no tickets in it).
7. Open a milestone for the next release.


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
2. Abort the release, make a new pre-release (e.g. abort 10.0.0, make 10.0.0pre3 after the bug is fixed)
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

  - eg. ``svn cp svn+ssh://svn.twistedmatrix.com/svn/Twisted/branches/releases/release-$API.0-7844 svn+ssh://svn.twistedmatrix.com/svn/Twisted/branches/releases/release-$API.1-7906 -m "Branching to $API.1"``

3. Cherry-pick the merge commits that merge the bugfixes into trunk, onto the new release branch.
4. Go through the rest of the process for a full release from "How to do a pre-release", merging the release branch into trunk as normal as the end of the process.

  - Instead of just ``--prerelease`` when running the change-versions script, add the patch flag, making it ``--patch --prerelease``.
  - Instead of waiting a week, a shorter pause is acceptable for a patch release.


Open questions
--------------

- How do we manage the case where there are untested builds in trunk?
- Should picking a release quote be part of the release or the pre-release?
- What bugs should be considered release blockers?

  - All bugs with a type from the release blocker family
  - Anybody can create/submit a new ticket with a release blocker type
  - Ultimately it's the RM's discretion to accept a ticket as a release blocker

- Should news fragments contain information about who made the changes?
