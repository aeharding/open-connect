"""Clock bounds retain known offsets despite asymmetric query delays."""

import unittest

from open_connect.clock_reference import bounds


class ClockReferenceTests(unittest.TestCase):
    def test_asymmetric_delay_and_quantization_preserve_the_known_epoch(self):
        exchanges = [
            {"before_s": 1010.10, "after_s": 1013.20, "uptime_s": 10.11},
            {"before_s": 1014.10, "after_s": 1017.30, "uptime_s": 17.29},
            {"before_s": 1020.121, "after_s": 1020.124, "uptime_s": 20.12},
        ]
        result = bounds(exchanges)
        self.assertLessEqual(result["kernel_zero_host_lower_s"], 1000)
        self.assertGreaterEqual(result["kernel_zero_host_upper_s"], 1000)
        self.assertLess(result["width_s"], 0.024)

    def test_clock_steps_and_invalid_inputs_are_not_silently_averaged(self):
        for data in (
            [],
            [{"before_s": 3, "after_s": 2, "uptime_s": 1}],
            [
                {"before_s": 100, "after_s": 100.001, "uptime_s": 1},
                {"before_s": 200, "after_s": 200.001, "uptime_s": 1},
            ],
        ):
            with self.assertRaises(ValueError):
                bounds(data)
