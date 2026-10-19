import assert from "node:assert/strict";
import test from "node:test";
test("recognizes the documented comment marker", () => {
  const example = "// TODO(factory): Add pagination to the search results";
  assert.ok(example.includes("TODO(factory):"));
});
