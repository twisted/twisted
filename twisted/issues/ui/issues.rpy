# issues.rpy
import twisted
from twisted.issues.ui import webrepo
from twisted.python import util
reload(webrepo)
import os
resource = webrepo.IssueSite(
    registry.getComponent(twisted.issues.repo.IssueRepository),
    registry.getComponent(twisted.words.service.Service),
    util.sibpath(__file__, "templates"))
