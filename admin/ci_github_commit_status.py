"""
Helper to send commit status from CI.

It uses the OAUTH_TOKEN environment variables for pushing to GitHub.

For more details see:
https://developer.github.com/v3/repos/statuses/#create-a-status
"""
from __future__ import print_function
import os
import sys

from twisted.python import usage
from twisted.internet.task import react

from txgithub.api import GithubApi


# Some placeholder to mark a parameter as required.
required = object()



class Options(usage.Options):
    optParameters = [
        ['commit', None, required,
            'SHA of the commit for which the status is updated.'],
        ['state', None, required,
            'The state of the status. '
            'Can be one of pending, success, error, or failure.'],
        ['state', None, required,
            'The state of the status. '
            'Can be one of pending, success, error, or failure.'],
        ['target-url', None, required,
            'The URL to associate with this status.'],
        ['description', None, required,
            'A short description of the status.'],
        ['context', None, required,
            'A string label to differentiate this status from the status of '
            'other systems'],
        ]



def postStatus(reactor, options):
    """
    Send the commit status to GitHub, if we have an OAUTH_TOKEN.
    """
    token = os.environ.get('OAUTH_TOKEN', None)

    if not token:
        print('No OAUTH_TOKEN env var defined. Status update ignored.')
        sys.exit(0)

    for key, value in options.items():
        if value is required:
            print('Error: --%s parameter is required.' % (key,))
            sys.exit(1)

    api = GithubApi(token)

    deferred = api.repos.createStatus(
        repo_user='twisted',
        repo_name='twisted',
        sha=options['commit'],
        state=options['state'],
        target_url=options['target-url'],
        description=options['description'],
        context=options['context'],
        )

    def cb_success(result):
        print('Status successfully updated as "%s" for "%s"' % (
            options['state'], options['commit']))

    def eb_failure(failure):
        error = failure.value
        print("%s\n%s" % (failure.getErrorMessage(), error.response))
        sys.exit(1)

    deferred.addCallback(cb_success)
    deferred.addErrback(eb_failure)
    return deferred



def run(reactor, *argv):
    options = Options()
    try:
        options.parseOptions(argv[1:])
    except usage.UsageError as error:
        print(error)
        print('Try --help for usage details.')
        sys.exit(1)

    return postStatus(reactor, options)



react(run, sys.argv)
