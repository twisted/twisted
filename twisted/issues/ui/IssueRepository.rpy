# IssueRepository.rpy

import webrepo
reload(webrepo)
import twisted
resource = webrepo.MIssueRepository(
    registry.getComponent(twisted.issues.repo.IssueRepository)
    )
