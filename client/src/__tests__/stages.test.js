import { describe, it, expect } from "vitest";
import { STAGES, STATUS_META, formatDate, stageIndex } from "../stages.js";

describe("STAGES", () => {
  it("has 7 entries in expected order", () => {
    expect(STAGES).toHaveLength(7);
    expect(STAGES[0].key).toBe("queued");
    expect(STAGES[6].key).toBe("complete");
  });

  it("every stage has key, label, emoji, and blurb", () => {
    for (const stage of STAGES) {
      expect(stage.key).toBeTruthy();
      expect(stage.label).toBeTruthy();
      expect(stage.emoji).toBeTruthy();
      expect(stage.blurb).toBeTruthy();
    }
  });
});

describe("stageIndex", () => {
  it("returns 0 for queued", () => {
    expect(stageIndex("queued")).toBe(0);
  });

  it("returns correct index for a mid-pipeline stage", () => {
    expect(stageIndex("researching")).toBe(2);
  });

  it("returns correct index for complete", () => {
    expect(stageIndex("complete")).toBe(6);
  });

  it("returns 0 for unknown stage key", () => {
    expect(stageIndex("nonexistent_stage")).toBe(0);
  });
});

describe("STATUS_META", () => {
  it("covers all five job statuses", () => {
    const required = ["IN-PROGRESS", "COMPLETE", "HALTED", "FAILED", "AWAITING_INPUT"];
    for (const status of required) {
      expect(STATUS_META[status]).toBeDefined();
      expect(STATUS_META[status].label).toBeTruthy();
      expect(STATUS_META[status].className).toBeTruthy();
    }
  });
});

describe("formatDate", () => {
  it("returns empty string for null", () => {
    expect(formatDate(null)).toBe("");
  });

  it("returns empty string for undefined", () => {
    expect(formatDate(undefined)).toBe("");
  });

  it("returns empty string for an invalid ISO string", () => {
    expect(formatDate("not-a-date")).toBe("");
  });

  it("returns a non-empty string for a valid ISO string", () => {
    const result = formatDate("2026-08-21T12:00:00.000Z");
    expect(result).toBeTruthy();
    expect(typeof result).toBe("string");
  });
});
