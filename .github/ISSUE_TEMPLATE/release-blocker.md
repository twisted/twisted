---
name: Release blocker
about: An issue with critical priority that should be considered before the next release
title: ''
labels: ["bug", "release-blocker"]
assignees: 'adiroiban'

---

Report any issue that should block the next release.
This should follow the same process are reporting a bug, the only difference is that it will get higher priority.


**Describe the incorrect behavior you saw**
A clear and concise description of what the bug is and why the release should be blocked unless this defect is fixed.

**Describe how to cause this behavior**

What did you do to get it to happen?
Does it happen every time you follow these steps, sometimes, or only one time?

```
If you have a traceback, please paste it here; otherwise, delete this.
```


Preferable a [Short, Self Contained, Correct (Compilable), Example](http://www.sscce.org/) on a branch or on [a gist](https://gist.github.com).

Automated tests that are demonstrating the failure would be awesome.

**Describe the correct behavior you'd like to see**
A clear and concise description of what you expected to happen, or what you believe should be happening instead.

**Testing environment**
 - Operating System and Version; paste the output of these commands:
   - on Linux, `uname -a ; cat /etc/lsb-release`
   - on Windows, `systeminfo | Findstr /i "OS"`
   - on macOS, `sw_vers`
 - Twisted version [e.g. 22.2.0]
   - please paste the output of `twist --version` and `pip --freeze`
 - Reactor [e.g. select, iocp]


**Additional context**
Add any other context about the problem here.
