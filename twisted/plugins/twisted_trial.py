from twisted.trial import reporter


_Plugin = reporter.TrialReporterPlugin

Tree = _Plugin('verbose', reporter.TreeReporter)

BlackAndWhite = _Plugin('bwverbose', reporter.VerboseTextReporter)

Minimal = _Plugin('summary', reporter.MinimalReporter)

Classic = _Plugin("text", reporter.TextReporter)

Timing = _Plugin('timing', reporter.TimingTextReporter)

