## Scope and purpose

Fixes #<!-- ISSUE-ID -->

<!-- Add a few words about why this PR is needed and what is its scope. -->


<!-- If the associated issue fully explains the need you can just refer to it. -->
<!-- Add any comments about trade-offs (if any) made in this PR and the reasoning behind them. -->
<!-- Link to any follow-ups -->

## Contributor Checklist:

Have a look at [our developer documentation](https://docs.twisted.org/en/latest/development/dev-process.html) before submitting your Pull Request.

The following checklist applies to *all* pull requests - no matter how small.
(PRs which have completed this checklist will get reviewed much faster.)

* [ ] I have not directly included the output of any generative AI system in this pull request, as per Twisted's [policy on generative AI](https://docs.twisted.org/en/latest/development/ai-policy.html).
* [ ] I have linked to a GitHub Issue describing the problem that this issue is solving in the `Fixes #` line above.
      (All PRs must resolve at least one issue.
      For larger PRs, describing the problem *before* submitting a PR is very useful to make sure you're solving the right thing.
      Someone from the core team will probably do this for you if this is a small, obvious fix and you forget, but your review might go a bit faster if you do it yourself.)
* [ ] I have edited the PR title to be the issue number followed by a description of the change being made, like `#1234 fix crash in reactor.run()`.
* [ ] I have created a release notes news fragment file in src/twisted/newsfragments/
      (see: [Release notes fragments docs.](https://docs.twisted.org/en/latest/core/development/dev-process.html#release-notes-management). CI will fail and block your review if you don't do this.)
* [ ] I have updated the automated tests to cover any modified code and to verify any changed behavior.
      (OR, if appropriate, I certify that this PR changes only configuration or documentation and does not have associated automated tests.)
* [ ] I have requested a review by leaving a comment that contains exactly the string `please review`.
      (Our bot will trigger the review process, by applying the pending review label and requesting a review from the Twisted dev team.)
