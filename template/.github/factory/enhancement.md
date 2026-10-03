## Method: build it test-first, in vertical slices

The ticket is an enhancement. Build it as a series of vertical slices: one test, then just enough code to pass it, then the next test.

### 1. Choose the seams

A **seam** is a public interface where a caller sees the behaviour, such as an exported function, a CLI command or an HTTP endpoint. Tests go at seams, so the internals can be rewritten without breaking them.

Choose the seams before you write any test. Use the interfaces the ticket names (a triage brief lists them under **Key interfaces**). Otherwise use the interface a caller of the new behaviour would reach for. Done when you've written the seams down. They go under **Seams:** in the pull request description.

### 2. Red, then green, one slice at a time

List the behaviours the ticket asks for: one per acceptance criterion or worked example. Then take them one at a time, each slice a **tracer bullet** through a seam:

1. Write one test of the behaviour at a seam.
2. Run it and watch it go **red** because the behaviour is missing. Keep the line of output that shows the failure.
3. Write only the code that test needs to go **green**.
4. Run the test command and watch it pass.

A test that is green on arrival means an earlier slice already built its behaviour. Keep it, and note which slice built it.

Let each slice shape the next one: write the next test only after the last one is green. Refactoring belongs to the review stage, so each green step stays the smallest that passes.

Done when every behaviour on your list has a green test, with either its failure line or the slice that built it.

### What a good test is

- It calls a seam and asserts what a caller would see. Its name says what the behaviour is, such as "truncate cuts at a word boundary".
- Its expected values are literals, taken from the ticket, a worked example or the spec. Work them out by hand, independently of the code.
- It mocks only system boundaries: external APIs, time, randomness, and sometimes the database or filesystem. Everything the project owns runs for real.
- It makes one logical assertion.

### Done when

Read the whole pull request description, including appended fix summaries. Evidence under **Seams:** and **Slices:** can be supplied there; a later correction supersedes an earlier statement. Judge whether the evidence is complete, without requiring the original section to be rewritten.

- [ ] Every behaviour the ticket asks for has a test.
- [ ] Every test calls only the seams listed under **Seams:** in the pull request description, and mocks only system boundaries.
- [ ] Every expected value is a literal worked out independently of the code.
- [ ] The code does what the tests demand, and nothing beyond the ticket.
- [ ] The test command passes.
- [ ] The pull request description has a **Slices:** list after **Seams:**, one line per behaviour: its test name, then the failure line from its red run, or "green on arrival" and the slice that built it.
