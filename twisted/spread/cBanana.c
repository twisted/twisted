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

/* Python accessible */
extern EXTERN_API PyObject *dataReceived( PyObject *self, PyObject *args );
extern EXTERN_API PyObject *cBananaState_new( PyObject *self, PyObject *args );

// function table passed into Python by initcBanana()
static PyMethodDef cBanana__methods__[] =
  {
    { "dataReceived", dataReceived, METH_VARARGS },
    { "newState", cBananaState_new, METH_VARARGS },
    { NULL, NULL }        /* Sentinel */
  };

static PyObject *BananaError;

#define HIGH_BIT_SET 0x80

#define LIST		 0x80
#define INT			 0x81
#define STRING		 0x82
#define SYMBOL		 0x83
#define NEG			 0x84
#define VOCAB		 0x85
#define FLOAT		 0x86

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


const char *findVocab(int key)
{
  int offset = -key;
  if (offset < 0 || offset >= NUM_VOCABS) {
    return NULL;
  }
  return vocab[offset];
}

int b1282int(unsigned char *str, int begin, int end)
{
  int i = 0;
  int place = 0;
  int count;

  for (count=begin; count < end; count++) {
    unsigned char num = str[count];
    /*printf("b1282int: num = %d\n", num);*/
    if (place) {
      i = i +  (num << (7 * place)); // (num * (128 ^ place));
    } else {
      i = i + num;
    }
    place++;
  }
  return i;
}



/**************
** Real gotItem - invokes the python callback if required
**************/
int gotPythonItem(PyObject *object, struct listItem *currentList, PyObject *expressionReceived)
{
  PyObject *result;
  PyObject *args;
  int ret;

  if (currentList) {
    PyList_Append(currentList->thisList, object);
    return 1;
  }
  else {
    args = PyTuple_New(1);
    ret = PyTuple_SetItem(args, 0, object);
    if (ret != 0) {
      //printf("Couldn't add item to tuple\n");
      return 0;
    }
    
    /*printf("Calling expressionReceived.\n");*/
    result = PyObject_CallObject(expressionReceived, args);
    if (!result) {
      /* printf("Call to expressionReceived failed.\n"); */
      /* printf( "ARGS: < %s >\n",  PyString_AsString( PyObject_Repr(args) ) ); */
      /* PyErr_Print(); */
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
** dataReceived
**
**
** Inputs:
**		newChunk - the new data to decode
**      expressionReceived - the python callable to invoke for each expression
**
** Output:
**  number of bytes processed
*****************************************/
extern EXTERN_API PyObject *dataReceived( PyObject *self, PyObject *args )
{

  PyObject *newChunk;		  // pointer to new chunk
  PyObject *expressionReceived;   // callback
  PyObject *stateobj;             // state object
  cBananaState *state;            // state
  unsigned char *buffer;          // buffer to work from
  int bufferSize;                 // size of the remaining portion
  int pos;
  int nBeginPos;
  int nEndPos;
  unsigned char typeByte;

  /* printf("Entering dataReceived!\n"); */

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

  PyString_AsStringAndSize(newChunk,(char**) &buffer, &bufferSize);
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
      if (!state->currentList)	{
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
      break;
    }
    case INT: {
      int num = b1282int(buffer, nBeginPos, nEndPos);
      if (!gotItemInt(num, state->currentList, expressionReceived)){
	return NULL;
      }
      break;
    }
    case NEG: {
      int num = -b1282int(buffer, nBeginPos, nEndPos);
      if (!gotItemInt(num, state->currentList, expressionReceived)){
	return NULL;
      }
      break;
    }
      
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
      pos = pos + len;
      break;
    }
      
    case SYMBOL:
    case VOCAB: {
      // SYBMOL and VOCAB are the same??
      int num = b1282int(buffer, nBeginPos, nEndPos);
      const char *vocabString = findVocab(-num);
      if (vocabString == NULL) {
	PyErr_SetString(BananaError, "Vocab String not found.");
	return NULL;
      }
      if (!gotItemString(vocabString, strlen(vocabString), state->currentList, expressionReceived)) {
	return NULL;
      }
      break;
    }
      
    case FLOAT: {
      // TODO: optimize floats
      char* numBuffer;
      int numLen;
      double num;

      numLen = (nEndPos - nBeginPos) + 1;
      numBuffer = malloc(numLen);
      memcpy(numBuffer, buffer+nBeginPos, (nEndPos - nBeginPos));
      numBuffer[numLen-1] = 0;
      /* printf("float string: %s %d\n", numBuffer, numLen); */
      num = atof(numBuffer);
      free(numBuffer);
      /* printf("float number: %f\n", num); */
      gotItemFloat(num, state->currentList, expressionReceived);
      break;
    }
      
    default: {
      PyErr_SetString(BananaError, "Invalid Type Byte");
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
  PyObject *m, *d;
  cBananaStateType.ob_type = &PyType_Type;
  m = Py_InitModule("cBanana", cBanana__methods__);
  d = PyModule_GetDict(m);
  BananaError = PyErr_NewException("cBanana.error", NULL, NULL);
  PyDict_SetItemString(d, "error", BananaError);
}


