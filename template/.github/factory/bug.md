## Method: diagnose the bug, then fix it

The ticket is a bug. Work these steps in order, and finish each one before you start the next. The loop in step 1 is the whole method: everything after it consumes it.

### 1. Build a red loop

Build one command that goes **red** on this bug: it drives the code path where the bug happens and asserts the exact symptom the ticket reports. Reach for these in order:

1. A failing test at whatever seam reaches the bug: unit, integration or end to end.
2. A CLI run on a fixture input, diffed against the expected output.
3. A throwaway harness that calls the buggy code path directly, with external services stubbed.
4. For output that is only sometimes wrong, a loop over many random inputs that stops at the first wrong one.

Then make it **tight**: seconds to run, the same verdict every run (pin the time, seed randomness, isolate the filesystem and network), asserting the specific symptom. For an intermittent bug, raise the reproduction rate (repeat the trigger, add load, narrow the timing window) until most runs go red.

Done when you have run the command and watched it go red on the reported symptom. The red has to match the ticket: the trigger it describes, and the symptom at the severity it reports. A loop built on a trigger you made up, or showing a milder symptom, such as a slowdown for a reported hang, has found a different bug. Theories wait until the loop matches.

If you can't build a matching red loop, stop here and return `needs-info` as described in the implementer instructions. Ask for what would let the factory reproduce this bug, such as access to an environment, a captured log or a failing input. That report is the finished result of this run.

### 2. Minimise

Note the exact symptom the loop shows: the error message, the wrong output or the timing.

Then cut inputs, callers, config, data and steps one at a time, rerunning the loop after each cut. Done when every remaining element is load-bearing: removing any one of them turns the loop green.

### 3. Hypothesise

Rank 3–5 hypotheses before you test any of them. Make each one falsifiable by stating its prediction: "If X is the cause, then changing Y makes the bug disappear."

### 4. Probe

Test the hypotheses in rank order. Each probe tests one prediction by changing one variable. Inspect state in a REPL where you can. Otherwise log at the boundaries that tell the hypotheses apart, and tag every log line `[DEBUG-xxxx]`, with one random suffix for the whole run. For a performance bug, measure a baseline first, then bisect.

Done when a probe confirms one hypothesis: that is the root cause.

### 5. Regression test, then fix

Turn the minimised repro into a regression test at a **correct seam**: one where the test exercises the bug as it happens at the real call site, with every caller and step the bug needs.

1. Run the test and watch it go red. Keep the line of output that shows the failure.
2. Fix the root cause.
3. Run the test and watch it go green.
4. Rerun the step 1 loop on the original, unminimised scenario, and watch it go green.

If no correct seam exists, that is a finding in itself: the code's structure stops the bug being locked down. Write it under **No seam:** in the pull request description, saying what a test can't reach, and make the fix anyway.

### Done when

- [ ] The regression test drives the code path the fix changes and asserts the symptom the ticket reports, from the trigger it describes and at the severity it reports, so it goes red without the fix. Or **No seam:** in the pull request description explains why there is no regression test.
- [ ] The fix changes the root cause, not just the place where the symptom shows.
- [ ] The test command passes.
- [ ] A grep for `[DEBUG-` finds nothing, and every throwaway harness and fixture is deleted. The regression test and its fixtures stay.
- [ ] The pull request description has a **Root cause:** paragraph before **Decisions:**: the hypothesis that held, the probe that confirmed it, and the regression test's failure line from before the fix.
