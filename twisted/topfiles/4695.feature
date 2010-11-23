twisted.internet.endpoints.serverFromString and clientFromString, and therefore
also twisted.application.strports.service, now support plugins, so third
parties may implement their own endpoint types.
