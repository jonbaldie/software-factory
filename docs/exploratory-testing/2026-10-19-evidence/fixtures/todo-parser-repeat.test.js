import assert from "node:assert/strict";
import test from "node:test";
test("recognizes a second example", () => {
  const example = "// TODO(factory): Add retry support to the client";
  assert.ok(example.includes("TODO(factory):"));
});
