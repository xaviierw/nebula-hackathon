from __future__ import annotations

import sys
from pathlib import Path
import unittest

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from ACV.core.errors import AcvInputError
from app.schemas.acv import AcvResult
from app.subsystems.acv.runner import AcvRunner


class AcvRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.runner = AcvRunner()
        cls.runner.load()
        if not cls.runner.available:
            raise AssertionError(cls.runner.unavailable_reason)

    def test_representative_excel_recording(self) -> None:
        path = BACKEND_DIR / "ACV" / "prediction" / "Test" / "acv_test_case.xlsx"
        result = self.runner.run(path.read_bytes(), path.name)

        AcvResult.model_validate(result)
        self.assertEqual(
            result["ranked_cars"],
            ["01", "03", "04", "08", "07", "06", "02", "05"],
        )
        self.assertEqual(set(result["scores"]), set(result["ranked_cars"]))

    def test_valid_csv_recording(self) -> None:
        header = (
            "car_01_ambient_temp,car_01_indoor_temp,car_01_cooling_setpoint,"
            "car_01_running_mode,car_01_valid_status,car_02_ambient_temp,"
            "car_02_indoor_temp,car_02_cooling_setpoint,car_02_running_mode,"
            "car_02_valid_status\n"
        )
        row = (
            "30,29,24,Automatic Cooling,Valid,"
            "30,25,24,Automatic Cooling,Valid\n"
        )
        result = self.runner.run((header + row * 4).encode(), "recording.csv")
        self.assertEqual(result["ranked_cars"], ["01", "02"])

    def test_incomplete_schema_is_rejected(self) -> None:
        with self.assertRaisesRegex(AcvInputError, "at least two cars"):
            self.runner.run(b"car_01_indoor_temp\n25\n", "incomplete.csv")

    def test_no_usable_cooling_observations_are_rejected(self) -> None:
        raw = (
            "car_01_ambient_temp,car_01_indoor_temp,car_01_cooling_setpoint,"
            "car_01_running_mode,car_01_valid_status,car_02_ambient_temp,"
            "car_02_indoor_temp,car_02_cooling_setpoint,car_02_running_mode,"
            "car_02_valid_status\n"
            "30,29,24,Stop,Valid,30,25,24,Stop,Valid\n"
        ).encode()
        with self.assertRaisesRegex(AcvInputError, "no usable cooling observations"):
            self.runner.run(raw, "stopped.csv")


if __name__ == "__main__":
    unittest.main()
