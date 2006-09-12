
package com.twistedmatrix.internet;

import junit.framework.Test;
import junit.framework.TestCase;
import junit.framework.TestSuite;

public class TestInternet extends TestCase {
    public static class DeferredTest extends TestCase {
        int callcount = 0;
        public void testImmediateSuccessDeferred() {
            Deferred d = Deferred.succeed();
            d.addCallback(new Deferred.Callback() {
                    public Object callback(Object o) {
                        callcount++;
                        // XXX could autoboxing help here?
                        return new Integer(((Integer)o).intValue() + 1);
                    }
                });
            assertEquals(callcount, 1);
        }
    }

    public static Test suite() {
        TestSuite suite = new TestSuite();
        suite.addTest(new TestSuite(DeferredTest.class));
        return suite;
    }
}
