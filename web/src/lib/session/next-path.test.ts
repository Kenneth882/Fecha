import { describe, expect, it } from "vitest";

import { safeNextPath } from "./next-path";

describe("safeNextPath", () => {
  it.each([
    ["/", "/"],
    ["/plan", "/plan"],
    ["/tasks/42?from=today#phrases", "/tasks/42?from=today#phrases"],
  ])("keeps the same-origin path %s", (next, expected) => {
    expect(safeNextPath(next)).toBe(expected);
  });

  it.each([
    "https://evil.example/",
    "//evil.example/steal",
    "/\\evil.example",
    "\\\\evil.example",
    "javascript:alert(1)",
    "evil.example",
    "/%0d%0aSet-Cookie:x",
    " /plan",
  ])("falls back to / for the off-site or odd value %j", (next) => {
    expect(safeNextPath(next)).toBe("/");
  });

  it("falls back to / when there's no next", () => {
    expect(safeNextPath(null)).toBe("/");
    expect(safeNextPath(undefined)).toBe("/");
    expect(safeNextPath("")).toBe("/");
  });

  it("never sends a User back to the login or refresh steps, which would loop", () => {
    expect(safeNextPath("/login?next=/plan")).toBe("/");
    expect(safeNextPath("/api/session/refresh?next=/")).toBe("/");
  });
});
