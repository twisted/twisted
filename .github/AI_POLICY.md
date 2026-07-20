# Generative AI / LLM Policy

The Twisted policy is based on the [_attrs AI policy_][attrs-policy].

We appreciate that we can't realistically police how you author your pull requests,
which includes whether you employ large-language model (LLM)-based development tools.
So, we don't.

However, due to both legal and human reasons, we have to establish boundaries.

> [!CAUTION]
> **TL;DR:**
> - We take the responsibility for this project very seriously and we expect you to take your responsibility for your contributions seriously, too.
>   This used to be a given, but it changed now that a pull request is just one prompt away.
>
> - Every contribution has to be backed by a human who unequivocally owns the copyright for all changes.
>   Listing AI tooling as a co-author, co-signing commits using an AI tool, or using the assisted-by, co-developed or similar commit trailer is not allowed.
>
> - No LLM output in issues, PRs, code, documentation, or any interaction with the other contributors.
>  LLM-based autocomplete falls under the same policy as LLM generated content.
>
> - You can use AI tools to help with research and investigation for new features or bugs.
>
> - Absolutely **no** unsupervised agentic tools or "AI pipeline".
>


## Pull requests

By submitting a pull request, you certify that:

 - You are the author of the contribution or have the legal right to submit it.
 - You either hold the copyright to the changes or have explicit legal authorization to contribute them under this project's license.
 - As the author, you are responsible for understanding every change.
 - You accept full responsibility for it.
 - When responding to review comments, you must do so without relying on AI tools.
   Reviewers want to engage directly with you, not with generated responses.
   If you do not engage directly with reviewers, the PR will be closed.


## Issue/bugs/security reports

If you used AI tools in preparing your report, you must disclose this in report.

Proper attribution helps track the evolving role of AI in the development process.


## Legal

There is ongoing legal uncertainty regarding the copyright status of LLM-generated works and their provenance.
Since we do not have a formal [Contributor License Agreement](https://en.wikipedia.org/wiki/Contributor_license_agreement) (CLA),
you retain your copyright to your changes to this project.

Therefore, allowing contributions by LLMs has unpredictable consequences for the copyright status of this project – even when leaving aside possible copyright violations due to plagiarism.

AI agents **must not** add Signed-off-by tags.
Only humans can legally certify the Developer Certificate of Origin (DCO).
The human submitter is responsible for:

- Reviewing all AI-generated code
- Ensuring compliance with licensing requirements
- Adding their own Signed-off-by tag to certify the DCO
- Taking full responsibility for the contribution


## Human

As the makers of software that is used by millions of people worldwide and with a reputation for high-quality maintenance, we take our responsibility to our users very seriously.
No matter what LLM vendors or boosters on LinkedIn tell you, we have to manually review every change before merging, because it's **our responsibility** to keep the project stable.

You can use LLM tools to help with research and investigation for new features or bugs.
You can use "AI mode" in search engines, use AI tools to generate reports, AI spell-checkers or other code review tools.
Make sure any output from those tools is kept outside of the Twisted code tree.

Any LLM tooling cannot be allowed to write to the code,
whether you **review** that or not.
Human review of LLM outputs tends to decay over time, and so we have to set a hard line to prevent that gradual slide.
You cannot copy and paste the output of the LLM into the code.

The usage of AI coding tools can lead to *software necrosis* and *atrophy of software development skills*.
Any design decisions should be done by a human and you should be able to explain line-by-line how the code works.

Please understand that by opening low-quality pull requests you're not helping anyone.
Worse, you're [poisoning the open source ecosystem](https://lwn.net/Articles/1058266/) that was precarious even before the arrival of LLM tools.
Having to wade through plausible-looking-but-low-quality pull requests and trying to determine which ones are legit is extremely demoralizing and has already burned out many good maintainers.

Put bluntly, we have no time or interest to become part of your vibe coding loop where you drop LLM slop at our door, we spend time and energy to review it, and you just feed it back into the LLM for another iteration.

This dynamic is especially pernicious because it poisons the well for mentoring new contributors which we are committed to.


## Summary

In practice, this means:

- Pull requests that have an LLM product listed as co-author can't be merged and will be closed without further discussion.
  We cannot risk the copyright status of this project.

  If you used LLM tools during development, you may still submit – but you must remove any LLM co-author tags and take full ownership of every line.

- By submitting a pull request, **you** take full **technical and legal** responsibility for the contents of the pull request and promise that **you** hold the copyright for the changes submitted.

  "An LLM wrote it" is **not** an acceptable response to questions or critique.
  **If you cannot explain and defend the changes you submit, do not submit them** and open a high-quality bug report/feature request instead.

- Accounts that exercise bot-like behavior – like automated mass pull requests – will be permanently banned, whether they belong to a human or not.

- Do **not** post LLM-generated review comments – we can prompt LLMs ourselves should we desire their wisdom.
  Do **not** post summaries unless you've fact-checked them and take responsibility for 100% of their content.
  Remember that *all* LLM output *looks* **plausible**.
  When using these tools, it's **your** responsibility to ensure that it's also **correct** and has a reasonable signal-to-noise ratio.

[attrs-policy]: https://github.com/python-attrs/attrs/blob/main/.github/AI_POLICY.md
