# Contributing

This project targets an experimental OrcaSlicer nightly plugin API. When
reporting a problem, include:

- OrcaSlicer version and full build SHA.
- Plugin version.
- Whether **Orca AI Slice Observer** was selected in the active process.
- The observer status shown in the plugin.
- A redacted copy of the answer or error message.

Never include an OpenAI API key, private model files or proprietary 3MF/STL
files in an issue.

Before proposing a code change, run:

```bash
python3 -m py_compile orca_ai.py
```
