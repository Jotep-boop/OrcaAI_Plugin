# Changelog

## 0.7.0-beta.1

- Add a separate Tuning tab with an 11-step, resumable calibration workflow.
- Add conditional Klipper PID tuning for both hotend and bed, using target
  temperatures from the active Orca filament profile.
- Add printer-level mechanical, extruder, first-layer and Input Shaper steps.
- Add filament-level temperature, Pressure Advance, Flow Ratio, cooling,
  retraction and maximum volumetric-flow steps.
- Add validated calculators for rotation distance, E-steps, Pressure Advance,
  Flow Ratio and maximum volumetric flow.
- Keep all configuration writes manual and show the intended destination for
  each calculated value.

## 0.6.0

- Add beginner, experienced and expert guidance levels.
- Make experienced guidance the default and suppress routine slicer reminders.
- Add quick-check and deep-analysis response modes.
- Give project checks a clear REDO, KONTROLLERA or STOPP status.
- Limit quick checks to one compact line per captured plate and at most three actions.

## 0.5.6

- Distinguish Orca objects and instances from disconnected physical parts.
- Review all captured build plates in project-wide checks.
- Capture per-plate layer, height, support and placement context.
- Correctly treat slicing bounds as object-local coordinates.
- Add slicing-observer diagnostics and active-process detection.
- Improve compact Markdown rendering and Swedish response guidance.
- Validate API keys before HTTP header construction.

## Earlier proof-of-concept milestones

- `0.4`: safer speed, cooling and volumetric-flow analysis.
- `0.3`: multi-plate awareness and narrow-layout Markdown output.
- `0.2`: OpenAI Responses API chat integration.
- `0.1`: embedded OrcaSlicer page and project-context prototype.
