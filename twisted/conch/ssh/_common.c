#include <string.h>
#include <Python.h>
#include <longintrepr.h> // for conversions
#include <gmp.h>

PyObject* _common_module;

void longObjToMPZ(mpz_t m, PyLongObject *p) {
  int size, i;
  mpz_t temp, temp2;
  mpz_init(temp);
  mpz_init(temp2);
  if (p->ob_size>0)
    size = p->ob_size;
  else
    size = -p->ob_size;
  for (i=0; i<size; i++) {
    mpz_set_ui(temp, p->ob_digit[i]);
    mpz_mul_2exp(temp2, temp, SHIFT * i);
    mpz_add(m, m, temp2);
  }
  mpz_clear(temp);
  mpz_clear(temp2);
}

PyObject* mpzToLongObj(mpz_t m) {
  /* borrowed from gmpy */
  int size = (mpz_sizeinbase(m, 2) + SHIFT - 1) / SHIFT;
  int i;
  mpz_t temp;
  PyLongObject *l = _PyLong_New(size);
  if (!l) return NULL;
  mpz_init_set(temp, m);
  for (i=0;i<size;i++){
    l->ob_digit[i] = (digit) (mpz_get_ui(temp) & MASK);
    mpz_fdiv_q_2exp(temp, temp, SHIFT);
  }
  i=size;
  while ((i>0) && (l->ob_digit[i-1] == 0)) i--;
  l->ob_size = i;
  mpz_clear(temp);
  return (PyObject*)l;
}

PyObject* long2str(PyObject*, PyObject*);
PyObject* pow2str(PyObject*, PyObject*);
PyObject* getMP(PyObject*, PyObject*);
PyObject* fast_pow(PyObject*, PyObject*);

static PyMethodDef _common__methods__[] =
  {
    { "MP", long2str, METH_VARARGS },
    { "_MPpow", pow2str, METH_VARARGS },
    { "getMP", getMP, METH_VARARGS },
    { "pow", fast_pow, METH_VARARGS },
    { NULL, NULL }
  };

PyObject* long2str(PyObject* self, PyObject* args) {
  PyObject* l, *r;
  mpz_t m;
  char *s, *s2;
  int len, len2, i;
  if (!PyArg_ParseTuple(args, "O!", &PyLong_Type, &l)) return NULL;
  mpz_init(m);
  longObjToMPZ(m, (PyLongObject*)l);
  s = mpz_export(NULL, &len, 1, sizeof(char), 1, 0, m);
  s2=(char*)malloc(len);
  len2 = len;
  i=4;
  do {
    s2[--i] = (char)len2;
    len2 >>= 8;
  } while (i>0);
  mpz_clear(m);
  memcpy(s2+4, s, len);
  r=Py_BuildValue("s#", s2, len+4);
  free(s2);
  return r;
}

PyObject* pow2str(PyObject* self, PyObject* args) {
  PyObject *lx, *ly, *lz, *r;
  mpz_t x,y,z;
  char *s, *s2=NULL;
  unsigned int len, len2, i;
  if (!PyArg_ParseTuple(args, "O!O!O!", &PyLong_Type, &lx,
                                        &PyLong_Type, &ly,
                                        &PyLong_Type, &lz)) return NULL;
  mpz_init(x);
  mpz_init(y);
  mpz_init(z);
  longObjToMPZ(x, (PyLongObject*)lx); 
  longObjToMPZ(y, (PyLongObject*)ly); 
  longObjToMPZ(z, (PyLongObject*)lz);
  mpz_powm(x, x, y, z);
  s = mpz_export(NULL, &len, 1, sizeof(char), 1, 0, x);
  s2=(char*)malloc(len+4);
  len2 = len;
  i=4;
  do {
    s2[--i] = (char)len2;
    len2 >>= 8;
  } while (i>0);
  memcpy(s2+4, s, len);
  r=Py_BuildValue("s#", s2, len+4);
  free(s2);
  mpz_clear(x);
  mpz_clear(y);
  mpz_clear(z);
  return r;
}

PyObject* getMP(PyObject* self, PyObject* args) {
  char *s, *rest;
  unsigned int len, lenrest, x=0, i=4;
  PyObject *l, *r;
  mpz_t temp;
  if (!PyArg_ParseTuple(args, "s#", &s, &len)) return NULL;
  do {
    x = (x<<8) | (*s++ & 0xFF);
  } while (--i > 0);
  lenrest = len - 4 - x;
  rest = malloc(lenrest);
  memcpy(rest, s+x, lenrest);
  mpz_init(temp);
  mpz_import(temp, x, 1, sizeof(char), 1, 0, s);
  l = mpzToLongObj(temp);
  mpz_clear(temp);
  r = Py_BuildValue("(Ns#)", l, rest, lenrest);
  free(rest);
  return r;
}

PyObject* fast_pow(PyObject *self, PyObject* args) {
  PyObject *lx, *ly, *lz=NULL, *r;
  mpz_t x,y,z;
  if (!PyArg_ParseTuple(args, "O!O!O!", &PyLong_Type, &lx,
                                        &PyLong_Type, &ly,
                                        &PyLong_Type, &lz)) return NULL;
  mpz_init(x);
  mpz_init(y);
  mpz_init(z);
  longObjToMPZ(x, (PyLongObject*)lx);
  longObjToMPZ(y, (PyLongObject*)ly);
  longObjToMPZ(z, (PyLongObject*)lz);
  mpz_powm(x, x, y, z);
  r = mpzToLongObj(x);
  mpz_clear(x);
  mpz_clear(y);
  mpz_clear(z);
  return r;
}

void init_common(void) {
  _common_module = Py_InitModule("_common", _common__methods__);
}
