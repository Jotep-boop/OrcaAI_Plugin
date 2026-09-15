# Orca AI Plugin

Experimental AI assistant for OrcaSlicer. It reads the active printer,
filament, process, model and captured slicing context, then sends a compact
project summary to the OpenAI Responses API.

The plugin is read-only: it can review a project and suggest changes, but it
does not modify OrcaSlicer settings or models.

## Current status

- Version: `0.5.6`
- Tested with: OrcaSlicer `2.5.0-dev`, build
  `ac3997c0d1920dc37ebb0a093e7e4ba423a4e7ea`
- API provider: OpenAI Responses API
- UI language: Swedish

This project targets an experimental nightly plugin API. Compatibility with
other OrcaSlicer builds is not guaranteed.

## Features

- Chat panel embedded in OrcaSlicer.
- Reads active printer, process and filament profiles.
- Collects object dimensions, transformations and mesh-error counts.
- Captures layer, height and support information through a slicing-pipeline
  observer.
- Keeps separate snapshots for multiple build plates.
- Estimates requested volumetric flow for common feature types.
- Produces compact Markdown without tables for OrcaSlicer's narrow chat view.
- Keeps the API key in memory only for the current OrcaSlicer session.

## Installation

1. Download [`orca_ai.py`](orca_ai.py).
2. Install the Python file from OrcaSlicer's plugin manager.
3. Enable both **Orca AI** and **Orca AI Slice Observer**.
4. Switch the process settings to Advanced mode.
5. Search for **Slicing Pipeline Plugin** and select
   **Orca AI Slice Observer**.
6. Slice each build plate individually. The current nightly may not invoke the
   observer for every plate when using a single "slice all" action.
7. Open the Orca AI page, enter an OpenAI API key and select
   **Use this session**.

The status card should show the number of captured plates before a project-wide
review is requested.

## Privacy

When a question is submitted, the prompt includes summarized project data such
as profile values, object names, dimensions, transformations and slicing
statistics. The STL/3MF file and raw mesh geometry are not uploaded by this
plugin.

Do not commit API keys. The plugin also accepts `OPENAI_API_KEY` and
`ORCA_AI_MODEL` environment variables.

## Known limitations

- The plugin cannot currently apply setting changes.
- Final auto-brim geometry, print time and material usage are not exposed at
  the captured pipeline step.
- Build-plate origin/offset is unavailable, so edge margins still require a
  visual check.
- Orca object/instance counts are not guaranteed to equal the number of
  disconnected physical parts inside an STL.
- Slicing snapshots are held in memory and reset when the plugin is reloaded.

## Development

The plugin is a single-file OrcaSlicer Python plugin with PEP 723 metadata.
Basic syntax validation:

```bash
python3 -m py_compile orca_ai.py
```

## Disclaimer

This is an independent experimental project and is not affiliated with or
endorsed by OrcaSlicer or OpenAI. Always verify recommendations in OrcaSlicer's
Preview before starting a print.
