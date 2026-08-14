# Contributors Guide

Thank you for wanting to contribute!
Development of Jellybench and the hardware server has slowed down considerably, but is still ongoing.
We have a GitHub Project to track progress. A major rewrite of the client is currently underway in [#109](https://github.com/BotBlake/jellybench_py/pull/109), so incoming PRs should target the `code-cleanup` branch instead.

## Developer Documentation

`jellybench_py` offers a few development-specific features. Some of them are not documented in the README and do not appear in the help menu.
This is intended to prevent end users from abusing them to manipulate uploaded data.
However, these commands can help speed up development, so they are documented here.

> **Note:** All of these options only take effect when the `--debug` flag is set.

| Argument | Parameters | Description | Status |
| --- | --- | --- | --- |
| `--ignorehash` | None | Ignores checksum mismatches. | Active |
| `--server` | `{Path/to/tests.json}` | Provides local tests instead of a server URL. | Currently unavailable |
| `--override-platform` | `{Platform Name}` | Overrides the detected platform. | Active |
