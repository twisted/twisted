#include <iostream>
using namespace std;

struct OVERLAPPED
{
	int a;
	int b;
};

class MyOverlappedWrapper : public OVERLAPPED
{
public:
	int c;
};

void use_overlapped(OVERLAPPED *ov)
{
	cout << ov->a << endl;

	MyOverlappedWrapper *theWrapper = static_cast<MyOverlappedWrapper *>(ov);
	cout << theWrapper->c << endl;
}

main()
{
	MyOverlappedWrapper wrapper;
	wrapper.a = 123;
	wrapper.b = 456;
	wrapper.c = 789;

	use_overlapped(&wrapper);
}
