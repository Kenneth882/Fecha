import { describe, expect, it } from "vitest";

import { taskHref } from "./task-links";

describe("taskHref", () => {
  it("links a Vocab Task to its screen", () => {
    expect(taskHref({ id: "t1", kind: "vocab" })).toBe("/tasks/t1");
  });

  it("links a Listen Task to the Listen Task screen", () => {
    expect(taskHref({ id: "t2", kind: "listen" })).toBe("/tasks/t2/listen");
  });

  it("gives a Speak Task no link: it's locked until Week 5", () => {
    expect(taskHref({ id: "t3", kind: "speak" })).toBeNull();
  });
});
