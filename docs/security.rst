Report a security issue
=======================

We take security very seriously.
Your input and feedback on our security is always appreciated.

You can send urgent or sensitive reports directly to security@twistedmatrix.com

You may use our public key (below) to keep your message safe.
Provide us with a secure way to respond.
We'll get back to you as soon as we can.

Twisted is an all volunteer project and there may be some delay before we can respond.

Feel free to follow up if you think an unreasonable amount of time has elapsed without a response!

All releases, including security releases, are announced on the mailing list.
Consider subscribing to receive notification about the availability of a security fix.


Security Procedure for Developers
=================================

The goal of the normal Twisted development procedure is to make all steps transparent and record all information at all times in a public location - either the issue tracker or a branch.

The goal of the security variation of the Twisted development procedure is to keep track of progress resolving security issues while minimizing the window of time where information useful to attackers is available before a fix for the issue is available to Twisted users.

This process is intended as a helpful recommendation.
Elements of it may be followed more or less strictly depending on the severity of the issue in question:

#. Begin by filing a ticket which does not describe the issue and simply says 'security issue, description pending' and has the 'security' keyword.

#. Create a security advisory in GitHub using the `GitHub UI <https://github.com/twisted/twisted/security/advisories/new>`_.
   This will trigger the creation of a private repository that can be use for developing a patch.
   This automatically created private repository is also used to review the PR in private.

#. Make the required changes to fix the security issue in the new private repository.

#. Create a new PR using the GitHub security advisory UI.
   This will generate a private PR.
   Request the review and get the approval for the PR.
   Don't merge the PR after approval.
   In the PR description define the desired merge commit message.
   The PR will be merged by the release manager at the same time with the first release candidate.

#. Automated notifications for the private repository and private PR are limited.
   Try to communicate over IRC, gitter or other means to find a person to
   review the new PR.
   Coordinate with the release manager.
   More info about the release process can be found on the :doc:`release process </core/development/policy/release-process>` dedicated page.

#. We are not aware of a way to securely transmit our code to our public continuous integration systems.
   Reviewers should manually run the automated tests on their local forks of the new private repository.

Aside from hiding the details of the issue while development is ongoing,
all of the normal policies apply.
Security fixes require unit tests, code review, etc.


PGP key for email communication
-------------------------------

Below is the PGP key for security@twistedmatrix.com::

    -----BEGIN PGP PUBLIC KEY BLOCK-----
    Version: GnuPG v2.0.22 (Darwin)

    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
    2pOVp6XTYdUW
    =HDSq
    -----END PGP PUBLIC KEY BLOCK-----


Security Audit
==============

We need to do a full audit of Twisted, module by module.
This document list the sort of things you want to look for
when doing this, or when writing your own code.


Bad input
---------

Any place we receive untrusted data, we need to be careful.
In some cases we are not careful enough. For example, in HTTP
there are many places where strings need to be converted to
ints, so we use ``int()`` . The problem
is that this will accept negative or hexadecimal (`0x123`) numbers as well, whereas
the protocol should only be accepting positive numbers.


Resource Exhaustion and DoS
---------------------------

Make sure we never allow users to create arbitrarily large
strings or files. Some of the protocols still have issues
like this. Place a limit which allows reasonable use but
will cut off huge requests, and allow changing of this limit.

Another operation to look out for are exceptions. They can fill
up logs and take a lot of CPU time to render in web pages.
