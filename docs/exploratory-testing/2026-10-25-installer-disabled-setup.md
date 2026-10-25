# Installer disabled setup: issue #79 (2026-10-25)

Focused verification of [#79](https://github.com/jonbaldie/software-factory/issues/79), using the candidate `install.sh` in this commit against real GitHub configuration in [the existing sandbox](https://github.com/jonbaldie/software-factory-sandbox).

## Feedback loop and diagnosis

`uv run tests/install.py` runs the actual installer through fake GitHub. The new regression carries installer-produced variables from an explicit clear into two ordinary reinstalls and a re-enable/reinstall. Before the fix, both ordinary reinstalls failed their assertions: saved state was `{'FACTORY_TEST_COMMAND': 'make test', 'FACTORY_SETUP_COMMAND': 'npm ci'}`. Nonempty saved commands passed the control test.

The minimal reproduction needs a lockfile, an explicit clear and an ordinary reinstall. Ranked hypotheses were lost disabled intent, loss of an empty value during reads, and general disregard of saved configuration. The nonempty control ruled out the third. Preserving explicit intent in separate metadata made both reinstalls pass: deleting the setup variable alone had erased the distinction between disabled and unspecified setup.

After the fix, the installer suite passes all 35 checks, including failures reading the new metadata with and without an override, before files, labels or variables change. `uv run tests/labels.py` passes 142 scenarios, `uv run tests/pi.py` passes all 22 cases, and `bash -n install.sh` passes.

## Live replay and evidence

The sandbox had no open PRs or active Actions runs. [Reservation](https://github.com/jonbaldie/software-factory/issues/79#issuecomment-6395029917). The test used a private local clone; nothing was pushed. A local-only committed `package-lock.json` containing `{}` supplied the installer's lockfile-presence fixture. No dependency installation was needed or attempted.

The first attempt lacked that fixture and stopped at the fresh-detection assertion: the sandbox has no lockfile. Its settings were restored. [Initial diagnostic](2026-10-25-evidence/issue79-initial-attempt.log).

The successful [full installer and GitHub readback transcript](2026-10-25-evidence/issue79-install.log) records these steps:

1. With setup and disabled metadata absent, save `FACTORY_TEST_COMMAND=node --test`; ordinary install detects `FACTORY_SETUP_COMMAND=npm ci`.
2. `bash /path/to/candidate/install.sh --setup-command ''` removes the setup variable and saves `FACTORY_SETUP_DISABLED=true`.
3. Run the installer normally twice. Each independent real GitHub readback shows only the disabled marker and the unchanged test command.
4. `--setup-command 'printf setup-enabled'` saves that command and removes the marker. An ordinary reinstall retains the custom command and test command.

Each invocation exited successfully. Assertions used fresh `gh variable list --json name,value` results, not installer status messages.

## Agent-stage behavior and limits

No workflow changes are needed: implement, review and fix already bind `SETUP_COMMAND` to `vars.FACTORY_SETUP_COMMAND`, and their setup steps require `env.SETUP_COMMAND != ''`. The live disabled state has no setup variable, so these existing guards skip setup. The marker is installer-only; no sentinel shell command runs in agent stages. This focused pass did not dispatch agents or rerun the push/merge smoke suite; triggers and queues are unchanged.

## Cleanup

All sandbox variables, labels and workflow permissions were compared with their original snapshots and restored exactly, including the original `FACTORY_TEST_COMMAND=npm test` and absent setup/disabled variables. No remote test issues, PRs, branches or workflow runs were created. The local fixture clone and test driver were removed. No Docker containers, images or volumes were created.
