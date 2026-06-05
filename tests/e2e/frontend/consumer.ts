// Compile-only contract check: the generated read view must be usable exactly
// as its types claim. If the projection were wrong (e.g. `id` optional, or
// `createdAt` typed as string), `tsc --noEmit` would fail here.

import { type GeoPoint, serverTimestamp, type Timestamp } from "firebase/firestore";
import type { Message, MessageUpdate } from "./generated";
import { messageConverter } from "./generated";

export function summarize(m: Message): string {
  const idLen: number = m.id.length; // doc-id -> required string (converter-injected)
  const body: string = m.body; // presence-guaranteed -> required
  const created = m.createdAt ?? null; // server-ts -> Timestamp | null (| undefined)
  const kind: string = m.kind ?? "unknown"; // open enum accepts any string
  const tagCount: number = m.tags?.length ?? 0;
  const reactionCount: number = m.reactions?.length ?? 0;
  const edited: Timestamp | undefined = m.editedAt; // non-server datetime -> Timestamp
  const loc: GeoPoint | undefined = m.location; // -> GeoPoint
  const bytes: number = m.thumbnail?.toUint8Array().byteLength ?? 0; // -> Bytes
  const span: number = (m.selection?.[1] ?? 0) - (m.selection?.[0] ?? 0); // tuple [number, number]
  return `${idLen}:${body}:${String(created)}:${kind}:${tagCount}:${reactionCount}:${String(edited)}:${String(loc)}:${bytes}:${span}`;
}

// The converter is what makes `id: string` hold at runtime.
export const converter = messageConverter;

// Update view: optional fields AND FieldValue are both accepted (UpdateData<Write>).
export function edit(): MessageUpdate {
  return { body: "edited", createdAt: serverTimestamp() };
}

// Discriminated union narrows on the literal `kind`: in each branch the
// variant-specific field (width / size) is accessible. If narrowing failed,
// tsc would reject `a.width` / `a.size`.
export function attachmentLabel(m: Message): string {
  const a = m.attachment;
  if (a === undefined) return "none";
  switch (a.kind) {
    case "image":
      return `image:${a.width ?? 0}`;
    case "file":
      return `file:${a.size ?? 0}`;
    default:
      return "unknown";
  }
}
