# Contributing

Small project, small rules.

- Zero runtime dependencies. Please keep it that way (standard library only).
- Run the tests: `python -m unittest discover -s tests`
- Add a test with every change. Bug reports with a `.jsonl` run file are very welcome (remove any private data first: runs store tool arguments and results).
- Real SDK adapters (OpenAI, Anthropic) are duck-typed. If a new SDK version breaks them, open an issue with the version number.
- Be kind. No spam, no promotion in issues.
