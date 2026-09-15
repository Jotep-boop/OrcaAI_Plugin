import importlib
import math
import sys
import types
import unittest


def _load_plugin_with_orca_stub():
    orca = types.ModuleType("orca")
    orca.pages = types.SimpleNamespace(PagesPluginCapabilityBase=object)
    orca.slicing = types.SimpleNamespace(SlicingPipelineCapabilityBase=object)
    orca.base = object
    orca.plugin = lambda cls: cls
    orca.register_capability = lambda capability: None
    sys.modules["orca"] = orca
    return importlib.import_module("orca_ai")


plugin = _load_plugin_with_orca_stub()


class TuningMathTests(unittest.TestCase):
    def test_klipper_rotation_distance(self):
        self.assertAlmostEqual(
            plugin.calculate_rotation_distance(40, 100, 98), 39.2
        )

    def test_marlin_e_steps(self):
        self.assertAlmostEqual(
            plugin.calculate_e_steps(420, 100, 98), 428.57142857142856
        )

    def test_orca_yolo_flow_ratio(self):
        self.assertAlmostEqual(
            plugin.calculate_flow_ratio(0.98, 0.01, "yolo"), 0.99
        )

    def test_orca_two_pass_flow_ratio(self):
        self.assertAlmostEqual(
            plugin.calculate_flow_ratio(0.98, 5, "two_pass"), 1.029
        )

    def test_pressure_advance_tower(self):
        self.assertAlmostEqual(
            plugin.calculate_pressure_advance(0, 0.002, 8), 0.016
        )

    def test_max_volumetric_speed_and_margin(self):
        result = plugin.calculate_max_volumetric_speed(5, 0.5, 19, 15)
        self.assertAlmostEqual(result["measured_mm3_s"], 14.5)
        self.assertAlmostEqual(result["recommended_mm3_s"], 12.325)
        self.assertEqual(result["safety_margin_percent"], 15)

    def test_volumetric_to_linear_speed(self):
        self.assertAlmostEqual(
            plugin.volumetric_speed_to_linear_speed(24, 0.2, 0.4), 300
        )

    def test_wizard_dispatcher_formats_profile_results(self):
        rotation = plugin.tuning_calculation(
            "rotation_distance",
            {"current": "40", "requested": "100", "actual": "98"},
        )
        self.assertEqual(rotation["formatted"], "39.200000")
        self.assertEqual(rotation["profile_key"], "rotation_distance")

        max_flow = plugin.tuning_calculation(
            "max_flow",
            {"start": "5", "step": "0.5", "height": "19", "margin": "15"},
        )
        self.assertEqual(max_flow["formatted"], "12.32 mm³/s")
        self.assertEqual(max_flow["measured_formatted"], "14.50 mm³/s")

    def test_wizard_dispatcher_rejects_unknown_or_missing_values(self):
        with self.assertRaises(ValueError):
            plugin.tuning_calculation("unknown", {})
        with self.assertRaises(ValueError):
            plugin.tuning_calculation("rotation_distance", None)

    def test_rejects_non_finite_and_impossible_inputs(self):
        with self.assertRaises(ValueError):
            plugin.calculate_rotation_distance(40, 100, math.inf)
        with self.assertRaises(ValueError):
            plugin.calculate_e_steps(420, 100, 0)
        with self.assertRaises(ValueError):
            plugin.calculate_flow_ratio(0.98, 1, "unknown")
        with self.assertRaises(ValueError):
            plugin.calculate_max_volumetric_speed(5, 0.5, 19, 100)


if __name__ == "__main__":
    unittest.main()
