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

/* portmap.c: A simple Python wrapper for pmap_set(3) and pmap_unset(3) */

#include <Python.h>
#include <rpc/rpc.h>
#include <rpc/pmap_clnt.h>

static PyObject * portmap_set(PyObject *self, PyObject *args)
{
	unsigned long program, version;
	int protocol;
	unsigned short port;
	
	if (!PyArg_ParseTuple(args, "llih:set", 
			      &program, &version, &protocol, &port))
		return NULL;

	pmap_unset(program, version);
	pmap_set(program, version, protocol, port);
	
	Py_INCREF(Py_None);
	return Py_None;
}

static PyObject * portmap_unset(PyObject *self, PyObject *args)
{
	unsigned long program, version;
	
	if (!PyArg_ParseTuple(args, "ll:unset",
			      &program, &version))
		return NULL;

	pmap_unset(program, version);
	
	Py_INCREF(Py_None);
	return Py_None;
}

static PyMethodDef PortmapMethods[] = {
	{"set", portmap_set, METH_VARARGS, 
	 "Set an entry in the portmapper."},
	{"unset", portmap_unset, METH_VARARGS,
	 "Unset an entry in the portmapper."},
	{NULL, NULL, 0, NULL}
};

void initportmap(void)
{
	(void) Py_InitModule("portmap", PortmapMethods);
}

