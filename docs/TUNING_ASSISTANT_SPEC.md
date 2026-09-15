# Tuning Assistant specification

Status: interactive beta for the `0.7` development branch.

## Product goal

Turn calibration into a guided workflow that remembers what has already been
verified, performs the calculations and shows the exact value that should be
changed. It must not pretend that a setting has been written to OrcaSlicer.

The default workflow is quality-first and inspired by Ellis' Print Tuning
Guide. Orca's own calibration models and terminology are used where practical.
The guide is referenced and paraphrased, not copied.

## Current API boundary

The current nightly plugin bindings expose preset values as read-only data.
They do not expose a supported method to open Orca's calibration dialogs or
save edited printer/filament profiles. Version 0.7 must therefore:

- read the active printer, process, nozzle and filament values;
- guide the user to the appropriate Orca calibration command;
- calculate and validate the result;
- show a before/after profile diff for manual confirmation;
- never claim that Orca or Klipper configuration was changed.

Automatic profile writes can be added later only if Orca exposes a documented
write API. Directly editing Orca profile files is out of scope.

## Default workflow: quality first

### Foundation — printer and mechanics

1. Mechanical preflight: loose fasteners, grub screws, nozzle condition,
   thermistor type and unobstructed extrusion.
2. PID tuning for the hotend and bed when hardware has changed or temperature
   control is unstable. This is printer maintenance, not a per-filament test.
3. Extruder calibration:
   - Klipper: calculate `rotation_distance`.
   - Marlin/RepRapFirmware: calculate E-steps.
   - Repeat measurements must agree; otherwise diagnose the extruder or hotend
     before continuing.
4. Build surface and first-layer squish.
5. Klipper Input Shaper when an accelerometer is configured.

These are printer-level results. They must not be stored as filament tuning.

### Filament profile

6. Temperature, when the material/hotend combination is not already proven.
7. Pressure Advance using Orca's pattern method by default.
8. Flow Ratio:
   - prefer Orca's Archimedean Chords + YOLO method;
   - retain the legacy two-pass calculator;
   - judge the broad centre area and avoid treating corner accumulation as the
     primary flow signal.
9. Cooling and minimum layer time.
10. Retraction, after Pressure Advance and Flow Ratio.
11. Maximum volumetric speed as an advanced/performance step. Report both the
   measured failure threshold and a separately selected safety margin.

Detailed motion-limit tuning, VFA and dimensional compensation are later
modules. Basic Klipper Input Shaper is included in the full-calibration beta.

## Wizard state

Each run should track:

- printer preset and firmware family;
- extruder type: direct drive or Bowden;
- nozzle diameter;
- filament preset, material, brand and optional spool/color note;
- current step, completed steps and skipped steps with reason;
- original value, observation, calculated value and confirmation state;
- timestamp and plugin version.

Results should remain local. A later design can decide how persistence works.

## Calculation contract

The dependency-free functions currently live in `orca_ai.py` so the plugin
remains installable as one file:

- `calculate_rotation_distance(current, requested, actual)`
- `calculate_e_steps(current, requested, actual)`
- `calculate_flow_ratio(current, modifier, method)`
- `calculate_pressure_advance(start, step, measured_height)`
- `calculate_max_volumetric_speed(start, step, measured_height, margin)`
- `volumetric_speed_to_linear_speed(flow, layer_height, line_width)`

Every input must be finite and physically valid. UI formatting must not destroy
the unrounded value; rounding is presentation only.

## MVP interface

Add a `Tuning` view beside chat with:

1. active printer/nozzle/filament summary;
2. workflow progress;
3. one instruction and one observation form at a time;
4. calculated result with the formula visible on demand;
5. a profile diff such as `filament_flow_ratio: 0.98 → 0.99`;
6. `Confirm result`, `Repeat test` and `Skip` actions.

Image interpretation is useful later, but manual selection of the winning
sample is the reliable MVP.

## Sources and attribution

- [Ellis' Print Tuning Guide](https://ellis3dp.com/Print-Tuning-Guide/)
- [Ellis: Extruder Calibration](https://ellis3dp.com/Print-Tuning-Guide/articles/extruder_calibration.html)
- [Ellis: Pressure Advance Pattern Method](https://ellis3dp.com/Print-Tuning-Guide/articles/pressure_linear_advance/pattern_method.html)
- [Ellis: Extrusion Multiplier](https://ellis3dp.com/Print-Tuning-Guide/articles/extrusion_multiplier.html)
- [Ellis: Maximum Volumetric Flow](https://ellis3dp.com/Print-Tuning-Guide/articles/determining_max_volumetric_flow_rate.html)
- [OrcaSlicer Calibration Guide](https://github.com/OrcaSlicer/OrcaSlicer/wiki/calibration_guide)
- [OrcaSlicer Flow Ratio Calibration](https://github.com/OrcaSlicer/OrcaSlicer/wiki/flow_ratio_calib)
- [OrcaSlicer Pressure Advance](https://github.com/OrcaSlicer/OrcaSlicer/wiki/pressure_advance_calib)
- [OrcaSlicer Max Volumetric Speed](https://github.com/OrcaSlicer/OrcaSlicer/wiki/volumetric_speed_calib)
- [Klipper PID_CALIBRATE and SAVE_CONFIG](https://www.klipper3d.org/G-Codes.html#pid_calibrate)
