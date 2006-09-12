
package com.twistedmatrix;

import junit.framework.Test;
import junit.framework.TestSuite;

import com.twistedmatrix.internet.TestInternet;
import com.twistedmatrix.amp.TestAMP;

public class AllJUnitTests {
    public static Test suite() {
        TestSuite ts = new TestSuite();
        for (Test t: new Test[]
            {
                TestInternet.suite(),
                TestAMP.suite()
            }) {
            ts.addTest(t);
        }
        return ts;
    }
}

