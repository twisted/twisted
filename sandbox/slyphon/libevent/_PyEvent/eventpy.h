// Python libevent helper routines
// Martin Murray <murrayma@citi.umich.edu>
// Mon Nov 24 04:26:37 EST 2003
//
#include <event.h>
#include <unistd.h>

struct event *allocate_event() {
    return malloc(sizeof(struct event));
}

void free_event(struct event *ev) {
    free(ev);
}

struct timeval *allocate_timeval() {
    return malloc(sizeof(struct timeval));
}

void free_timeval(struct timeval *tv) {
    free(tv);
}

