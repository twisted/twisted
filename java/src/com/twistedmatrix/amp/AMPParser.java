package com.twistedmatrix.amp;

import java.util.HashMap;
import java.util.List;
import java.util.ArrayList;

import java.io.UnsupportedEncodingException;

public abstract class AMPParser extends Int16StringReceiver {

    enum State { KEY, VALUE, INIT };

    State state = State.INIT;

    byte[] workingKey;

    AMPBox workingBox;

    public void stringReceived(byte[] hunk) {
        switch(this.state) {
        case INIT:
            this.workingBox = new AMPBox();
        case KEY:
            if (hunk.length == 0) {
                if (this.workingBox.size() == 0) {
                    System.out.println("empty box, you lose");
                }
                this.ampBoxReceived(this.workingBox);
                this.workingBox = null;
                this.state = State.INIT;
            } else {
                this.workingKey = hunk;
                this.state = State.VALUE;
            }
            break;
        case VALUE:
            this.workingBox.put(workingKey, hunk);
            this.state = State.KEY;
            this.workingKey = null;
            break;
        }
    }

    public abstract void ampBoxReceived(AMPBox hm);

    private static class ParseGatherer extends AMPParser {
        ArrayList<AMPBox> alhm;
        public ParseGatherer() {
            alhm = new ArrayList<AMPBox>();
        }
        public void ampBoxReceived(AMPBox hm) {
            alhm.add(hm);
        }
    }

    public static List<AMPBox> parseData(byte[] data) {
        ParseGatherer pg = new ParseGatherer();
        pg.dataReceived(data);
        if (pg.recvd.length != 0) {
            System.out.println("UNPARSED: " + new String(pg.workingKey));
            for (byte b: pg.recvd) {
                System.out.print(Int16StringReceiver.toInt(b));
                System.out.print(", ");
            }
            System.out.println();
        }
        return pg.alhm;
    }
}
