//
//  bin-python-main.m
//  cocoaDemo
//
//  Created by Bob Ippolito on Fri Jan 17 2003.
//  Copyright (c) 2003 __MyCompanyName__. All rights reserved.
//

/*
 This main file uses execve() to transfer control of execution to the standard command line python interpreter.   As such, compiled classes in the project will not actually be linked into the runtime as execve() effectively overlays the existing process with the process being called -- in this case the python command line tool.

 To use compiled classes with this main, create a separate bundle target and load the bundle in the main python file.  The main python file should be in Resources and should be named "__main__.py", "__realmain__.py" or "Main.py".

 This style of execution works with the Apple provided version of Python.
 */

#import <Foundation/Foundation.h>
#import <sys/param.h>
#import <unistd.h>

int pyobjc_main(int argc, char * const *argv, char * const *envp)
{
    // The autorelease pool is not released on purpose.   The call to execve() destroys the
    // calling process entirely and, as such, memory management in the traditional sense
    // is not necessary (and not doing so avoids potential bugs associated with releasing
    // the pool prior to the call to execve).
    [[NSAutoreleasePool alloc] init];

    const char **childArgv = alloca(sizeof(char *) * (argc + 5));
    NSEnumerator *bundleEnumerator = [[NSBundle allFrameworks] reverseObjectEnumerator];
    NSBundle *aBundle;
    NSBundle *mainBundle = [NSBundle mainBundle];
    NSMutableArray *bundlePaths = [NSMutableArray array];
    int i;
    int envc;
    char** childEnvp;
    char*  PYTHONPATH = NULL;

    // set up paths to be prepended to the PYTHONPATH
    const char *pythonPathInWrapper = [[NSString stringWithFormat: @"%@:%@",
        [[NSBundle mainBundle] resourcePath],
        [[[NSBundle mainBundle] resourcePath] stringByAppendingPathComponent: @"pyobjc"]] UTF8String];

    // count entries in environment and find the PYTHONPATH setting, if present
    for (envc = 0; envp[envc] != NULL; envc++) {
        if (strncmp(envp[envc], "PYTHONPATH=", sizeof("PYTHONPATH=")-1) == 0) {
            PYTHONPATH=envp[envc] + sizeof("PYTHONPATH=") - 1;
            /* No break, we also want to know how large envp is */
        }
    }

    // copy the environment into a new array that will eventually also contain the PYTHONPATH
    childEnvp = alloca(sizeof(char*) * (envc + 10)); // enough for both PYTHONPATH and the DYLD stuff
    for (envc = 0; envp[envc] != NULL; envc ++) {
        if (strncmp(envp[envc], "PYTHONPATH=", sizeof("PYTHONPATH=")-1) == 0) {
            // already exisxts, prepend app wrapper paths
            NSString *envValue = [NSString stringWithFormat: @"PYTHONPATH=%s:%s", pythonPathInWrapper, PYTHONPATH];
            childEnvp[envc] = (char *)[envValue UTF8String];
        } else {
            childEnvp[envc] = envp[envc];
        }
    }
    if (PYTHONPATH) {
        // already set in for() loop above
        childEnvp[envc] = NULL;
    } else {
        // wasn't set -- add PYTHONPATH to child
        NSString *envValue = [NSString stringWithFormat: @"PYTHONPATH=%s", pythonPathInWrapper];
        childEnvp[envc] = (char *)[envValue UTF8String];
        envc++;
        childEnvp[envc] = NULL;
    }

    // if this is set, it is most likely because of PBX or because the developer is doing something....
    if ( !getenv("DYLD_FRAMEWORK_PATH") ) {
        // if not, put the DYLD environment into a state where we can actually load frameworks from within the app
        // wrapper where the frameworks may have inter-dependencies.
        NSArray *paths = [NSArray arrayWithObjects: [mainBundle sharedFrameworksPath], [mainBundle privateFrameworksPath], nil];
        NSString *joinedPaths = [paths componentsJoinedByString: @":"];
        const char *dyldFrameworkPath = [[NSString stringWithFormat: @"DYLD_FRAMEWORK_PATH=%@", joinedPaths] UTF8String];
        const char *dyldLibraryPath = [[NSString stringWithFormat: @"DYLD_LIBRARY_PATH=%@", joinedPaths] UTF8String];

        childEnvp[envc++] = (char *)dyldFrameworkPath;
        childEnvp[envc++] = (char *)dyldLibraryPath;

        // useful for debugging-- set this as a default.
        if ([[NSUserDefaults standardUserDefaults] boolForKey: @"DYLD_PRINT_LIBRARIES"])
            childEnvp[envc++] = (char *)"DYLD_PRINT_LIBRARIES=1";
        childEnvp[envc++] = NULL;
    }

    // grab a list of all frameworks that were linked into this executable
    while ( aBundle = [bundleEnumerator nextObject] ) {
        if ( [[[aBundle bundlePath] pathExtension] isEqualToString: @"framework"] )
            [bundlePaths addObject: [aBundle bundlePath]];
    }

    // set an environment variable to contain the linked frameworks
    childEnvp[envc++] = (char*)[[NSString stringWithFormat: @"PYOBJCFRAMEWORKS=%@", [bundlePaths componentsJoinedByString: @":"]] UTF8String];
    childEnvp[envc++] = NULL;

    // figure out which python interpreter to use
    NSString *pythonBinPath = [[NSUserDefaults standardUserDefaults] stringForKey: @"PythonBinPath"];
    pythonBinPath = pythonBinPath ? pythonBinPath : @"/usr/bin/python";

    const char *pythonBinPathPtr = [pythonBinPath UTF8String];

    // find main python file.  __main__.py seems to be a standard.
    NSArray *possibleMains = [NSArray arrayWithObjects:
        @"__main__.py",
        @"__main__.pyc",
        @"__main__.pyo",
        @"__realmain__.py",
        @"__realmain__.pyc",
        @"__realmain__.pyo",
        @"Main.py",
        @"Main.pyc",
        @"Main.pyo",
        nil];
    NSEnumerator *possibleMainsEnumerator = [possibleMains objectEnumerator];
    NSString *mainPyPath;
    NSString *nextFileName;

    while (nextFileName = [possibleMainsEnumerator nextObject]) {
        mainPyPath = [mainBundle pathForResource: nextFileName ofType: nil];
        if ( mainPyPath )
            break;
    }

    if ( !mainPyPath )
        [NSException raise: NSInternalInconsistencyException
                    format: @"%s:%d pyobjc_main() Failed to find one of %@ in app wrapper.  Exiting.", __FILE__, __LINE__, possibleMains];
    const char *mainPyPathPtr = [mainPyPath UTF8String];

    // construct argv for the child

    // the path to the executable in the app wrapper -- must be in the app wrapper or CFBundle does not initialize correctly
    childArgv[0] = argv[0];

    // path to the python file that acts as the main entry point
    childArgv[1] = mainPyPathPtr;

    // Pass original arguments (such as -NSOpen) verbatum
    //
    // Move each argument right one slot
    for (i = 1; i<argc; i++)
        childArgv[i+1] = argv[i];
    i++; // compensate for i+1 in for() loop

    // terminate the arg list
    childArgv[i++] = NULL;

    // print a nice debugging helper message, if desired
    if ([[[NSProcessInfo processInfo] environment] objectForKey: @"SHOWPID"])
        NSLog(@"Process ID is: %d (\n\tgdb %s %d\n to debug)", getpid(), pythonBinPathPtr, getpid());

    // pass control to the python interpreter
    if (execve(pythonBinPathPtr, (char **)childArgv, childEnvp) == -1)
        perror("execve");
    return 1;
}

int main(int argc, char * const *argv, char * const *envp)
{
    return pyobjc_main(argc, argv, envp);
}
