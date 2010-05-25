FilePath now calls os.stat() only when new status information is required,
rather than immediately when anything changes.  For some applications this may
result in fewer stat() calls.  Additionally, FilePath has a new method,
'changed', which applications may use to indicate that the FilePath may have
been changed on disk and therefore the next status information request must 
fetch a new stat result.  This is useful if external systems, such as C
libraries, may have changed files that Twisted applications are referencing via
a FilePath.