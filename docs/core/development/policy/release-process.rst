Twisted Release Process
=======================

This document describes the Twisted release process.
Although it is still incomplete, every effort has been made to ensure that it is accurate and up-to-date.

If you want to make changes to the release process, follow the normal Twisted development process (contribute release automation software that has documentation and unit tests demonstrating that it works).


Outcomes
--------

By the end of a Twisted release we'll have:

- Wheel and sdist package published on `PyPI Twisted project <https://pypi.org/project/Twisted/>`_.
- Updated documentation (API & howtos) on `Twisted Read The Docs <https://docs.twistedmatrix.com/>`_ for `stable` and `$RELEASE` versions.
- Announcement email sent to Twisted main list
- A `GitHub Release <https://github.com/twisted/twisted/releases>`_ with the associated tag in our Git repository


Prerequisites
-------------

To release Twisted, you will need:

- Commit privileges to Twisted GitHub repository.


Dependencies
------------

Below is the list of moving parts and web services used by the release process.
For day to day operation, you should not need management access to them.
If things go wrong, you should be aware of them and get administration access.

* Release tag is automatically created via the GitHub Release GUI.
* PyPi file publishing is done via GitHub Actions workflow when a tag is created.
  Any Twisted contributor in GitHub should have access to modify the workflow.
* docs.twistedmatrix.com is a CNAME and you will need access to Twisted DNS server to modify it.
* Documentation is published via `Read The Docs Twisted project <https://readthedocs.org/dashboard/twisted/edit/>`_.
  There is an `automated rule <https://readthedocs.org/dashboard/twisted/rules/regex/1057/>` to activate the documentation for every tag matching ``^twisted-\d+\.\d+\.\d+$`` (release candidates are excluded)
  From RTD `Advanced Settings <https://readthedocs.org/dashboard/twisted/advanced/>`_ the branch named `stable` is configured as the default branch.
  There is also a "active" documentation version for the branch named `stable`.


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

#. Check for any regressions using `Trac regression report <https://twistedmatrix.com/trac/report/26>`_

#. Any regression should be fixed and merged into trunk before making the release branch

#. Choose a version number.
   $RELEASE will be something like 21.7.0 for a major release.
   $RELEASE will be something like 21.7.1 for a bugfix release.

#. File a ticket in Trac called "Release $RELEASE" and assign it to yourself.

#. Make a branch for the release.
   It's very important to use `release-$RELEASE-$TRAC_ID` as the branch name (4290 is Trac ticket ID, 21.7.0 is the release number) as this is used as a hint for CI:

   - ``git fetch origin``
   - ``git checkout origin/trunk``
   - ``git checkout -b release-21.7.0-4290``


How to do a release candidate
-----------------------------


This section describes the steps and requirements for creating the first release candidate.


Prepare the branch
~~~~~~~~~~~~~~~~~~

#. Check that all the CI tests on the main branch (trunk) pass.
   Failing tests on the main branch should be considered release blocker.
   They should be fixed in separate ticket/PR.
   The release can continue once the main branch is green again.
#. In your Git repo, fetch and check out the new release branch.
#. Run ``python -m incremental.update Twisted --rc``
#. Commit the changes made by Incremental.
#. Run ``tox -e towncrier``.
#. Commit the changes made by towncrier - this automatically removes the newsfragment files.
#. Bump copyright dates in ``LICENSE``, ``src/twisted/copyright.py``, and ``README.rst`` if required
#. Push the changes up to GitHub and create a new release PR.
#. The GitHub PR is dedicated to the final release and the same PR is used to release the candidate and final version.
#. Wait for all the PR checks to pass.
#. If a check fails investigate it.
   If is just a flaky tests, retry the run.
   Any serious error should be considered a blocker and should be
   fixed in a separate ticket/PR.
   Avoid making non-release changes (even minor one) as part of the release branch.
#. Use the `GitHub Create Release UI <https://github.com/twisted/twisted/releases/new>`_ the make a new release.
#. Create a tag using the format `twisted-VERSION` based on the latest commit on the release branch.
#. Use `Twisted VERSION` as the name of the release.
#. Add the release NEWS to GitHub Release page.
#. Make sure 'This is a pre-release` is checked.
#. Github Actions will upload the dist to PyPI when a new tag is pushed to the repo.
#. You can check the status of the automatic upload via `GitHub Action <https://github.com/twisted/twisted/actions/workflows/test.yaml?query=event%3Apush>`_
#. Read the Docs hooks not have version for the release candidate.
   Use the Read the Docs published for the pull request.
#. The review for the PR will be requested after the files are on PyPI so that a full review and manual test can be done.
#. Most probably there will be some minor comments received via email or GitHub regarding the final content of the release notes.
   It's OK to make those changes as part of the release branch.
   It's OK to update the text of the candidate release notes,
   in the final NEWS file the release candidate version is removed and replaced with the final version.
   No need for a new ticket or separate pull request.
   These changes will be reviewed as part of the final release review process.
#. While the final public release is not made and the release tag created
   the release branch will not be kept up to date with trunk.


Announce
~~~~~~~~

#. Write the release announcement

#. Announce the release candidate on

   - the twisted-python mailing list by sending the an email with the subject: Twisted $RELEASE Pre-Release Announcement
   - on IRC in the ``#twisted-dev`` topic by sending the version number or pip install command

The release candidate announcement might mention the important changes since the last release, and ask readers to test this release candidate.

Here's what the $RELEASE release candidate announcement might look like::

   On behalf of the Twisted contributors I announce the release candidate of Twisted $RELEASE

   Short summary of the release.
   For example:
   Python 3.5 is no longer a supported platform.
   The minimum supported platform is Python 3.6.7.


   The notable changes are:

   * Mention the main new features.
   * As well as important bug fixes
   * Or deprecation/removals

   The release and NEWS file is available for review at

      https://github.com/twisted/twisted/pull/PRID/files

   Release candidate documentation is available at

      https://twisted--PRID.org.readthedocs.build/en/PRID/

   Wheels for the release candidate are available on PyPI

      https://pypi.org/project/Twisted/$RELEASErc1

      python -m pip install Twisted==$RELEASErc1

   Please test it and report any issues.
   If nothing comes up in one week,
   $RELEASE will be released based on the latest release candidate.

   Many thanks to everyone who had a part in Twisted
   the supporters of the Twisted Software Foundation,
   the developers, and all the people testing and building great things with Twisted!

A week is a generally good length of time to wait before doing the final release.


How to do a final release
-------------------------


Prepare the branch
~~~~~~~~~~~~~~~~~~

#. Have the release branch, previously used to generate a release candidate, checked out
#. Run ``python -m incremental.update Twisted --newversion $RELEASE``
#. Manually update the release version and date inside the NEWS file.
   The release candidate notes will be removed from the final NEWS file.
   Manually move all the release notes from the release candidates to the notes for the final version.
#. Commit and push.
#. Submit the ticket for the final review.
#. Pause until the ticket is reviewed and accepted.
#. Use the `GitHub Create Release UI <https://github.com/twisted/twisted/releases/new>`_ the make a new release.
#. Create a tag using the format `twisted-VERSION` based on the latest commit on the release branch that was approved after the review.
#. Use `Twisted VERSION` as the name of the release.
#. Add the release NEWS to GitHub Release page.
#. Make sure 'This is a pre-release` is not checked.
#. Github Actions will upload the dist to PyPI when a new tag is pushed to the repo. PyPI is the only canonical source for Twisted packages.
#. Read the Docs hooks will publish a new version of the docs for the tag.


Announce
~~~~~~~~

#. Write the release announcement that should be similar to the release candidate, with the updated version and release date.

#. Announce the release

   - Send a text version of the announcement to: twisted@python.org
   - Twitter, TikTok, Instagram, Snapchat if you feel like it :)
   - ``#twisted`` message on IRC


Post release
~~~~~~~~~~~~

#. Run ``python -m incremental.update Twisted --post`` to add a `post` version number.

#. Commit the post0 update change.

#. Update the trunk into the release branch, resolving any possible conflicts.

#. No need to request another review.

#. Merge the release branch into trunk (via GitHub PR UI),
   closing the release ticket at the same time.


Release candidate fixes
-----------------------

This section described the steps to follow when after a release candidate is published, critical or regression defects are found.

If a defect is found after the final release is published, check the next section: `Bug fix releases`.

1. Pause the release process.
2. Separate tickets should be files for each defect.
3. The defect should be fixed, reviewed and merged in trunk.
4. On the release branch, cherry-pick the merges from trunk that merges the fixes `git cherry-pick -m 1 TRUNK_MERGE_SHA`.
5. Follow the same steps as for any release candidate, with the exception that a new branch is not created.
   Use the same `python -m incremental.update Twisted --rc` command to increment the release candidate version.

Don't delete a tag that was already pushed for a release.
Create a new tag with incremented version.


Bug fix releases
----------------

Sometimes, bugs happen, and sometimes these are regressions in the current released version.
This section goes over doing these "bugfix" releases.

1. Ensure all bugfixes are in trunk.

2. Make a branch off the affected released version (not from trunk HEAD).

3. Cherry-pick the merge commits that merge the bugfixes into trunk, onto the new release branch.

4. Go through the rest of the process for a full release from "How to do a release candidate", merging the release branch into trunk as normal as the end of the process.

   - Instead of just ``--rc`` when running the change-versions script, add the patch flag, making it ``--patch --rc``.
   - Instead of waiting a week, a shorter pause is acceptable for a patch release.
     You can do the release as soon as you get the confirmation from the original bug reports that the release candidate fixes the issues.

5. If you are doing a security release for an older release,
   the automated release will overwrite the `stable` branch and consider it as the latest release.
   You will need to manually reset/rebase the `stable` branch to point to the actual latest release.
