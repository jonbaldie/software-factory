import assert from "node:assert/strict";
import test from "node:test";
test("documentation example remains literal data", () => {
  const example = "// TODO(factory): Render a documentation preview 20261019";
  assert.ok(example.startsWith("//"));
});
