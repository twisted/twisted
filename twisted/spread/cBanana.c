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
/* cBanana.c */

#ifdef WIN32
#	include <windows.h>
#	define EXTERN_API __declspec(dllexport)
#	define snprintf _snprintf
#else
#	define EXTERN_API
#endif

#ifdef __GNUC__
#       define TM_INLINE inline
#else
#       define TM_INLINE /* */
#endif

#include <Python.h>

/* Python module initialization */

PyObject* cBanana_module;
PyObject* cBanana_dict;

/* Python accessible */
/* Initialization */
EXTERN_API void initcBanana(void);

/* Encoding */
extern EXTERN_API PyObject *cBanana_encode( PyObject *self, PyObject *args );
extern EXTERN_API PyObject *cBanana_dataReceived( PyObject *self, PyObject *args );

/* State Object */
extern EXTERN_API PyObject *cBananaState_new( PyObject *self, PyObject *args );
extern EXTERN_API void      cBananaState_dealloc(PyObject* self);

/* Buffer Object */
extern EXTERN_API PyObject *cBananaBuf_new( PyObject *self, PyObject *args );
extern EXTERN_API void      cBananaBuf_dealloc(PyObject* self);
extern EXTERN_API PyObject *cBananaBuf_getattr(PyObject* self, char* attrname);
extern EXTERN_API PyObject *cBananaBuf_write( PyObject *self, PyObject *args );
extern EXTERN_API PyObject *cBananaBuf_get( PyObject *self, PyObject *args );
extern EXTERN_API PyObject *cBananaBuf_clear( PyObject *self, PyObject *args );

/* function table passed into Python by initcBanana() */
static PyMethodDef cBanana__methods__[] =
  {
    { "dataReceived", cBanana_dataReceived, METH_VARARGS },
    { "encode", cBanana_encode, METH_VARARGS },
    { "newState", cBananaState_new, METH_VARARGS },
    { "newBuf", cBananaBuf_new, METH_VARARGS },
    { NULL, NULL }        /* Sentinel */
  };

static PyMethodDef cBananaBuf__methods__[] =
  {
    { "write", cBananaBuf_write, METH_VARARGS },
    { "clear", cBananaBuf_clear, METH_VARARGS },
    { "get", cBananaBuf_get, METH_VARARGS },
    { NULL, NULL }        /* Sentinel */
  };


static PyObject *BananaError;

#define HIGH_BIT_SET     0x80

#define LIST             0x80
#define INT              0x81
#define STRING           0x82
#define NEG              0x83
#define FLOAT            0x84
#define LONGINT          0x85
#define LONGNEG          0x86

#define VOCAB            0x87

#define NUM_VOCABS   31

struct listItem
{
  struct listItem *lastList;
  PyObject *thisList;
  int currentIndex;
  int size;
};

/*
 * This struct represents state that's carried between calls.
 */

typedef struct {
  PyObject_HEAD
  struct listItem *currentList;
} cBananaState;

static PyTypeObject cBananaStateType = {
  PyObject_HEAD_INIT(NULL)
  0,
  "cBananaState",
  sizeof(cBananaState),
  0,
  cBananaState_dealloc, /* dealloc */
  0, /* print */
  0, /* getattr */
  0, /* setattr */
  0, /* compare */
  0, /* repr */
  0, /* as_number */
  0, /* as_sequence */
  0, /* as_mapping */
  0, /* hash */
};

typedef struct {
  PyObject_HEAD
  char* contents;
  unsigned int available;
  unsigned int size;
} cBananaBuf;

static PyTypeObject cBananaBufType = {
  PyObject_HEAD_INIT(NULL)
  0,
  "cBananaBuf",
  sizeof(cBananaBuf),
  0,
  cBananaBuf_dealloc, /* dealloc */
  0, /* print */
  cBananaBuf_getattr, /* getattr */
  0, /* setattr */
  0, /* compare */
  0, /* repr */
  0, /* as_number */
  0, /* as_sequence */
  0, /* as_mapping */
  0, /* hash */
  0, /* call */
};

#define INITIAL_BUF_SZ 1024

extern EXTERN_API PyObject*
cBananaBuf_new(PyObject *self, PyObject *args) {
  cBananaBuf* buf;
  if (!PyArg_ParseTuple(args, ":newState")){
    return NULL;
  }
  buf = PyObject_New(cBananaBuf, &cBananaBufType);
  buf->contents = malloc(INITIAL_BUF_SZ);
  buf->size = INITIAL_BUF_SZ;
  buf->available = INITIAL_BUF_SZ;
  return (PyObject*) buf;
}

extern EXTERN_API void
cBananaBuf_dealloc(PyObject *self) {
  cBananaBuf* buf;
  buf = (cBananaBuf*) self;
  if (buf->contents) {
    free(buf->contents);
  }
  buf->contents = 0;
  buf->available = 0;
  buf->size = 0;
  PyObject_Del(self);
}

extern EXTERN_API PyObject*
cBananaBuf_getattr(PyObject *self, char* attrname) {
  return Py_FindMethod(cBananaBuf__methods__, self, attrname);
}

static void cBananaBuf_write_internal(cBananaBuf* me, const char* src, unsigned int len) {
  unsigned int index;
  while (len > (me -> available)) {
    unsigned int newsize;
    newsize = me->size * 2;
    me->contents = realloc(me->contents, newsize);
    me->available += me->size;
    me->size = newsize;
  }
  index = me->size - me->available;
  memcpy((me->contents)+index, src, len);
  me->available -= len;
}

#define cBananaBuf_append_byte(me, byte) \
  do { \
    if (me->available >= 1) { \
      me->contents[me->size - me->available] = byte; \
      me->available--; \
    } else { \
      cBananaBuf_write_internal(me, &byte, 1); \
    } \
  } while (0)

extern EXTERN_API PyObject*
cBananaBuf_write(PyObject *self, PyObject *args) {
  cBananaBuf* me;
  char* src;
  int len;
  me = (cBananaBuf*) self;
  if (!PyArg_ParseTuple(args, "s#:write", &src, &len)) {
    return NULL;
  }
  cBananaBuf_write_internal(me, src, len);
  Py_INCREF(Py_None);
  return Py_None;
}


static void cBananaBuf_clear_internal(cBananaBuf* me) {
  me->available = me->size;
}

extern EXTERN_API PyObject*
cBananaBuf_clear(PyObject *self, PyObject *args) {
  cBananaBuf* me;
  me = (cBananaBuf*) self;
  if (!PyArg_ParseTuple(args, ":clear")) {
    return NULL;
  }
  cBananaBuf_clear_internal(me);
  Py_INCREF(Py_None);
  return Py_None;
}

extern EXTERN_API PyObject*
cBananaBuf_get(PyObject *self, PyObject *args) {
  cBananaBuf* me;
  me = (cBananaBuf*) self;
  if (PyArg_ParseTuple(args, ":get")) {
    return PyString_FromStringAndSize(me->contents, me->size - me->available);
  }
  return NULL;
}


extern EXTERN_API PyObject*
cBananaState_new(PyObject *self, PyObject *args) {
  cBananaState* state;
  if (!PyArg_ParseTuple(args, ":newState")){
    return NULL;
  }
  state = PyObject_New(cBananaState, &cBananaStateType);
  state->currentList = NULL;
  return (PyObject*) state;
}

extern EXTERN_API void
cBananaState_dealloc(PyObject* self)
{
  struct listItem* thatList;
  struct listItem* thisList;
  thisList = ((cBananaState*)self) -> currentList;
  while (thisList) {
    thatList = thisList->lastList;
    Py_DECREF(thisList->thisList);
    free(thisList);
    thisList = thatList;
  }
  PyObject_Del(self);
}

static const char *vocab[] = {
  /* Filler so we start at 1 not 0 */
  "Dummy",  /* 0 */
  /* Jelly Data Types */
  "None",   /* 1 */
  "class",  /* 2 */
  "dereference", /* 3 */
  "reference",  /* 4 */
  "dictionary", /* 5 */
  "function",/* 6 */
  "instance",/* 7 */
  "list", /* 8 */
  "module",/* 9 */
  "persistent",/* 10 */
  "tuple",/* 11 */
  "unpersistable",/* 12 */
  /* PB Data Types */
  "copy",/* 13 */
  "cache",/* 14 */
  "cached",/* 15 */
  "remote",/* 16 */
  "local",/* 17 */
  "lcache",/* 18 */
  /* PB Protocol messages */
  "version",/* 19 */
  "login",/* 20 */
  "password",/* 21 */
  "challenge",/* 22 */
  "perspective",/* 23 */
  "inperspective",/* 24 */
  "cachemessage",/* 25 */
  "message",/* 26 */
  "answer",/* 27 */
  "error",/* 28 */
  "decref",/* 29 */
  "decache",/* 30 */
  "uncache"/* 31 */
};


static const char *findVocab(int offset)
{
  if (offset < 0 || offset > NUM_VOCABS) {
    return NULL;
  }
  return vocab[offset];
}

static void int2b128(long integer, cBananaBuf* writeobj) {
  char typeByte;
  if (integer == 0) {
    typeByte = 0;
    cBananaBuf_append_byte(writeobj, typeByte);
    return;
  }
  while (integer) {
    typeByte = (char) integer & 0x7f;
    cBananaBuf_append_byte(writeobj, typeByte);
    integer >>= 7;
  }
}

PyObject* cBanana_encode_internal(PyObject* encodeobj, cBananaBuf* writeobj) {
  char typeByte;
  if (PyList_Check(encodeobj)) {
    int counter;
    int2b128(PyList_Size(encodeobj), writeobj);
    typeByte = LIST;
    cBananaBuf_append_byte(writeobj, typeByte);
    for (counter=0; counter < PyList_Size(encodeobj); counter ++) {
      if (!cBanana_encode_internal(PyList_GetItem(encodeobj, counter), writeobj)) {
	return NULL;
      }
    }
  } else if (PyTuple_Check(encodeobj)) {
    int counter;
    int2b128(PyTuple_Size(encodeobj), writeobj);
    typeByte = LIST;
    cBananaBuf_append_byte(writeobj, typeByte);
    for (counter=0; counter < PyTuple_Size(encodeobj); counter ++) {
      if (!cBanana_encode_internal(PyTuple_GetItem(encodeobj, counter), writeobj)) {
	return NULL;
      }
    }
  } else if (PyInt_Check(encodeobj)) {
    long integer = PyInt_AsLong(encodeobj);
    if (integer >= 0) {
      int2b128(integer, writeobj);
      typeByte = INT;
      cBananaBuf_append_byte(writeobj, typeByte);
    } else {
      int2b128(-integer, writeobj);
      typeByte = NEG;
      cBananaBuf_append_byte(writeobj, typeByte);
    }
  } else if (PyLong_Check(encodeobj)) {
    PyObject* result;
    PyObject* argtup;
    argtup = PyTuple_New(2);
    Py_INCREF(encodeobj);
    if (PyObject_Compare(encodeobj, PyLong_FromDouble(0.0)) == -1) {
      typeByte = LONGNEG;
      PyTuple_SetItem(argtup, 0, PyNumber_Negative(encodeobj));
    } else {
      typeByte = LONGINT;
      PyTuple_SetItem(argtup, 0, encodeobj);
    }
    /* Py_INCREF(writeobj); */
    PyTuple_SetItem(argtup, 1, PyObject_GetAttrString((PyObject*) writeobj, "write"));
    result = PyObject_CallObject(PyObject_GetAttrString(cBanana_module, "pyint2b128"), argtup);
    Py_DECREF(argtup);
    if (!result) {
      return NULL;
    }
    Py_DECREF(result);
    cBananaBuf_append_byte(writeobj, typeByte);
  } else if (PyFloat_Check(encodeobj)) {
    double x;
    int s;
    int e;
    double f;
    long fhi, flo;
    char floatbuf[8];
    x = PyFloat_AS_DOUBLE(encodeobj);
    if (x < 0) {
      s = 1;
      x = -x;
    }
    else
      s = 0;
    f = frexp(x, &e);
    /* Normalize f to be in the range [1.0, 2.0) */
    if (0.5 <= f && f < 1.0) {
      f *= 2.0;
      e--;
    }
    else if (f == 0.0) {
      e = 0;
    }
    else {
      PyErr_SetString(PyExc_SystemError,
		      "frexp() result out of range");
      return NULL;
    }
    
    if (e >= 1024) {
      /* XXX 1024 itself is reserved for Inf/NaN */
      PyErr_SetString(PyExc_OverflowError,
		      "float too large to pack with d format");
      return NULL;
    }
    else if (e < -1022) {
      /* Gradual underflow */
      f = ldexp(f, 1022 + e);
      e = 0;
    }
    else if (!(e == 0 && f == 0.0)) {
      e += 1023;
      f -= 1.0; /* Get rid of leading 1 */
    }
    
    /* fhi receives the high 28 bits; flo the low 24 bits (== 52 bits) */
    f *= 268435456.0; /* 2**28 */
    fhi = (long) floor(f); /* Truncate */
    f -= (double)fhi;
    f *= 16777216.0; /* 2**24 */
    flo = (long) floor(f + 0.5); /* Round */
    
    /* This is hard-coded to be encoded big-endian */
    floatbuf[0] = (s<<7) | (e>>4); 
    floatbuf[1] = (char) (((e&0xF)<<4) | (fhi>>24));
    floatbuf[2] = (fhi>>16) & 0xFF;
    floatbuf[3] = (fhi>>8) & 0xFF;
    floatbuf[4] = fhi & 0xFF;
    floatbuf[5] = (flo>>16) & 0xFF;
    floatbuf[6] = (flo>>8) & 0xFF;
    floatbuf[7] = flo & 0xFF;
    
    typeByte = FLOAT;
    cBananaBuf_append_byte(writeobj, typeByte);
    /* it's CALLING PYTHON FUNCTIONS FOR FUN AND PROFIT!!! */
    cBananaBuf_write_internal(writeobj, floatbuf, sizeof(floatbuf));
  } else if (PyString_Check(encodeobj)) {
    int len;
    char* src;
    PyString_AsStringAndSize(encodeobj, &src, &len);
    int2b128(len, writeobj);
    typeByte = STRING;
    cBananaBuf_append_byte(writeobj, typeByte);
    cBananaBuf_write_internal(writeobj, src, len);
  } else {
    char errmsg[256];
    snprintf(errmsg, 256, "Unknown Python Type: %s", encodeobj->ob_type->tp_name);
    PyErr_SetString(BananaError, errmsg);
    return NULL;
  }

  Py_INCREF(Py_None);
  return Py_None;
}


extern EXTERN_API
PyObject* cBanana_encode(PyObject* self, PyObject *args) {
  PyObject* encodeobj;
  PyObject* writeobj;
  if (!PyArg_ParseTuple(args, "OO", &encodeobj, &writeobj)) {
    return NULL;
  }
  if (writeobj->ob_type != &cBananaBufType) {
    PyErr_SetString(BananaError, "Encoding only accepts BananaBufs");
    return NULL;
  }
  return cBanana_encode_internal(encodeobj, (cBananaBuf*) writeobj);
}


/* TODO: change the API to return a failure if the encoded value won't fit.
   Current implementation just folds oversized values. */
static long b1282int(unsigned char *str, int begin, int end) {
  long result = 0;
  long place = 0;
  int count;

  for (count=begin; count < end; count++) {
    unsigned char num = str[count];
    if (place) {
      result = result +  (num << (7 * place)); /* (num * (128 ^ place)); */
    } else {
      result = result + num;
    }
    place++;
  }
  return result;
}



/**************
 ** invokes the python callback if required
 ** Arguments:
 ** "object" argument must be a new reference -- I steal a reference to it.
 **************/

static TM_INLINE int gotPythonItem(PyObject *object, struct listItem *currentList, PyObject *expressionReceived)
{
  if (currentList) {
    PyList_SET_ITEM(currentList->thisList, currentList->currentIndex, object);
    currentList->currentIndex++;
    return 1;
  }
  else {
    PyObject *result;
    PyObject *args;

    args = PyTuple_New(1);
    PyTuple_SetItem(args, 0, object);
    result = PyObject_CallObject(expressionReceived, args);
    if (result) {
      Py_DECREF(result);
    }
    Py_DECREF(args);
    return (int) result;
  }
}

/**************
** Helper function to add a float
**************/
static TM_INLINE int gotItemFloat(double value, struct listItem *currentList, PyObject *expressionReceived)
{
  PyObject *object = PyFloat_FromDouble(value);
  return gotPythonItem(object, currentList, expressionReceived);
}

/**************
** Helper function to add an int
**************/
static TM_INLINE int gotItemInt(int value, struct listItem *currentList, PyObject *expressionReceived)
{
  PyObject *object = PyInt_FromLong(value) ;
  return gotPythonItem(object, currentList, expressionReceived);
}

/**************
** Helper function to add a string
**************/
static TM_INLINE int gotItemString(const char *value, int len, struct listItem *currentList, PyObject *expressionReceived)
{
  PyObject *object;
  object = PyString_FromStringAndSize(value, len);
  return gotPythonItem(object, currentList, expressionReceived);
}

/**************
** Helper function to add a list
**************/
static TM_INLINE int gotItemList(PyObject *listObject, struct listItem *currentList, PyObject *expressionReceived)
{
  return gotPythonItem(listObject, currentList, expressionReceived);
}

/****************************************
** cBanana_dataReceived
**
**
** Inputs:
**              newChunk - the new data to decode
**      expressionReceived - the python callable to invoke for each expression
**
** Output:
**  number of bytes processed
*****************************************/
extern EXTERN_API PyObject *cBanana_dataReceived( PyObject *self, PyObject *args )
{

  PyObject *newChunk;             /* pointer to new chunk */
  PyObject *expressionReceived;   /* callback */
  PyObject *stateobj;             /* state object */
  cBananaState *state;            /* state */
  unsigned char *buffer;          /* buffer to work from */
  char **bufptr;                  /* for python funcs that want *buffer */
  int bufferSize;                 /* size of the remaining portion */
  int pos;
  int nBeginPos;
  int nEndPos;
  unsigned char typeByte;
  bufptr = (char**) &buffer;

  if( !PyArg_ParseTuple( args, "OOO", &stateobj, &newChunk, &expressionReceived) )
    return NULL;

  if (!PyCallable_Check(expressionReceived) ) {
    /* ERROR - must be a callback we can use */
    Py_INCREF(Py_None);
    return Py_None;
  }

  if (!PyString_Check(newChunk)) {
    printf("Second arg was not a string\n");
    Py_INCREF(Py_None);
    return Py_None;
  }

  if ((stateobj == NULL) || ((stateobj->ob_type) != (&cBananaStateType))) {
    printf("state object wasn't\n");
    Py_INCREF(Py_None);
    return Py_None;
  }

  state = (cBananaState*) stateobj;

  PyString_AsStringAndSize(newChunk, bufptr, &bufferSize);

  pos = 0;
  while (pos < bufferSize) {
    /* printf("beginning at %d\n", pos); */
    nBeginPos = pos; /* beginning of number, also, 'consumed so far' */
    while (buffer[pos] < HIGH_BIT_SET) {
      /* printf("Got character %c (%d) at %d\n", current[pos], current[pos], pos ); */
      pos++;
      if ((pos-nBeginPos) > 64) {
        /* ERROR: "Security precaution: more than 64 bytes of prefix" */
        PyErr_SetString(PyExc_SystemError,
			"Security precaution: more than 64 bytes of prefix (this should raise an exception).\n");
        return NULL;
      } else if (pos == bufferSize) {
        /* boundary condition -- not enough bytes to finish the number */
        return PyInt_FromLong(nBeginPos);
      }
    }
    /* extract the type byte */
    nEndPos = pos;
    typeByte = buffer[pos];
    pos++;

    switch (typeByte) {
    case LIST: {
      int num = b1282int(buffer, nBeginPos, nEndPos);

      if (num > 640*1024) {
        PyErr_SetString(BananaError,
                        "Security precaution: List too long.\n");
        return NULL;
      }
      if (!state->currentList)  {
        state->currentList = (struct listItem *)malloc(sizeof(struct listItem));
        if (!state->currentList)
          return PyErr_NoMemory();
        state->currentList->lastList = NULL;
        state->currentList->currentIndex = 0;
        state->currentList->size = num;
        state->currentList->thisList = PyList_New(num);
        if (!state->currentList->thisList) {
          /* PyList_New sets PyErr_NoMemory for us */
          free(state->currentList); state->currentList = NULL;
          return NULL;
        }
      } else {
        struct listItem *newList = (struct listItem *) malloc(sizeof(struct listItem));
        if (!newList)
          return PyErr_NoMemory();
        newList->size = num;
        newList->thisList = PyList_New(num);
        if (!newList->thisList) {
          free(newList);
          return NULL;
        }
        newList->currentIndex = 0;
        newList->lastList = state->currentList;
        state->currentList = newList;
      }
    }
      break;
      
    case INT: {
      int num = b1282int(buffer, nBeginPos, nEndPos);
      if (!gotItemInt(num, state->currentList, expressionReceived)){
        return NULL;
      }
    }
      break;
    case NEG: {
      int num = -b1282int(buffer, nBeginPos, nEndPos);
      if (!gotItemInt(num, state->currentList, expressionReceived)){
        return NULL;
      }
    }
      break;
    case LONGINT: {
      PyObject* argtup;
      PyObject* rval;
      PyObject* pyb1282int;
      
      argtup = PyTuple_New(1);
      PyTuple_SetItem(argtup, 0,
		      PyString_FromStringAndSize(buffer + nBeginPos,
						 nEndPos - nBeginPos));
      pyb1282int = PyObject_GetAttrString(cBanana_module, "pyb1282int");
      if (!pyb1282int) { return NULL; }
      rval = PyObject_CallObject(pyb1282int, argtup);
      Py_DECREF(argtup);
      Py_DECREF(pyb1282int);
      if (!rval) { return NULL; }
      if (!gotPythonItem(rval, state->currentList, expressionReceived)) {
	return NULL;
      }
      
    }
      break;
    case LONGNEG: {
      PyObject* argtup;
      PyObject* rval;
      PyObject* negval;
      PyObject* pyb1282int;

      argtup = PyTuple_New(1);
      PyTuple_SetItem(argtup, 0,
		      PyString_FromStringAndSize(buffer + nBeginPos,
						 nEndPos - nBeginPos));
      pyb1282int = PyObject_GetAttrString(cBanana_module, "pyb1282int");
      if (!pyb1282int) { return NULL; }
      rval = PyObject_CallObject(pyb1282int, argtup);
      Py_DECREF(argtup);
      Py_DECREF(pyb1282int);
      if (!rval) {
	return NULL;
      }
      negval = PyNumber_Negative(rval);
      if (!negval) {
	return NULL;
      }
      Py_DECREF(rval);
      if (!gotPythonItem(negval, state->currentList, expressionReceived)) {
	return NULL;
      }
    }
      break;
    case STRING: {
      int len = b1282int(buffer, nBeginPos, nEndPos);
      if (len > 640 * 1024) {
        PyErr_SetString(BananaError,
                        "Security precaution: String too long.\n");
        return NULL;
      }
      if (len > (bufferSize - pos) ) {
        /* boundary condition; not enough bytes to complete string */
        return PyInt_FromLong(nBeginPos);
      }
      if (!gotItemString(buffer+pos, len, state->currentList, expressionReceived)) {
        return NULL;
      }
      pos += len;
    }
      break;

    case VOCAB: {
      int num = b1282int(buffer, nBeginPos, nEndPos);
      const char *vocabString = findVocab(num);
      if (vocabString == NULL) {
	char errmsg[256];
	snprintf(errmsg, 256, "Vocab String Not Found: %d", num);
        PyErr_SetString(BananaError, errmsg);
        return NULL;
      }
      if (!gotItemString(vocabString, strlen(vocabString),
			 state->currentList, expressionReceived)) {
        return NULL;
      }
    }
      break;

    case FLOAT: {
      double num;
      /* the following snippet thanks to structmodule.c */
      /* new moon tonight.  be careful! */
      int sign_bit;
      int exponent;
      long fhi, flo;
      char* p;
      if (8 > (bufferSize - pos) ) {
	/* printf("\nWARNING: buffer size %d pos %d\n", bufferSize, pos); */
        /*   boundary condition; not enough bytes to complete string */
        return PyInt_FromLong(nBeginPos);
      }
      p = (char*) (buffer + pos);

      sign_bit = (*p>>7) & 1; /* First byte */
      exponent = (*p & 0x7F) << 4;
      p ++;
      exponent |= (*p>>4) & 0xF; /* Second byte */
      fhi = (*p & 0xF) << 24;
      p ++;
      fhi |= (*p & 0xFF) << 16; /* Third byte */
      p ++;
      fhi |= (*p & 0xFF) << 8; /* Fourth byte */
      p ++;
      fhi |= (*p & 0xFF);	/* Fifth byte */
      p ++;
      flo = (*p & 0xFF) << 16; /* Sixth byte */
      p ++;
      flo |= (*p & 0xFF) << 8;	/* Seventh byte */
      p ++;
      flo |= (*p & 0xFF); /* Eighth byte */
      p ++;
      
      num = (double)fhi + (double)flo / 16777216.0; /* 2**24 */
      num /= 268435456.0; /* 2**28 */
      
      /* XXX This sadly ignores Inf/NaN */
      if (exponent == 0)
	exponent = -1022;
      else {
	num += 1.0;
	exponent -= 1023;
      }
      num = ldexp(num, exponent);
      
      if (sign_bit)
	num = -num;
      /* Would you like your posessions identified? */
      /* printf("float number: %f\n", num); */
      gotItemFloat(num, state->currentList, expressionReceived);
      /* doubles are 8 bytes long */
      pos += 8;
    }
      break;

    default: {
      char errmsg[256];
      snprintf(errmsg, 256, "Invalid Type Byte: %hhd", typeByte);
      PyErr_SetString(BananaError, errmsg);
      return NULL;
    }
    }
    /* If there is a list, check if it is full */
    if (state->currentList) {
      /* printf("bufferSize: %d  listSize: %d\n", PyList_Size(state->currentList->thisList), state->currentList->size); */
      while (state->currentList && (state->currentList->currentIndex == state->currentList->size)){
        PyObject *list;
        struct listItem *tmp;

        list = state->currentList->thisList;
        tmp = state->currentList->lastList;
        free(state->currentList);
        state->currentList = tmp;

        if (!gotItemList(list, state->currentList, expressionReceived)) {
          return NULL;
        }
      }
    }
  }


  /* printf(full); */
  return PyInt_FromLong(pos);

}

/* Do the equivalent of:
 * from foo.bar import baz
 * where "foo.bar" is 'name' and "baz" is 'from_item'
 * Stolen from cReactorUtil.c
 */
static PyObject *util_FromImport(const char *name, const char *from_item)
{
  PyObject *from_list;
  PyObject *module;
  PyObject *item;

  /* Make the from list. */
  from_list = PyList_New(1);
  PyList_SetItem(from_list, 0, PyString_FromString(from_item));

  /* Attempt the import, with const correctness removed. */
  module = PyImport_ImportModuleEx((char *)name, NULL, NULL, from_list);
  Py_DECREF(from_list);
  if (!module)
  {
    return NULL;
  }

  /* Get the from_item from the module. */
  item = PyObject_GetAttrString(module, (char *)from_item);
  Py_DECREF(module);

  return item;
}

/* module's initialization function for Python */
extern EXTERN_API void initcBanana(void)
{
  cBananaStateType.ob_type = &PyType_Type;
  cBananaBufType.ob_type = &PyType_Type;
  cBanana_module = Py_InitModule("cBanana", cBanana__methods__);
  cBanana_dict = PyModule_GetDict(cBanana_module);
  BananaError = util_FromImport("twisted.spread.banana", "BananaError");
  if (!BananaError) {
    PyErr_Print();
    /* this means we'll have our own exception type, not shared with
       banana.py */
    BananaError = PyErr_NewException("BananaError", NULL, NULL);
  }
  PyDict_SetItemString(cBanana_dict, "BananaError", BananaError);
}

