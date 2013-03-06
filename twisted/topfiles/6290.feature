twisted.application.internet.TimerService.stopService now waits for
any currently running call to finish before firing its deferred.
