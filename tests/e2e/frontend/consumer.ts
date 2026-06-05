// Compile-only contract check: the generated read view must be usable exactly
// as its types claim. If the projection were wrong (e.g. `id` optional, or
// `createdAt` typed as string), `tsc --noEmit` would fail here.

import type { Message } from "./generated";
import { messageConverter } from "./generated";

export function summarize(m: Message): string {
  const idLen: number = m.id.length; // doc-id -> required string (converter-injected)
  const body: string = m.body; // presence-guaranteed -> required
  const created = m.createdAt ?? null; // server-ts -> Timestamp | null (| undefined)
  const kind: string = m.kind ?? "unknown"; // open enum accepts any string
  const tagCount: number = m.tags?.length ?? 0;
  const reactionCount: number = m.reactions?.length ?? 0;
  return `${idLen}:${body}:${String(created)}:${kind}:${tagCount}:${reactionCount}`;
}

// The converter is what makes `id: string` hold at runtime.
export const converter = messageConverter;
