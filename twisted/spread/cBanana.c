/* cBanana.c */

#ifdef WIN32
#include <windows.h>
#define EXTERN_API __declspec(dllexport)
#else
#define EXTERN_API
#endif

#include <Python.h>

/* Python module initialization */

EXTERN_API void initcBanana(void);

PyObject* cBanana_module;
PyObject* cBanana_dict;


/* Python accessible */
extern EXTERN_API PyObject *cBanana_encode( PyObject *self, PyObject *args );
extern EXTERN_API PyObject *cBanana_dataReceived( PyObject *self, PyObject *args );
extern EXTERN_API PyObject *cBananaState_new( PyObject *self, PyObject *args );

// function table passed into Python by initcBanana()
static PyMethodDef cBanana__methods__[] =
  {
    { "dataReceived", cBanana_dataReceived, METH_VARARGS },
    { "encode", cBanana_encode, METH_VARARGS },
    { "newState", cBananaState_new, METH_VARARGS },
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
  int size;
};

/*
 * This struct represents state that's carried between calls.
 */

typedef struct {
  PyObject_HEAD
  struct listItem *currentList;
} cBananaState;

staticforward PyTypeObject cBananaStateType;

extern EXTERN_API PyObject*
cBananaState_new(PyObject *self, PyObject *args) {
  cBananaState* state;
  if (!PyArg_ParseTuple(args, ":newState")){
    return NULL;
  }
  state = PyObject_NEW(cBananaState, &cBananaStateType);
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
    Py_XDECREF(thisList->thisList);
    free(thisList);
    thisList = thatList;
  }
  PyMem_DEL(self);
}

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

const char *vocab[] = {
  // Filler so we start at 1 not 0
  "Dummy",  /* 0 */
  // Jelly Data Types
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
  // PB Data Types
  "copy",/* 13 */
  "cache",/* 14 */
  "cached",/* 15 */
  "remote",/* 16 */
  "local",/* 17 */
  "lcache",/* 18 */
  // PB Protocol messages
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


const char *findVocab(int offset)
{
  if (offset < 0 || offset > NUM_VOCABS) {
    return NULL;
  }
  return vocab[offset];
}

void callWithChar(PyObject* writeobj, char x) {
  PyObject *argtup;
  PyObject *argstring;

  argtup = PyTuple_New(1);
  argstring = PyString_FromStringAndSize(&x, 1);
  
  PyTuple_SetItem(argtup, 0, argstring);
  PyObject_CallObject(writeobj, argtup);
  Py_XDECREF(argtup);
  Py_XDECREF(argstring);
}

void int2b128(long integer, PyObject* writeobj) {
  if (integer == 0) {
    callWithChar(writeobj, '\0');
    return;
  }
  while (integer) {
    callWithChar(writeobj, (char) integer &0x7f);
    integer >>= 7;
  }
}

PyObject* cBanana_encode_internal(PyObject* encodeobj, PyObject* writeobj) {
  
  if (PyList_Check(encodeobj)) {
    int counter;
    int2b128(PyList_Size(encodeobj), writeobj);
    callWithChar(writeobj, LIST);
    for (counter=0; counter < PyList_Size(encodeobj); counter ++) {
      if (!cBanana_encode_internal(PyList_GetItem(encodeobj, counter), writeobj)) {
	return NULL;
      }
    }
  } else if (PyTuple_Check(encodeobj)) {
    int counter;
    int2b128(PyTuple_Size(encodeobj), writeobj);
    callWithChar(writeobj, LIST);
    for (counter=0; counter < PyTuple_Size(encodeobj); counter ++) {
      if (!cBanana_encode_internal(PyTuple_GetItem(encodeobj, counter), writeobj)) {
	return NULL;
      }
    }
  } else if (PyInt_Check(encodeobj)) {
    long integer = PyInt_AS_LONG(encodeobj);
    if (integer >= 0) {
      int2b128(integer, writeobj);
      callWithChar(writeobj, INT);
    } else {
      int2b128(-integer, writeobj);
      callWithChar(writeobj, NEG);
    }
  } else if (PyLong_Check(encodeobj)) {
    PyErr_SetString(BananaError,
		    "Longs not yet supported.");
    return NULL;
  } else if (PyFloat_Check(encodeobj)) {
    double x;
    int s;
    int e;
    double f;
    long fhi, flo;
    char floatbuf[8];
    PyObject *argtup;
    PyObject *argstring;
    PyObject* ret;
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
    
    callWithChar(writeobj, FLOAT);
    /* it's CALLING PYTHON FUNCTIONS FOR FUN AND PROFIT!!! */
    argtup = PyTuple_New(1);
    argstring = PyString_FromStringAndSize(floatbuf, 8);

    PyTuple_SetItem(argtup, 0, argstring);
    ret = PyObject_CallObject(writeobj, argtup);
    Py_XDECREF(argtup);
    Py_XDECREF(argstring);
    return ret;
  } else if (PyString_Check(encodeobj)) {
    PyObject* argtup;
    PyObject* ret;
    int2b128(PyString_Size(encodeobj), writeobj);
    callWithChar(writeobj, STRING);

    argtup = PyTuple_New(1);

    PyTuple_SetItem(argtup, 0, encodeobj);
    ret = PyObject_CallObject(writeobj, argtup);
    Py_XDECREF(argtup);
    return ret;
  } else {
    PyErr_SetString(BananaError, "Unknown Python Type.  Can't deal with it.");
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
  if (!PyCallable_Check(writeobj)) {
    Py_INCREF(Py_None);
    return Py_None;
  }
  return cBanana_encode_internal(encodeobj, writeobj);
}


long long b1282int(unsigned char *str, int begin, int end) {
  long long result = 0;
  long long place = 0;
  int count;

  for (count=begin; count < end; count++) {
    unsigned char num = str[count];
    /*printf("b1282int: num = %d\n", num);*/
    if (place) {
      result = result +  (num << (7 * place)); // (num * (128 ^ place));
    } else {
      result = result + num;
    }
    place++;
  }
  return result;
}



/**************
 ** invokes the python callback if required
 **************/
int gotPythonItem(PyObject *object, struct listItem *currentList, PyObject *expressionReceived)
{
  PyObject *result;
  PyObject *args;

  if (currentList) {
    PyList_Append(currentList->thisList, object);
    return 1;
  }
  else {
    args = PyTuple_New(1);
    if (PyTuple_SetItem(args, 0, object) != 0) {
      //printf("Couldn't add item to tuple\n");
      return 0;
    }

    /*printf("Calling expressionReceived.\n");*/
    result = PyObject_CallObject(expressionReceived, args);
    if (!result) {
      return 0;
    }
    return 1;
  }
}

/**************
** Helper function to add a float
**************/
int gotItemFloat(double value, struct listItem *currentList, PyObject *expressionReceived)
{
  PyObject *object = PyFloat_FromDouble(value);
  return gotPythonItem(object, currentList, expressionReceived);
}

/**************
** Helper function to add an int
**************/
int gotItemInt(int value, struct listItem *currentList, PyObject *expressionReceived)
{
  PyObject *object = PyInt_FromLong(value) ;
  return gotPythonItem(object, currentList, expressionReceived);
}

/**************
** Helper function to add a long int
**************/
int gotItemLong(long long value, struct listItem *currentList, PyObject *expressionReceived)
{
  PyObject *object = PyLong_FromLongLong(value) ;
  return gotPythonItem(object, currentList, expressionReceived);
}

/**************
** Helper function to add a string
**************/
int gotItemString(const char *value, int len, struct listItem *currentList, PyObject *expressionReceived)
{
  char* myValue;
  PyObject *object;
  myValue = malloc(len);
  memcpy(myValue, value, len);
  object = PyString_FromStringAndSize(myValue, len);
  return gotPythonItem(object, currentList, expressionReceived);
}

/**************
** Helper function to add a list
**************/
int gotItemList(PyObject *listObject, struct listItem *currentList, PyObject *expressionReceived)
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

  PyObject *newChunk;             // pointer to new chunk
  PyObject *expressionReceived;   // callback
  PyObject *stateobj;             // state object
  cBananaState *state;            // state
  unsigned char *buffer;          // buffer to work from
  int bufferSize;                 // size of the remaining portion
  int pos;
  int nBeginPos;
  int nEndPos;
  unsigned char typeByte;

  /* printf("Entering cBanana_dataReceived!\n"); */

  if( !PyArg_ParseTuple( args, "OOO", &stateobj, &newChunk, &expressionReceived) )
    return NULL;

  if (!PyCallable_Check(expressionReceived) ) {
    // ERROR - must be a callback we can use
    //printf("ERROR - must be a callback we can use.\n");
    Py_INCREF(Py_None);
    return Py_None;
  }

  if (!PyString_Check(newChunk)) {
    printf("First arg was not a string\n");
    Py_INCREF(Py_None);
    return Py_None;
  }

  if ((stateobj == NULL) || ((stateobj->ob_type) != (&cBananaStateType))) {
    printf("state object wasn't\n");
    Py_INCREF(Py_None);
    return Py_None;
  }
  state = (cBananaState*) stateobj;

  buffer = PyString_AS_STRING(newChunk);
  bufferSize = PyString_GET_SIZE(newChunk);

  pos = 0;
  while (pos < bufferSize) {
    /* printf("beginning at %d\n", pos); */
    nBeginPos = pos; /* beginning of number, also, 'consumed so far' */
    while (buffer[pos] < HIGH_BIT_SET) {
      //printf("Got character %c (%d) at %d\n", current[pos], current[pos], pos );
      pos++;
      if ((pos-nBeginPos) > 64) {
        //ERROR: "Security precaution: more than 64 bytes of prefix"
        printf("Security precaution: more than 64 bytes of prefix (this should raise an exception).\n");
        Py_INCREF(Py_None);
        return Py_None;
      } else if (pos == bufferSize) {
        /* boundary condition -- not enough bytes to finish the number */
        return PyInt_FromLong(nBeginPos);
      }
    }
    // extract the type byte
    nEndPos = pos;
    typeByte = buffer[pos];
    pos++;

    switch (typeByte) {
    case LIST: {
      int num = b1282int(buffer, nBeginPos, nEndPos);
      if (!state->currentList)  {
        state->currentList = (struct listItem *)malloc(sizeof(struct listItem));
        state->currentList->lastList = NULL;
        state->currentList->size = num;
        state->currentList->thisList = PyList_New(0);
      } else {
        struct listItem *newList = (struct listItem *) malloc(sizeof(struct listItem));
        newList->size = num;
        newList->thisList = PyList_New(0);
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
      
      argtup = PyTuple_New(1);
      PyTuple_SetItem(argtup, 0,
		      PyString_FromStringAndSize(buffer + nBeginPos,
						 nEndPos - nBeginPos));
      rval = PyObject_CallObject(PyObject_GetAttrString(cBanana_module, "pyb1282int"), argtup);

      if (!rval) {
	return NULL;
      }
      if (!gotPythonItem(rval, state->currentList, expressionReceived)) {
	return NULL;
      }
    }
      break;
    case LONGNEG: {
      PyObject* argtup;
      PyObject* rval;
      PyObject* negval;

      argtup = PyTuple_New(1);
      PyTuple_SetItem(argtup, 0,
		      PyString_FromStringAndSize(buffer + nBeginPos,
						 nEndPos - nBeginPos));
      rval = PyObject_CallObject(PyObject_GetAttrString(cBanana_module, "pyb1282int"), argtup);
      if (!rval) {
	return NULL;
      }
      negval = PyNumber_Negative(rval);
      if (!negval) {
	return NULL;
      }
      Py_XDECREF(rval);
      if (!gotPythonItem(negval, state->currentList, expressionReceived)) {
	return NULL;
      }
    }
      break;
    case STRING: {
      int len = b1282int(buffer, nBeginPos, nEndPos);
      /* printf("String length: %d\n", len); */
      if (len > 640 * 1024) {
        PyErr_SetString(BananaError, "Security precaution: Length identifier  > 640K.\n");
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
	// printf("\nWARNING: buffer size %d pos %d\n", bufferSize, pos);
        // boundary condition; not enough bytes to complete string
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
      // printf("float number: %f\n", num);
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
    // If there is a list, check if it is full
    if (state->currentList) {
      /* printf("bufferSize: %d  listSize: %d\n", PyList_Size(state->currentList->thisList), state->currentList->size); */
      while (state->currentList && PyList_Size(state->currentList->thisList) == state->currentList->size) {
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


  ////printf(full);
  return PyInt_FromLong(pos);

}

// module's initialization function for Python
extern EXTERN_API void initcBanana(void)
{
  cBananaStateType.ob_type = &PyType_Type;
  cBanana_module = Py_InitModule("cBanana", cBanana__methods__);
  cBanana_dict = PyModule_GetDict(cBanana_module);
  BananaError = PyErr_NewException("cBanana.error", NULL, NULL);
  PyDict_SetItemString(cBanana_dict, "cBanana.error", BananaError);
}


