#include "Python.h"
#include <stdio.h>
#include <stdlib.h>
#include <Windows.h>

/*
   A simple front-end for running a python file using an explicit version of
   python. Needed on Windows because "running" a .py file will always use the
   system-default Python, which is not always desirable.  See ticket #2381.

   This file is meant to be compiled and then renamed to match the name of
   the script you want to run. E.g. rename it to trial.exe to run trial.py
   existing in the same directory.

   build_exes.py should automate creating the necessary file for each
   Twisted command. It is meant to be used with MingW.
*/

static char scriptPath[_MAX_PATH]; // _MAX_PATH comes from stdlib.h
static char scriptExt[] = "py";
static char exeName[] = "\\python.exe";

int main(int argc, char** argv) {
	char** new_argv;
	int i, len;
	FILE* fp;
	PyObject* sys;
	char* interpreterPath;
	char* exec_prefix;
	PyObject* py_interpreterPath;

	// get the path to this process' exe module
	GetModuleFileName(NULL, scriptPath, sizeof(scriptPath));
	len = strlen(scriptPath);

	// copy "py" over "exe" and null-terminate
	strcpy(scriptPath+len-3, scriptExt);

	if ((new_argv = malloc( (argc+1) * sizeof(char*) )) == NULL) {
		printf("Can't allocate memory\n");
		exit(1);
	}

	new_argv[0] = scriptPath; // insert the script file to run

	for (i=1; i<argc; i++) { // now copy the remaining arguments
		new_argv[i] = argv[i];
	}
	new_argv[argc] = NULL; // ensure that new_argv is NULL terminated

	Py_Initialize();
	PySys_SetArgv(argc, new_argv);

	// figure out path to python.exe
	exec_prefix = Py_GetExecPrefix();
	if ((interpreterPath = malloc(strlen(exec_prefix) + strlen(exeName) + 1)) == NULL) {
		printf("Can't allocate memory\n");
		exit(1);
	}
	strcpy(interpreterPath, exec_prefix);
	strcat(interpreterPath, exeName);

	// make a Python string out of it
	if ((py_interpreterPath = PyString_FromString(interpreterPath)) == NULL) {
		PyErr_Print();
		exit(1);
	}

	// don't need the C string anymore
	free(interpreterPath);

	// import sys
	if ((sys = PyImport_ImportModule("sys")) == NULL) { // import sys
		PyErr_Print();
		exit(1);
	}

	// set sys.executable to what some people tend to expect :(
	if (PyObject_SetAttrString(sys, "executable", py_interpreterPath) == -1) {
		PyErr_Print();
		exit(1);
	}

	if ((fp = fopen(scriptPath, "r")) == NULL) {
		perror("Error opening script");
		printf("Script path: %s\n", scriptPath);
		exit(1);
	}

        return PyRun_AnyFile(fp, scriptPath);
}


