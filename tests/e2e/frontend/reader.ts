// Runtime contract check: subscribe to the doc the Python backend wrote via the
// Firestore emulator and assert the generated read view holds at runtime (this
// is what catches a by_alias key mismatch -- trap #1). Exits 0 on success.

import { initializeApp } from "firebase/app";
import {
  connectFirestoreEmulator,
  doc,
  DocumentReference,
  getFirestore,
  onSnapshot,
  Timestamp,
} from "firebase/firestore";

import { type Message, messageConverter } from "./generated";

const projectId = process.env.GCLOUD_PROJECT ?? "demo-firepact";
// Parse the standard Firebase env var `FIRESTORE_EMULATOR_HOST` (host:port),
// which the test harness sets; fall back to the well-known local default.
const [emuHost, emuPort] = (
  process.env.FIRESTORE_EMULATOR_HOST ?? "127.0.0.1:8080"
).split(":");
const host = emuHost || "127.0.0.1";
const port = Number(emuPort ?? "8080");
const path = process.env.E2E_DOC_PATH ?? "rooms/r1/messages/m1";

const app = initializeApp({ projectId });
const db = getFirestore(app);
connectFirestoreEmulator(db, host, port);

const ref = doc(db, path).withConverter(messageConverter);

const timeout = setTimeout(() => {
  console.error("timeout: no snapshot received");
  process.exit(1);
}, 15000);

const unsubscribe = onSnapshot(
  ref,
  (snapshot) => {
    if (!snapshot.exists()) {
      return;
    }
    const m: Message = snapshot.data();
    const violations: string[] = [];
    if (m.id !== snapshot.id) violations.push(`id ${m.id} != ${snapshot.id}`);
    if (typeof m.body !== "string") violations.push("body not string");
    if (m.createdAt !== null && !(m.createdAt instanceof Timestamp)) {
      violations.push("createdAt not Timestamp|null");
    }
    if (m.author !== undefined && !(m.author instanceof DocumentReference)) {
      violations.push("author not DocumentReference");
    }
    if (typeof m.kind !== "string") violations.push("kind not string");

    clearTimeout(timeout);
    unsubscribe();
    if (violations.length > 0) {
      console.error("contract violations:", violations.join("; "));
      process.exit(1);
    }
    console.log(
      JSON.stringify({
        id: m.id,
        body: m.body,
        kind: m.kind,
        createdAtIsTimestamp: m.createdAt instanceof Timestamp,
        authorIsRef: m.author instanceof DocumentReference,
        tags: m.tags ?? [],
      }),
    );
    process.exit(0);
  },
  (err) => {
    console.error("onSnapshot error:", err.message);
    process.exit(1);
  },
);
