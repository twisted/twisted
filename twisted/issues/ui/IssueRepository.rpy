# IssueRepository.rpy

import webrepo
reload(webrepo)
import twisted
resource = twisted.web.woven.view.View( webrepo.MIssueRepository(
    registry.getComponent(twisted.issues.repo.IssueRepository)
    ), "webrepo_template.html")
