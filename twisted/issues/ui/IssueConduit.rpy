# WebConduit.rpy

import issueconduit
import twisted
#from twisted.python import rebuild
#rebuild.rebuild(issueconduit)
resource = issueconduit.MWebConduit(
    registry.getComponent(twisted.words.service.Service),
    registry.getComponent(twisted.issues.repo.IssueRepository)
    )
