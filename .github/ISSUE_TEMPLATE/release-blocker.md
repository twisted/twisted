---
name: Release blocker
about: An issue with critical priority that should be considered before the next release
title: ''
labels: ["bug", "release-blocker"]
assignees: 'adiroiban'

---

<!-- Most bugs should not block the release. -->
**Why should this block the release?**

- [ ] This is a regression from the **most recently released** previous version.
- [ ] Tests on trunk are currently failing.
- [ ] There is a high priority security fix that should be included.

<!-- If it is a regression from a previous version, please include information about what version that was, and whether you've tested everything on the exact same platform. -->

**Describe the incorrect behavior you saw**
<!-- Describe what's wrong with the bug. -->

**Describe how to cause this behavior**

<!-- What did you do to get it to happen? -->

<!-- Does it happen every time you follow these steps, sometimes, or only one time? -->

<!-- If you have a traceback, please paste it here; otherwise, delete this. -->

```

```

<!-- Preferable a [Short, Self Contained, Correct (Compilable), Example](http://www.sscce.org/) on a branch or on [a gist](https://gist.github.com). -->

<!-- Automated tests that are demonstrating the failure would be awesome. -->

**Describe the correct behavior you'd like to see**

<!-- A clear and concise description of what you expected to happen, or what you believe should be happening instead. -->

**Testing environment**

<!-- output of

git rev-parse HEAD
twist --version
-->
Twisted Version:
```

```

<!--
- Operating System and Version; paste the output of these commands:

Linux:

uname -a ; cat /etc/lsb-release

Windows:

systeminfo | Findstr /i "OS"

macOS:

sw_vers

-->

Operating System Version:
```

```

<!--

python -V

-->
Python Version:
```

```

<!--

pip freeze

-->
Installed Dependencies:
```

```

**Additional context**

<!-- Add any other context about the problem here. -->


