Code Review Process
===================


All commits to Twisted's trunk must follow this review process.

Both authors and reviewers should be intimately familiar with all requirements on this page.

Long story short for contributors / PR authors:

* Start by creating a GitHub Issue describing the issue or the reason a change is needed.
* Follow our coding standard and implement the required changes
* Create a GitHub Pull Request to have the changes merged in the main trunk
* Make sure all the PR checks are green and the changes are ready for review.
* Leave an explicit comment on the PR containing the `please review` text.
  You can use a `draft PR` but once ready, leave the explicit comment asking for the review.
  This will trigger the review process and the required team notifications.
* Wait for a review or try to find a review via IRC, mailing list or Gitter
* Engage in a conversation with the reviewer to get the changes approved.
* Once the changes from the PR are approved, the PR can be merged.


Authors: Before you get started
-------------------------------

For the most part, we'd love for you to jump right in and start writing code!
The code review process should catch any serious problems with your contribution,
and the continuous integration system should catch most tricky cross-platform issues.
It's easy to get too caught up in trying to do everything perfectly the first time and never get any code written,
so you should usually err on the side of just trying something out rather than waiting for someone to tell you if it's OK.
That being said, there are a few things that you should be aware of before you write your first line of code.

Make sure you have a *clear idea of what work needs doing*.
Write down your idea first; `file an issue <https://github.com/twisted/twisted/issues/new/choose>`_ before you write a patch.
A really good issue will give a precise description of what needs to change and why it needs changing;
it avoids giving precise details of exactly *how* the code needs to change,
because the patch should supply those details.
A really *bad* issue will say "here is a patch I wrote, apply it".
If you're just getting started with contributing to Twisted,
it would be good to find an existing issue rather than come up with something yourself,
so you have an idea how to go through the process before you start making difficult changes.
You'll need to have a good description of your work for other parts of the process as well (the NEWS file, the commit message) which is another reason thinking about what you're trying to do helps.

**If you're filing a bug because you noticed a regression** in the current pre-release,
make sure to mark it as a regression,
add it to the release milestone, and post something to the mailing list as well.
It's very important for us to spot regressions before they make it into a final release,
so redundant communication is better in this case!

Issues should be described well enough that the change is already justified and the new code should be easy enough to read that further explanations aren't necessary to understand it, but sometimes diffs themselves can be more difficult to read than either the old or new state of the code, so comments like ''the implementation of foo moved from bar.py to baz.py'' can sometimes make a reviewer's job easier.

Try **not** to *write too much code at once*.
A good change needs to be under 1000 lines of diff for a reviewer to be able to deal with it before getting fatigued and missing things.
You should be aiming for things in the neighborhood of 200 lines.
This is for your benefit as well as the reviewer's; we don't want you to spend weeks on a 10,000-line monster of a feature,
only to have it rejected because we're not interested in having such a feature at all.


Authors: Things your branch or patch must contain
-------------------------------------------------

 * Code which follows the :doc:`coding standards </development/coding-standard>`.
 * 100% unit test coverage for all modified and new code (even if it didn't have tests before)
 * 100% API docstring coverage for all modified and new code (even if it didn't have docs before)
 * No :doc:`backwards-incompatible </development/compatibility-policy>` changes.
   Also be sparing when adding 'public' names to the API, as they must be supported in the future.
   If it can start with an underscore and not be exposed publicly, it probably should.
 * Appropriate new or modified "End User" guide documentation (in the form of rst files in the `docs/ <https://github.com/twisted/twisted/tree/trunk/docs>`_ directory)
 * A file in all relevant "newsfragments" directories describing changes that affect users See the Newsfiles section below.


Authors: How to get your change reviewed
----------------------------------------

* There must be an issue in the Twisted Github Issue tracker describing the desired outcome.
   See more info below.
* **Note**: For security issues, see :doc:`Security </security>`.
* Create a GitHub Pull request
* Write a comment or PR description with any relevant information for the reviewer.
* Once the PR is ready for review,
  leave a separate comment on that PR containing the text `please review`.
  This will trigger the review process and will notify the review team.


Reviewers: How to review a change
---------------------------------

 * Be familiar with the Twisted codebase, coding standard, and these review requirements.
 * Don't be the author of the change.
   It makes no sense to review your code, and we assume that before pushing the code to a public PR,
   you already did the first round of self-review.
 * Make sure that all checks are **green**!
 * Note any unreliable / flaky tests should have a separate issue created.
 * Review the change, and write a detailed comment about all potential improvements to the branch (See [#Howtobeagoodreviewer below]).
 * Use GitHub review UI to approve or request changes to the PR.
 * If the author does not have commit access, merge the change for them or add the "needs-merge" label.


Authors: How to merge the change to trunk
-----------------------------------------

 * If your reviewers are happy with the changes for your PR, you can merge it.
 * Check in the GitHub PR that all tests are green (or the failed one are just unrelated/spurious failures)
 * Use the GitHub merge button to merge the request, using the GitHub default commit subject, and with the standard commit format required by Twisted. See below for details.
 * Alternatively, you can use the command line and merge the change into a checkout of Twisted trunk (as a merge commit, using `git merge --no-ff`) and commit it.

The commit message, when using both the GitHub button or the CLI commit, must follow this format.
This helps automatically close the associated ticket::

    Merge pull request #123 from twisted/FIRST-LINE-AUTOMATICALLY-GENERATED-BY-GITHUB

    Author: comma_separated_github_username
    Reviewer: comma_separated_github_usernames
    Fixes #issue number

    Long description (as long as you wish)

If this fix has implications for an ongoing pre-release in progress,
please announce it on the mailing list so that the release manager will know.

A change has implications for the release process if:

* a pre-release has been issued for which there is no final release
* this issue was a known regression and is now closed, so another pre-release should be issued
* this issue was in the release milestone and is now closed, so another pre-release should be issued
* as part of the final review, the reviewer noticed that this is fixing something that could be considered a regression.
  In general, if there's any doubt, communicate to the mailing list.  The mailing list is fairly low traffic, and so a little extra noise about interesting developments is much better than letting an important fix slip through the cracks.  If you're not sure whether something qualifies as a regression or not, let the release manager know so they can decide.
* If no regression appears, you can delete the source branch.


Who can review a PR?
--------------------

Changes must be reviewed by a developer other than the author of the changes. If changes are paired on, a third party must review them.  If changes constitute the work of several people who worked independently, a non-author must review them.

A reviewer need not necessarily be familiar with the specific area of Twisted being changed, but he or she should feel confident in his or her abilities to spot problems in the change.

Twisted committers may review anyone's PRs; those submitted by other committers or those submitted by non-committer contributors.  If a non-committer contributor submits a PR that is acceptable to merge, it is the committer's responsibility to commit and merge the PR.  When a committer reviews a PR, they are responsible if there are any problems with the review.

Non-committer contributors may review PRs that committers have submitted.  When a non-committer does a passing review, the committer may accept it and land their change, but they are then responsible for the adequacy of the review.  So, if a non-committer does a review you feel might be incomplete, put it back into review and explain what they might have missed - this kind of reviewing-the-review is important to make sure that more people learn how to do reviews well!


How to be a good reviewer
-------------------------

First, make sure all of the obvious things are accounted for.
Check the "Things your branch or patch must contain" list above,
and make sure each point applies to the branch.

A reviewer may reject a change for various reasons, many of which are hard to quantify.
Use your best judgment, and don't be afraid to point out problems that don't fit into the list of branch requirements laid out in this document.

Here are some extra things to consider while reviewing a change:

* Is the code written in a straightforward manner that will allow it to be easily maintained in the future,
  possibly by a developer other than the author?
* If it introduces a new feature, is that feature generally useful and have its long-term implications been considered and accounted for?
  * Will it confuse application developers?
  * Does it encourage application code using it to be well factored and easily testable?
  * Is it similar to any existing feature offered by Twisted, such that it might make sense as an extension or modification to some other piece of code, rather than an entirely new functional unit?
* Does it require new documentation and examples?

When you're done with the review, always say what the next step should be: for example, if the author is a committer, can they commit after making a few minor fixes?  If your review feedback is more substantial, should they re-submit for another review?

If you are officially "doing a review", please make sure you do a complete review and look for ''all'' of these things, so that the author has as much feedback as possible to work with while their ticket is out of the review state.  If you don't have time to do a complete review, and you just notice one or two things about the ticket, just make a comment to help the future reviewer, and don't remove the review keyword, so another reviewer might have a look.  For example, say, "I just checked for a news file and I noticed there wasn't one", or, "I saw some trailing whitespace in these methods".  If you remove the PR from the review queue, you may substantially increase the amount of time that the author has to wait for a real, comprehensive review, which is very frustrating.
