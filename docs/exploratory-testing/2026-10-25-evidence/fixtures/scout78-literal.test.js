import assert from "node:assert/strict";
import test from "node:test";
test("documentation example remains literal data", () => {
  const example = "// TODO(factory): Render a documentation preview 20261025";
  assert.ok(example.startsWith("//"));
  assert.ok(example.includes("TODO(factory):"));
  const single = '// TODO(factory): Single-quoted preview 20261025';
  const escaped = "a \" // TODO(factory): Escaped preview 20261025";
  const template = `${single} // TODO(factory): Template preview 20261025`;
  assert.ok(escaped.length && template.length);
});
