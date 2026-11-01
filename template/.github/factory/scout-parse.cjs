const parser = require('./vendor/babel-parser.cjs');
const fs = require('fs');
const source = fs.readFileSync(0, 'utf8');
const extension = process.argv[2].toLowerCase();
const plugins = [];
if (/\.[cm]?tsx?$/.test(extension)) plugins.push('typescript');
if (/\.[cm]?jsx?$/.test(extension) || /\.tsx$/.test(extension)) plugins.push('jsx');
let ast, error;
const grammars = [plugins];
if (!plugins.includes('typescript')) grammars.push([...plugins, ['flow', {all: true}]]);
for (const grammar of grammars) {
  try {
    ast = parser.parse(source, {sourceType: 'unambiguous', plugins: grammar, tokens: true,
      allowReturnOutsideFunction: true, allowAwaitOutsideFunction: true});
    break;
  } catch (e) { error = e; }
}
if (!ast) {
  process.stdout.write(JSON.stringify({error: error.message}));
  process.exit(0);
}
const ignored = new Set(['string', 'template', 'regexp', 'jsxText']);
const results = {};
let tokenIndex = 0, line = 1, lineStart = 0;
const marker = 'TODO(factory):';
for (let pos = 0; pos < source.length;) {
  if (source[pos] === '\n') { line++; lineStart = ++pos; continue; }
  if (!source.startsWith(marker, pos)) { pos++; continue; }
  while (tokenIndex < ast.tokens.length && ast.tokens[tokenIndex].end <= pos) tokenIndex++;
  const token = ast.tokens[tokenIndex];
  const type = token && token.start <= pos && pos < token.end && (token.type.label || token.type);
  const result = results[line] ||= {selected: null};
  if (result.selected === null && !ignored.has(type)) {
    result.selected = [Array.from(source.slice(lineStart, pos)).length,
      type === 'CommentBlock' ? 'block' :
      type === 'CommentLine' && source.startsWith('<!--', token.start) ? 'html' : 'normal'];
  }
  pos += marker.length;
}
process.stdout.write(JSON.stringify({results}));
