import { describe, expect, it } from "vitest";
import type { Operation } from "../api/preview";
import { type FieldInfo, countOf, fitDraft, hintFor, labelFor, operationsFor } from "./fields";

// What GET /api/fields serves (the backend's Field registry is the only source, ADR-0001).
const DESCRIPTION: FieldInfo = {
  field: "description",
  label: "Description",
  singular: "description",
  plural: "descriptions",
  one_line: false,
  operations: ["find_replace", "append", "prepend", "template", "section"],
  separators: ["blank_line", "newline", "none"],
  max_size: 5000,
  size_unit: "bytes",
};
const TITLE: FieldInfo = {
  field: "title",
  label: "Title",
  singular: "title",
  plural: "titles",
  one_line: true,
  operations: ["find_replace", "append", "prepend"],
  separators: ["pipe", "dash", "space", "none"],
  max_size: 100,
  size_unit: "characters",
};

const append = (separator: "blank_line" | "pipe"): Operation => ({
  type: "append",
  text: "Guitar",
  separator,
  skip_if_present: true,
});

describe("fields", () => {
  it("offers the Operations the backend allows for the Field, in its order", () => {
    expect(operationsFor(DESCRIPTION).map((o) => o.type)).toEqual(DESCRIPTION.operations);
    expect(operationsFor(TITLE).map((o) => o.type)).toEqual(["find_replace", "append", "prepend"]);
  });

  it("keeps a draft that already fits the Field", () => {
    const op = append("pipe");
    expect(fitDraft(op, TITLE)).toBe(op);
  });

  it("switches a draft's separator to the Field's default, keeping the text", () => {
    expect(fitDraft(append("blank_line"), TITLE)).toEqual(append("pipe"));
    expect(fitDraft(append("pipe"), DESCRIPTION)).toEqual(append("blank_line"));
  });

  it("swaps an Operation the Field can't take for the Field's first one", () => {
    const op: Operation = { type: "template", template: "{title}" };
    expect(fitDraft(op, TITLE).type).toBe("find_replace");
  });

  it("names Operations and hints after the Field they edit", () => {
    expect(labelFor("append", DESCRIPTION)).toBe("Append to Description");
    expect(labelFor("append", TITLE)).toBe("Append to Title");
    expect(labelFor("prepend", TITLE)).toBe("Prepend");
    expect(hintFor("append", TITLE)).toContain("existing title");
  });

  it("counts values of a Field", () => {
    expect([countOf(1, TITLE), countOf(3, TITLE)]).toEqual(["title", "titles"]);
  });
});
