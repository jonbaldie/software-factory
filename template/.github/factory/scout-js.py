import re
import sys
import json
import subprocess
from pathlib import Path

JS = re.compile(r'\.[cm]?[jt]sx?$', re.I)


def main():
    data = sys.stdin.buffer.read()
    pos = 0
    cache = {}
    out = sys.stdout.buffer
    while pos < len(data):
        end = data.index(b'\0', pos)
        path = data[pos:end]
        pos = end + 1
        end = data.index(b'\0', pos)
        line = data[pos:end]
        pos = end + 1
        end = data.index(b'\n', pos)
        hit = data[pos:end]
        pos = end + 1
        name = path.decode('utf-8', 'surrogateescape')
        kind = 'normal'
        context = b''
        if JS.search(name):
            if path not in cache:
                with open(path, 'rb') as source:
                    raw = source.read()
                # Match Node's UTF-8 decoding so parser offsets index the same characters.
                text = raw.decode('utf-8', 'replace')
                parsed = subprocess.run(['node', str(Path(__file__).with_name('scout-parse.cjs')), name],
                                        input=raw, stdout=subprocess.PIPE,
                                        check=True)
                result = json.loads(parsed.stdout)
                decisions = {number: entry['selected'] for number, entry in result.get('results', {}).items()}
                cache[path] = (text.split('\n'), decisions, 'error' in result)
            lines, found, parse_error = cache[path]
            if parse_error:
                kind = 'unparsed'
            else:
                selected = found.get(line.decode())
                if selected is None:
                    kind = 'skip'
                else:
                    offset, kind = selected
                    source_line = lines[int(line) - 1]
                    context = source_line[:offset].encode('utf-8')
                    hit = source_line[offset:].encode('utf-8')
        out.write(path + b'\0' + line + b'\0' + kind.encode() + b'\0' + context + b'\0' + hit + b'\n')


if __name__ == '__main__':
    main()
