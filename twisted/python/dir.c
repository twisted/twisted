/*
 * Twisted, the Framework of Your Internet
 * Copyright (C) 2001-2002 Matthew W. Lefkowitz
 * 
 * This library is free software; you can redistribute it and/or
 * modify it under the terms of version 2.1 of the GNU Lesser General Public
 * License as published by the Free Software Foundation.
 * 
 * This library is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * Lesser General Public License for more details.
 * 
 * You should have received a copy of the GNU Lesser General Public
 * License along with this library; if not, write to the Free Software
 * Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
 * 
 */

#include "Python.h"
#include "structmember.h"

static char dir__doc__[] =
"Wrapper for opendir(3) and related functions.";

/* We link this module statically for convenience.  If compiled as a shared
   library instead, some compilers don't allow addresses of Python objects
   defined in other libraries to be used in static initializers here.  The
   DEFERRED_ADDRESS macro is used to tag the slots where such addresses
   appear; the module init function must fill in the tagged slots at runtime.
   The argument is for documentation -- the macro ignores it.
*/
#define DEFERRED_ADDRESS(ADDR) 0

#include <sys/types.h>
#include <sys/stat.h>
#include <dirent.h>
#include <string.h>

static PyObject *PyDirObject_Error;

/*
 * Raa Raa Forward Decls
 */
typedef struct _PyDirObject {
	PyObject_HEAD
	DIR* directory;
} PyDirObject;

typedef struct _PyDirObjectIterator {
	PyObject_HEAD
	PyDirObject *dirobj;
	PyObject *filter;
} PyDirObjectIterator;

static PyObject *
PyDirObject_readdir(PyDirObject *self);

staticforward PyTypeObject PyDirObjectIterator_Type;
staticforward PyTypeObject PyDirObject_Type;

char ospathsep;
char* pardir;
char* curdir;

typedef int (*select_func)(const char *, const char *, int);

#define PyDirObject_Check(o) (PyObject_TypeCheck((o), &PyDirObject_Type))
#define PyDirObject_CheckExact(o) ((o)->ob_type == &PyDirObject_Type)

/*
 **************************** PyDirObjectIterator ***************************
 */


static PyObject *
PyDirObjectIterator_FromDirObjectAndCallable(PyDirObject* dirobj, PyObject* callable) {
	PyDirObjectIterator *o;

	o = (PyDirObjectIterator *)PyObject_New(PyDirObjectIterator, &PyDirObjectIterator_Type);
	if (o == NULL)
		return NULL;
	
	Py_INCREF(dirobj);
	o->dirobj = dirobj;
	
	Py_INCREF(callable);
	o->filter = callable;
	
	return (PyObject *)o;
}

static PyObject *
PyDirObjectIterator_new(PyDirObjectIterator *self, PyObject* args) {
	PyDirObject *dirobj;
	PyObject *filter;

	if (!PyArg_ParseTuple(args, "OO:DirObjectIterator", &dirobj, &filter))
		return NULL;
	
	if (!PyDirObject_Check(dirobj)) {
		PyErr_SetString(PyExc_TypeError,
			"First argument must be DirObject instance");
		return NULL;
	}
	
	return PyDirObjectIterator_FromDirObjectAndCallable(dirobj, filter);
}

static void
PyDirObjectIterator_free(PyDirObjectIterator *self) {
	Py_DECREF(self->dirobj);
	Py_DECREF(self->filter);
	PyObject_Del(self);
}

static PyObject *
PyDirObjectIterator_iter(PyDirObjectIterator *self) {
	Py_INCREF(self);
	return (PyObject *)self;
}

static PyObject *
PyDirObjectIterator_next(PyDirObjectIterator *self) {
   PyObject *ent;
	PyObject *args;
	PyObject *result;
	
	if (self->filter == Py_None)
		return PyDirObject_readdir(self->dirobj);
	
	while (1) {
		if ((ent = PyDirObject_readdir(self->dirobj)) == NULL)
			return NULL;
		
		args = PyTuple_New(1);
		Py_INCREF(ent);
		PyTuple_SetItem(args, 0, ent);
		result = PyObject_CallObject(self->filter, args);
		Py_DECREF(args);
		
		if (result == NULL) {
			Py_DECREF(ent);
			return NULL;
		}

		if (PyObject_IsTrue(result)) {
			Py_DECREF(result);
			return (PyObject *)ent;
		}
		Py_DECREF(ent);
	}
}

static PyTypeObject PyDirObjectIterator_Type = {
	PyObject_HEAD_INIT(DEFERRED_ADDRESS(&PyType_Type))
	0,
	"dir.DirIteratorType",
	sizeof(PyDirObjectIterator),
	0,
	0,							/* tp_dealloc */
	0,							/* tp_print */
	0,							/* tp_getattr */
	0,							/* tp_setattr */
	0,							/* tp_compare */
	0,							/* tp_repr */
	0,							/* tp_as_number */
	0,							/* tp_as_sequence */
	0,							/* tp_as_mapping */
	0,							/* tp_hash */
	0,							/* tp_call */
	0,							/* tp_str */
	0,							/* tp_getattro */
	0,							/* tp_setattro */
	0,							/* tp_as_buffer */
	Py_TPFLAGS_DEFAULT,	/* tp_flags */
	0,							/* tp_doc */
	0,							/* tp_traverse */
	0,							/* tp_clear */
	0,							/* tp_richcompare */
	0,							/* tp_weaklistoffset */
	(getiterfunc)PyDirObjectIterator_iter,		/* tp_iter */
	(iternextfunc)PyDirObjectIterator_next,	/* tp_iternext */
	0,							/* tp_methods */
	0,							/* tp_members */
	0,							/* tp_getset */
	0,							/* tp_base */
	0,							/* tp_dict */
	0,							/* tp_descr_get */
	0,							/* tp_descr_set */
	0,							/* tp_dictoffset */
	0,							/* tp_init */
	0,							/* tp_alloc */
	(newfunc)PyDirObjectIterator_new,		/* tp_new */
	(destructor)PyDirObjectIterator_free,	/* tp_free */
};

/*
 ******************************* PyDirObject ********************************
 */

static PyObject *
PyDirObject_FromDIR(DIR* directory)
{
	PyDirObject *self;
	if ((self = (PyDirObject *)PyObject_New(PyDirObject, &PyDirObject_Type)) == NULL)
		return NULL;
	
	self->directory = directory;
	return (PyObject *)self;
}

static PyObject *
PyDirObject_new(PyDirObject *self, PyObject *args)
{
   char* name = NULL;
   DIR* directory;

	if (!PyArg_ParseTuple(args, "s:DirObject", &name))
		return NULL;
	
	if ((directory = opendir(name)) == NULL) {
		PyErr_SetFromErrno(PyDirObject_Error);
		return NULL;
	}
	
	return PyDirObject_FromDIR(directory);
}

static void
PyDirObject_free(PyDirObject *self) {
	if (self->directory) {
		if (closedir(self->directory) == -1) {
			PyErr_SetFromErrno(PyDirObject_Error);
			PyErr_Print();
		}
	}
	PyObject_Del(self);
}

static PyObject *
PyDirObject_iter(PyDirObject *self) {
	return PyDirObjectIterator_FromDirObjectAndCallable(self, Py_None);
}

static PyObject *
PyDirObject_scan(PyDirObject *self, PyObject* args) {
	PyObject *func;
	
	if (!PyArg_ParseTuple(args, "O:scan", &func))
		return NULL;
	
	return PyDirObjectIterator_FromDirObjectAndCallable(self, func);
}

static PyObject *
PyDirObject_readdir(PyDirObject *self)
{
	int lasterrno = 0;
	struct dirent* next;
	PyObject *ret;
	
	PyObject *element;
	PyObject *type;
	
	if (!self->directory) {
		PyErr_SetString(PyDirObject_Error,
			"Iteration on closed DirObject");
		return NULL;
	}
	
	lasterrno = errno;
	errno = 0;
	if ((next = readdir(self->directory)) == NULL) {
		if (errno == 0) {
			PyErr_Clear();
			return NULL;
		}
		PyErr_SetFromErrno(PyDirObject_Error);
		errno = lasterrno;
		return NULL;
	}
	if (!(ret = PyTuple_New(2)))
		goto tuple_error;
	if (!(element = PyString_FromString(next->d_name)))
		goto name_error;
	if (!(type = PyInt_FromLong(next->d_type)))
		goto type_error;
   
	if (PyTuple_SetItem(ret, 0, element) < 0)
		goto setitem_error;
	if (PyTuple_SetItem(ret, 1, type) < 0)
		goto setitem_error;
	return ret;
	
	setitem_error:
		Py_DECREF(type);
	type_error:
		Py_DECREF(element);
	name_error:
		Py_DECREF(ret);
	tuple_error:
		return NULL;
}

static PyObject *
PyDirObject_tell(PyDirObject *self) {
	long result;
	
	if (!self->directory) {
		PyErr_SetString(PyDirObject_Error,
			"DirObject.tell() called on closed DirObject");
		return NULL;
	}
	
	if ((result = telldir(self->directory)) == -1) {
		PyErr_SetFromErrno(PyDirObject_Error);
		return NULL;
	}
	
	return PyLong_FromLong(result);
}

static PyObject *
PyDirObject_rewind(PyDirObject *self) {
	if (!self->directory) {
		PyErr_SetString(PyDirObject_Error,
			"DirObject.rewind() called on closed DirObject");
			return NULL;
	}
	rewinddir(self->directory);

	Py_INCREF(Py_None);
	return Py_None;
}

static PyObject *
PyDirObject_seek(PyDirObject *self, PyObject* args) {
	long pos;
	
	if (!PyArg_ParseTuple(args, "l:seek", &pos))
		return NULL;
	
	if (!self->directory) {
		PyErr_SetString(PyDirObject_Error,
			"DirObject.seek() called on closed DirObject");
		return NULL;
	}
	seekdir(self->directory, pos);
	
	Py_INCREF(Py_None);
	return Py_None;
}

static PyObject *
PyDirObject_close(PyDirObject *self)
{
	if (!self->directory) {
		PyErr_SetString(PyDirObject_Error,
			"DirObject.close() called on closed DirObject");
		return NULL;
	}
	
	if (closedir(self->directory) == -1) {
		PyErr_SetFromErrno(PyDirObject_Error);
		return NULL;
	}
	
	self->directory = NULL;

	Py_INCREF(Py_None);
	return Py_None;
}

static char PyDirObject_rewind_doc[] =
	"Seek to the beginning of this directory.";

static char PyDirObject_tell_doc[] =
	"Return an opaque handle for use by DirType.seek()\n"
	"\n"
	"The object returned is valid for one use only, and only for\n"
	"use by this DirType instance.\n";

static char PyDirObject_seek_doc[] =
	"Return to a previous position in the directory.\n"
	"\n"
	"The argument passed must have been returned by a call to this\n"
	"instances' tell() method, and must not have been passed to\n"
	"seek() before.  After this call returns, the argument may not\n"
	"be passed to this method again.\n";

static char PyDirObject_scan_doc[] =
	"Create an iterator for the contents of this directory.\n"
	"\n"
	"The elements created by the returned iterator will be two-tuples\n"
	"of file name (str) and file type (int).  If an argument is provided,\n"
	"it is called for each element with the file name and file type, and\n"
	"that element is only produced by the iterator if the call returns a\n"
	"true value.\n";

static char PyDirObject_close_doc[] =
	"Close this directory.\n";

static PyMethodDef PyDirObject_methods[] = {
	{"rewind", (PyCFunction)PyDirObject_rewind, METH_NOARGS, PyDirObject_rewind_doc},
	{"tell", (PyCFunction)PyDirObject_tell, METH_NOARGS, PyDirObject_tell_doc},
	{"seek", (PyCFunction)PyDirObject_seek, METH_VARARGS, PyDirObject_seek_doc},
	{"scan", (PyCFunction)PyDirObject_scan, METH_VARARGS, PyDirObject_scan_doc},
	{"close", (PyCFunction)PyDirObject_close, METH_NOARGS, PyDirObject_close_doc},
	{NULL,	NULL},
};

static PyTypeObject PyDirObject_Type = {
	PyObject_HEAD_INIT(DEFERRED_ADDRESS(&PyType_Type))
	0,
	"dir.DirType",
	sizeof(PyDirObject),
	0,
	0,							/* tp_dealloc */
	0,							/* tp_print */
	0,							/* tp_getattr */
	0,							/* tp_setattr */
	0,							/* tp_compare */
	0,							/* tp_repr */
	0,							/* tp_as_number */
	0,							/* tp_as_sequence */
	0,							/* tp_as_mapping */
	0,							/* tp_hash */
	0,							/* tp_call */
	0,							/* tp_str */
	0,							/* tp_getattro */
	0,							/* tp_setattro */
	0,							/* tp_as_buffer */
	Py_TPFLAGS_DEFAULT, 	/* tp_flags */
	0,							/* tp_doc */
	0,							/* tp_traverse */
	0,							/* tp_clear */
	0,							/* tp_richcompare */
	0,							/* tp_weaklistoffset */
	(getiterfunc)PyDirObject_iter,	/* tp_iter */
	0,							/* tp_iternext */
	PyDirObject_methods,	/* tp_methods */
	0,							/* tp_members */
	0,							/* tp_getset */
	0,							/* tp_base */
	0,							/* tp_dict */
	0,							/* tp_descr_get */
	0,							/* tp_descr_set */
	0,							/* tp_dictoffset */
	0,							/* tp_init */
	0,							/* tp_alloc */
	(newfunc)PyDirObject_new,		/* tp_new */
	(destructor)PyDirObject_free,		/* tp_free */
};

#ifndef PyBool_FromLong
#define PyBool_FromLong(o) PyInt_FromLong(o)
#endif

#define DEFINE(name, const)                                                 \
static PyObject *                                                           \
dir_is##name(PyObject *self, PyObject *args) {                              \
	PyObject *tup;                                                           \
	if (!PyArg_ParseTuple(args, "O", &tup))                                  \
		return NULL;                                                          \
	return PyBool_FromLong(PyInt_AsLong(PyTuple_GetItem(self, 1)) == const); \
}

DEFINE(Fifo, DT_FIFO)
DEFINE(CharDevice, DT_CHR)
DEFINE(BlockDevice, DT_BLK)
DEFINE(Directory, DT_DIR)
DEFINE(RegularFile, DT_REG)
DEFINE(SymbolicLink, DT_LNK)
DEFINE(Socket, DT_SOCK)
DEFINE(Whiteout, DT_WHT)

#undef DEFINE

int select_dirs(const char* path, const char* name, int type) {
	if (type == DT_DIR) {
		if (strcmp(name, curdir) && strcmp(name, pardir))
			return 1;
	} else if (type == DT_LNK) {
		struct stat m;
		char buf[1024];
		int ret;

		ret = snprintf(&buf[0], 1024, "%s%c%s", path, ospathsep, name);
		if (ret < 0 || ret > 1024) {
			perror("select_dirs(): snprintf");
			return 0;
		} 

		if (stat(buf, &m) < 0) {
			perror("select_dirs(): stat");
			return 0;
		}
		return (m.st_mode & S_IFDIR) == S_IFDIR;
	}
	return 0;
}

int select_links(const char *path, const char *name, int type) {
	return type == DT_LNK;
}

#if defined(__FreeBSD__)
/* FreeBSD doesn't want a const on this. */
int select_all(struct dirent* ent) {
#else
int select_all(const struct dirent* ent) {
#endif
	return 1;
}


static PyObject *
dir_list(PyObject *self, PyObject *args, select_func select) {
	int ret;
	int i, j;
	char *path;
	PyObject *list;
	PyObject *empty;
	PyObject *ent;
	struct dirent **ents;
	
	if (!PyArg_ParseTuple(args, "s", &path))
		return NULL;
	
	
	ret = scandir(path, &ents, select_all, NULL);
	if (ret == -1) {
		PyErr_SetFromErrno(PyDirObject_Error);
		return NULL;
	}
	
	if (!(list = PyList_New(ret)))
		return NULL;

	j = 0;
	for (i = 0; i < ret; ++i) {
		if (select(path, ents[i]->d_name, ents[i]->d_type)) {
			if (!(ent = PyString_FromString(ents[i]->d_name))) {
				Py_DECREF(list);
				return NULL;
			}
			if (PyList_SetItem(list, j, ent) < 0) {
				Py_DECREF(list);
				return NULL;
			}
			++j;
			free(ents[i]);
		}
	}
	free(ents);
	for (i = j ; i < ret; ++i) {
		Py_INCREF(Py_None);
		if (PyList_SetItem(list, i, Py_None) < 0) {
	    	Py_DECREF(list);
			return NULL;
		}
	}
	if (!(empty = PyList_New(0))) {
		Py_DECREF(list);
		return NULL;
	}
	
	if (PyList_SetSlice(list, j, i, empty) < 0) {
		Py_DECREF(list);
		Py_DECREF(empty);
		return NULL;
	}
	return list;
}

static PyObject *
dir_listDirectories(PyObject *self, PyObject *args) {
	return dir_list(self, args, select_dirs);
}

static PyObject *
dir_listLinks(PyObject *self, PyObject *args) {
	return dir_list(self, args, select_links);
}

static PyMethodDef dir_functions[] = {
	{"isFifo", (PyCFunction)dir_isFifo, METH_VARARGS,
		"isFifo() -> True if this entry is of FIFO type"},
	{"isCharDevice", (PyCFunction)dir_isCharDevice, METH_VARARGS,
		"isCharDevice() -> True if this entry is of CHR type"},
	{"isBlockDevice", (PyCFunction)dir_isBlockDevice, METH_VARARGS,
		"isBlockDevice() -> True if this entry is of BLK type"},
	{"isDirectory", (PyCFunction)dir_isDirectory, METH_VARARGS,
		"isDirectory() -> True if this entry is of DIR type"},
	{"isRegularFile", (PyCFunction)dir_isRegularFile, METH_VARARGS,
		"isRegularFile() -> True if this entry is of REG type"},
	{"isSymbolicLink", (PyCFunction)dir_isSymbolicLink, METH_VARARGS,
		"isSymbolicLink() -> True if this entry is of SYM type"},
	{"isSocket", (PyCFunction)dir_isSocket, METH_VARARGS,
		"isSocket() -> True if this entry is of SOCK type"},
	{"isWhiteout", (PyCFunction)dir_isWhiteout, METH_VARARGS,
		"isWhiteout() -> True if this entry is of WHT type"},

	{"listDirectories", (PyCFunction)dir_listDirectories, METH_VARARGS,
		"listDirectories(path) -> List the directories in the given path"},
	{"listLinks", (PyCFunction)dir_listLinks, METH_VARARGS,
		"listLinks(path) -> List the links in the given path"},
	{NULL, NULL},
};

DL_EXPORT(void)
initdir(void)
{
	PyObject *m, *d;
	PyObject *os, *sep;
	PyObject *cur, *par;
	char *pathsep;
	

	PyDirObject_Error = PyErr_NewException("dir.error", PyDirObject_Error, NULL);
	if (PyDirObject_Error == NULL)
		return;

	if (PyType_Ready(&PyDirObject_Type) < 0)
		return;

	if (PyType_Ready(&PyDirObjectIterator_Type) < 0)
		return;

	m = Py_InitModule3("dir", dir_functions, dir__doc__);
	if (m == NULL)
		return;

	d = PyModule_GetDict(m);
	if (d == NULL)
		return;

	Py_INCREF(PyDirObject_Error);
	if (PyDict_SetItemString(d, "DirError", PyDirObject_Error) < 0)
		return;

	Py_INCREF(&PyDirObject_Type);
	if (PyDict_SetItemString(d, "DirType",
				 (PyObject *) &PyDirObject_Type) < 0)
		return;

	Py_INCREF(&PyDirObjectIterator_Type);
	if (PyDict_SetItemString(d, "DirIteratorType",
				 (PyObject *) &PyDirObjectIterator_Type) < 0)
		return;
	
	if (!(os = PyImport_ImportModule("os")))
		return;

	if (!(sep = PyObject_GetAttrString(os, "sep")))
		return;
		
	if (!(pathsep = PyString_AsString(sep)))
		return;
	Py_INCREF(sep);
	ospathsep = pathsep[0];
	
	cur = PyObject_GetAttrString(os, "curdir");
	par = PyObject_GetAttrString(os, "pardir");

	if (!(curdir = PyString_AsString(cur)))
		return;
	Py_INCREF(cur);
	
	if (!(pardir = PyString_AsString(par)))
		return;
	Py_INCREF(par);
}
