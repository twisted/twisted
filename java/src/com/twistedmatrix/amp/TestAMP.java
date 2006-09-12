
package com.twistedmatrix.amp;

import java.util.List;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.Collection;

import java.nio.ByteBuffer;

import junit.framework.Test;
import junit.framework.TestCase;
import junit.framework.TestSuite;

import java.io.UnsupportedEncodingException;

public class TestAMP extends TestCase {
    public static class Int16ReceiverTest extends TestCase {
        byte[] parsedString = null;

        public void testParsing() throws Throwable {
            Int16StringReceiver ir = new Int16StringReceiver() {
                    public void stringReceived(byte[] hunk) {
                        parsedString = hunk;
                    }
                };
            String hw = "hello world";
            byte[] hwbytes = hw.getBytes("utf-8");
            byte[] lengthprefix = {0, (byte) hwbytes.length};
            byte[] trailingGarbage = {(byte)251};
            ir.dataReceived(lengthprefix);
            ir.dataReceived(hwbytes);
            ir.dataReceived(trailingGarbage);
            assertEquals(new String(parsedString, "ISO-8859-1"),
                         new String(hwbytes, "ISO-8859-1"));
        }
    }

    public static class AmpParserTest extends TestCase {
        AMPBox received;

        public void testParsing() throws Throwable {
            AMPParser ap = new AMPParser() {
                    public void ampBoxReceived(AMPBox hm) {
                        received = hm;
                    }
                };

            byte[] data =
                "\u0000\u0005hello\u0000\u0005world\u0000\u0000"
                .getBytes("ISO-8859-1");

            ap.dataReceived(data);
            assertEquals(AMPBox.asString(received.get("hello")), "world");
        }

        public void testParseData() throws Throwable {
            assertEquals(
                AMPBox.asString(
                    AMPParser.parseData(
                        "\u0000\u0005hello\u0000\u0005world\u0000\u0000"
                        .getBytes("ISO-8859-1")).get(0).get("hello")
                    ),
                "world");
        }

        public void testByteIntegerConversion() throws Throwable {
            for (int i = 0; i < 256; i++) {
                assertEquals(Int16StringReceiver.toInt((byte)i),
                             i);
            }
        }

        public void testParseLongString() throws Throwable {
            String veryLong = (
                "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" +
                "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" +
                "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" +
                "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx");

            String toParse = ("\u0000\u00ff" + veryLong + "\u0000\u00ff" + veryLong + "\u0000\u0000");
            byte[] dataToParse = toParse.getBytes("ISO-8859-1");

            List<AMPBox> alhm = AMPParser.parseData(dataToParse);
            assertEquals(
                AMPBox.asString(alhm.get(0).get(veryLong)),
                veryLong);
            assertEquals(alhm.size(), 1);
        }

        public void testParseEvenLongerString() throws Throwable {
            String veryLong = (
                "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" +
                "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" +
                "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" +
                "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx");

            String toParse = ("\u0001\u0004" + veryLong + "\u0001\u0004" + veryLong + "\u0000\u0000");
            byte[] dataToParse = toParse.getBytes("ISO-8859-1");

            List<AMPBox> alhm = AMPParser.parseData(dataToParse);
            assertEquals(
                AMPBox.asString(alhm.get(0).get(veryLong)),
                veryLong);
            assertEquals(alhm.size(), 1);
        }

        private class SomeAttributes {
            public int a;
            public String b;
            public boolean c;
            public byte[] d;
            // float?

            public boolean equals(Object o) {
                if (o instanceof SomeAttributes) {
                    SomeAttributes other = (SomeAttributes) o;
                    return ((other.a == this.a) &&
                            (other.b.equals(this.b)) &&
                            (other.c == this.c) &&
                            (Arrays.equals(other.d, this.d)));
                }
                return false;
            }
        }

        public void testFillingOutStruct() throws Throwable {
            AMPBox ab = new AMPBox();
            SomeAttributes sa = new SomeAttributes();

            ab.put("a", "1");
            ab.put("b", "hello world");
            ab.put("c", "True");
            ab.put("d", "bytes");

            ab.fillOut(sa);
            assertEquals(sa.a, 1);
            assertEquals(sa.b, "hello world");
            assertEquals(sa.c, true);
            assertEquals(AMPBox.asString(sa.d), "bytes");
        }

        public void testFillingOutRoundTrip() throws Throwable {
            AMPBox ab = new AMPBox();
            SomeAttributes sa = new SomeAttributes();
            SomeAttributes sb = new SomeAttributes();
            sa.a = 7;
            sa.b = "more stufp";
            sa.c = true;
            sa.d = new byte[] {1, 2, 3, 4, 5, 6, 7, 8};
            assertFalse(sa.equals(sb));

            ab.extractFrom(sa);
            ab.fillOut(sb);
            assertEquals(sa, sb);
        }

        public void testEncodeDecodeRoundTrip() throws Throwable {
            AMPBox ab = new AMPBox();
            AMPBox ab2 = null;
            String veryLong = (
                "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" +
                "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" +
                "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" +
                "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx");
            ab.put("a", "1");
            ab.put("asdfasdfasdfasdfasdfasdf", "1");
            ab.put("ninjas", "ashdufa879ghawghawunfauwdvn");
            ab.put(veryLong, "haha");
            ab.put("asdfqwer", veryLong);
            ab2 = AMPParser.parseData(ab.encode()).get(0);
            assertEquals(ab, ab2);
            ab2 = AMPParser.parseData(ab2.encode()).get(0);
            assertEquals(ab, ab2);
        }

        int rancommandcount = 0;

        public void testCommandDispatch() throws Throwable {
            AMP a = new AMP() {
                    @AMP.Command(
                        name="ninjas",
                        arguments="")
                    public void thingy() {
                        rancommandcount ++;
                    }
                };
            AMPBox ab = new AMPBox();
            ab.put("_command", "ninjas");
            ab.put("_ask", "ninjas");
            a.ampBoxReceived(ab);
            assertEquals(1, rancommandcount);
        }

        ArrayList<Integer> ali;

        public class WhatTheHell extends AMP {
            public @AMP.Command(name="addstuff",
                         arguments="a b c d")
                void
            thingy (int java, int doesnt, int know, int argnames) {
                rancommandcount++;
                ali.add(java);
                ali.add(doesnt);
                ali.add(know);
                ali.add(argnames);
            }
        }

        public void testCommandArgumentParsing() throws Throwable {
            this.ali = new ArrayList<Integer>();
            AMP a = new WhatTheHell();

            AMPBox ab = new AMPBox();
            ab.put("_command", "addstuff");
            ab.put("_ask", "0x847");
            ab.putAndEncode("a", new Integer(1234));
            ab.putAndEncode("b", new Integer(5678));
            ab.putAndEncode("c", new Integer(9101112));
            ab.putAndEncode("d", new Integer(13141516));
            a.ampBoxReceived(ab);
            assertEquals(1, rancommandcount);
            ArrayList<Integer> alicheck = new ArrayList<Integer>();
            alicheck.add(1234);
            alicheck.add(5678);
            alicheck.add(9101112);
            alicheck.add(13141516);
            assertEquals(ali, alicheck);
        }
    }

    public static Test suite() {
        TestSuite suite = new TestSuite();
        suite.addTest(new TestSuite(Int16ReceiverTest.class));
        suite.addTest(new TestSuite(AmpParserTest.class));
        return suite;
    }
}
