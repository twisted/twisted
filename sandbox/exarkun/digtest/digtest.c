#include <stdio.h>
#include "digcalc.h"

void go(char* n, char* cn, char* u, char* r, char* p, char* a, char* nc, char* m, char* q, char* i) {
	HASHHEX HA1;
	HASHHEX HA2 = "";
	HASHHEX Response;

	DigestCalcHA1(a, u, r, p, n, cn, HA1);
	DigestCalcResponse(HA1, n, nc, cn, q, m, i, HA2, Response);
	printf("Response = %s\n", Response);
}

void main(int argc, char** argv) {
/*
	char * pszNonce = "dcd98b7102dd2f0e8b11d0f600bfb0c093";
	char * pszCNonce = "0a4f113b";
	char * pszUser = "Mufasa";
	char * pszRealm = "testrealm@host.com";
	char * pszPass = "Circle Of Life";
	char * pszAlg = "md5";
	char szNonceCount[9] = "00000001";
	char * pszMethod = "GET";
	char * pszQop = "auth";
	char * pszURI = "/dir/index.html";
*/
	char* pszNonce = argv[1];
	char* pszCNonce = argv[2];
	char* pszUser = argv[3];
	char* pszRealm = argv[4];
	char* pszPass = argv[5];
	char* pszAlg = argv[6];
	char* szNonceCount = argv[7];
	char* pszMethod = argv[8];
	char* pszQop = argv[9];
	char* pszURI = argv[10];

	if (argc < 11)
		printf("Usage: %s nonce cnonce user realm password algorithm nonce-count method qop uri\n", argv[0]);
	else
		go(pszNonce, pszCNonce, pszUser, pszRealm, pszPass, pszAlg, szNonceCount, pszMethod, pszQop, pszURI);
}
