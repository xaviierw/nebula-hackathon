"""Inference checks: run with unittest discover; no notebook kernel or training needed."""

import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import joblib
import numpy as np
import pandas as pd
from scipy import signal, stats

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))
import predictor

class PredictorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="rail-predictor-tests-")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root = Path(cls.temp.name)
        rng = np.random.default_rng(42)
        values = rng.normal(0, 0.3, size=(10_000, 129)).astype(np.float32)
        values[:, 0] = (np.arange(10_000) // 50) % 2
        cls.frame = pd.DataFrame(values, columns=predictor.EXPECTED_HEADER)
        cls.first = cls.root / "sample_a.csv"
        cls.second = cls.root / "sample_b.CSV"
        cls.frame.to_csv(cls.first, index=False)
        other = cls.frame.copy()
        other[predictor.VIBRATION_COLUMNS["side_i"]] *= 4
        other.to_csv(cls.second, index=False)

        # Execute only the notebook's original feature definitions as a test oracle.
        # Production predictor.py never reads or executes the notebook.
        nb = json.loads((PROJECT_DIR / "Rail_Corrugation.ipynb").read_text(encoding="utf-8"))
        cell = next(c for c in nb["cells"] if c["id"] == "feature-recipe")
        cls.reference = {
            "Path": Path, "np": np, "pd": pd, "stats": stats, "signal": signal,
            "FS": 10_000, "EPSILON": 1e-12,
            "BANDS": [(0, 50), (50, 100), (100, 250), (250, 1_000), (1_000, 5_000)],
        }
        exec(compile("".join(cell["source"]), "notebook-feature-recipe", "exec"), cls.reference)

    def setUp(self):
        predictor._cached_model.cache_clear()

    def test_selected_features_match_notebook_exactly(self):
        self.assertEqual(predictor.FEATURE_CONTRACT, self.reference["FEATURE_CONTRACT"])
        for path in [self.first, self.second]:
            with self.subTest(file=path.name):
                reference = self.reference["extract_features"](path)
                actual = predictor.extract_features(path)
                self.assertEqual(list(actual), self.reference["VIBRATION_TIME_COLUMNS"])
                np.testing.assert_array_equal(
                    list(actual.values()), [reference[name] for name in predictor.FEATURE_COLUMNS],
                )

    def test_real_recordings_match_notebook_features_and_predictions(self):
        labels_path = PROJECT_DIR / "Dataset" / "Train_Labels.csv"
        if not labels_path.is_file():
            self.skipTest("Local training dataset is optional for these integration checks.")
        labels = pd.read_csv(labels_path)
        model = predictor.load_rail_model()["model"]
        # One recording from each real class covers distinct operating conditions.
        for label in predictor.CLASSES:
            filename = labels.loc[labels["label"] == label, "filename"].iloc[0]
            path = labels_path.parent / "Train" / filename
            with self.subTest(label=label, file=filename):
                reference = self.reference["extract_features"](path)
                actual = predictor.extract_features(path)
                np.testing.assert_array_equal(
                    list(actual.values()), [reference[name] for name in predictor.FEATURE_COLUMNS],
                )
                X = pd.DataFrame([reference]).loc[:, predictor.FEATURE_COLUMNS]
                self.assertEqual(predictor.predict_file(path), {
                    "file_id": filename, "prediction": str(model.predict(X)[0]),
                })

    def test_constant_signals_keep_the_notebook_fallback(self):
        frame = pd.DataFrame(np.zeros((10_000, 129), dtype=np.float32), columns=predictor.EXPECTED_HEADER)
        with patch.object(predictor, "read_recording", return_value=frame):
            features = predictor.extract_features(self.first)
        self.assertEqual(len(features), 15)
        self.assertTrue(all(value == 0.0 for value in features.values()))

    def test_single_batch_and_repeated_predictions_agree_without_training(self):
        with patch.object(predictor.ExtraTreesClassifier, "fit", side_effect=AssertionError("Must not train")):
            first = predictor.predict_file(self.first)
            second = predictor.predict_file(self.second)
            batch = predictor.predict_files(path for path in [self.second, self.first])
            self.assertEqual(batch.columns.tolist(), ["file_id", "prediction"])
            self.assertEqual(batch.to_dict("records"), [second, first])
            self.assertEqual(predictor.predict_file(self.first), first)
        self.assertIn(first["prediction"], predictor.CLASSES)
        # The DataFrame is directly suitable for the required two-column CSV.
        exported = pd.read_csv(io.StringIO(batch.to_csv(index=False)))
        pd.testing.assert_frame_equal(exported, batch)

    def test_model_is_loaded_once_for_repeated_requests(self):
        with patch.object(predictor.joblib, "load", wraps=joblib.load) as load:
            predictor.predict_file(self.first)
            predictor.predict_files([self.second, self.first])
        self.assertEqual(load.call_count, 1)

    def test_analysis_evidence_matches_notebook_and_preserves_submission(self):
        for path in [self.first, self.second]:
            with self.subTest(file=path.name):
                reference = self.reference["extract_features"](path)
                with patch.object(predictor, "read_recording", wraps=predictor.read_recording) as read:
                    analysis = predictor.analyse_file(path)
                    self.assertEqual(read.call_count, 1)
                self.assertEqual(
                    {key: analysis[key] for key in ("file_id", "prediction")},
                    predictor.predict_file(path),
                )
                evidence = analysis["evidence"]
                self.assertEqual(evidence["samples_per_sensor"], 10_000)
                self.assertEqual(evidence["column_count"], 129)
                self.assertEqual(evidence["duration_seconds"], 1.0)
                self.assertEqual(evidence["vibration_sensors_per_side"], 32)
                self.assertEqual(evidence["feature_count"], 15)
                for side in ["side_i", "side_ii"]:
                    for metric in ["rms_median", "rms_max", "abs_peak_max"]:
                        self.assertEqual(evidence[side][metric], reference[f"vibration__{side}__{metric}"])
                # Evidence must be JSON-safe, while submission helpers stay two-column.
                json.dumps(analysis, allow_nan=False)
                self.assertEqual(predictor.predict_files([path]).columns.tolist(), ["file_id", "prediction"])

    def test_analysis_measurements_follow_the_actual_side_and_handle_zero_signals(self):
        first = predictor.analyse_file(self.first)["evidence"]
        second = predictor.analyse_file(self.second)["evidence"]
        for metric in ["rms_median", "rms_max", "abs_peak_max"]:
            self.assertAlmostEqual(second["side_i"][metric], first["side_i"][metric] * 4)
            self.assertEqual(second["side_ii"][metric], first["side_ii"][metric])
        frame = pd.DataFrame(np.zeros((10_000, 129), dtype=np.float32), columns=predictor.EXPECTED_HEADER)
        with patch.object(predictor, "read_recording", return_value=frame):
            analysis = predictor.analyse_file(self.first)
        for side in ["side_i", "side_ii"]:
            self.assertTrue(all(value == 0.0 for value in analysis["evidence"][side].values()))
        json.dumps(analysis, allow_nan=False)

    def test_analysis_rejects_invalid_input_instead_of_producing_evidence(self):
        path = self.root / "invalid_analysis.csv"
        path.write_text("wrong,header\n1,2\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            predictor.analyse_file(path)

    def test_replacing_model_at_same_path_refreshes_cache(self):
        path = self.root / "replaceable.joblib"
        bundle = predictor.load_rail_model()
        joblib.dump(bundle, path, compress=0)
        with patch.object(predictor.joblib, "load", wraps=joblib.load) as load:
            predictor.load_rail_model(path)
            replacement = dict(bundle, test_marker="a different saved copy")
            joblib.dump(replacement, path, compress=0)
            self.assertEqual(predictor.load_rail_model(path)["test_marker"], replacement["test_marker"])
            self.assertEqual(load.call_count, 2)

    def test_fresh_process_works_without_notebook_or_training_data(self):
        # Ship only the production module and artifact to an otherwise empty folder.
        import shutil
        isolated = self.root / "standalone"
        (isolated / "models").mkdir(parents=True)
        shutil.copy2(PROJECT_DIR / "predictor.py", isolated / "predictor.py")
        shutil.copy2(predictor.DEFAULT_MODEL_PATH, isolated / "models" / "rail_corrugation.joblib")
        code = (
            "import json, sys; from pathlib import Path; "
            "sys.path.insert(0, sys.argv[1]); import predictor; "
            "assert not (Path(sys.argv[1]) / 'Dataset').exists(); "
            "assert not (Path(sys.argv[1]) / 'Rail_Corrugation.ipynb').exists(); "
            "print(json.dumps(predictor.predict_file(sys.argv[2])))"
        )
        # Different working directory also checks that model lookup is module-relative.
        completed = subprocess.run(
            [sys.executable, "-c", code, str(isolated), str(self.first)],
            cwd=self.root, capture_output=True, text=True, check=True,
        )
        self.assertEqual(json.loads(completed.stdout), predictor.predict_file(self.first))

    def test_empty_batch_has_headers_and_needs_no_model(self):
        result = predictor.predict_files([], model_path=self.root / "missing.joblib")
        self.assertTrue(result.empty)
        self.assertEqual(result.columns.tolist(), ["file_id", "prediction"])

    def test_duplicate_filenames_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "unique"):
            predictor.predict_files([self.first, self.first])
        import shutil
        folder = self.root / "another_folder"
        folder.mkdir()
        duplicate = folder / self.first.name
        shutil.copy2(self.first, duplicate)
        with self.assertRaisesRegex(ValueError, "unique"):
            predictor.predict_files([self.first, duplicate])

    def test_batch_requires_sequence_and_rejects_invalid_member(self):
        with self.assertRaisesRegex(TypeError, "sequence"):
            predictor.predict_files(str(self.first))
        bad = self.root / "bad_batch_member.csv"
        bad.write_text("wrong,header\n1,2\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            predictor.predict_files([self.first, bad])

    def test_missing_files_wrong_extensions_and_missing_model(self):
        with self.assertRaises(FileNotFoundError):
            predictor.predict_file(self.root / "absent.csv")
        with self.assertRaises(FileNotFoundError):
            predictor.predict_file(self.root)
        with self.assertRaisesRegex(ValueError, "CSV"):
            predictor.predict_file(PROJECT_DIR / "README.md")
        with self.assertRaises(FileNotFoundError):
            predictor.predict_file(self.first, model_path=self.root / "absent.joblib")

    def test_bad_shapes_headers_and_nonfinite_values(self):
        # Shape and header faults exercise the CSV reader using actual files.
        cases = {
            "short": self.frame.iloc[:-1],
            "long": pd.concat([self.frame, self.frame.iloc[:1]], ignore_index=True),
            "missing_column": self.frame.iloc[:, :-1],
            "reordered": self.frame.iloc[:, ::-1],
            "wrong_name": self.frame.rename(columns={predictor.EXPECTED_HEADER[1]: "unknown"}),
            "duplicate_header": self.frame.rename(columns={predictor.EXPECTED_HEADER[1]: predictor.EXPECTED_HEADER[0]}),
        }
        for name, value in [("missing_value", np.nan), ("infinite_value", np.inf)]:
            frame = self.frame.copy()
            frame.iloc[0, 1] = value
            cases[name] = frame
        for name, frame in cases.items():
            with self.subTest(case=name):
                path = self.root / f"{name}.csv"
                frame.to_csv(path, index=False)
                with self.assertRaises(ValueError):
                    predictor.predict_file(path)

    def test_malformed_empty_nonnumeric_and_extra_fields(self):
        header = ",".join(predictor.EXPECTED_HEADER) + "\n"
        valid_row = ",".join(["0"] * 129) + "\n"
        cases = {
            "empty": "",
            "nonnumeric": header + "not-a-number," + ",".join(["0"] * 128) + "\n",
            "unclosed_quote": header + '"unfinished\n',
            "extra_field": header + ",".join(["0"] * 130) + "\n" + valid_row * 9999,
        }
        for name, text in cases.items():
            with self.subTest(case=name):
                path = self.root / f"{name}.csv"
                path.write_text(text, encoding="utf-8")
                with self.assertRaises(ValueError):
                    predictor.predict_file(path)

    def test_incompatible_model_bundle_is_rejected(self):
        bundle = predictor.load_rail_model()
        cases = {
            "format": dict(bundle, format_version=999),
            "recipe": dict(bundle, feature_contract={}),
            "feature_order": dict(bundle, feature_columns=list(reversed(predictor.FEATURE_COLUMNS))),
            "classes": dict(bundle, classes=["Normal"]),
            "unfitted": dict(bundle, model=predictor.ExtraTreesClassifier()),
            "versions": dict(bundle, versions=dict(bundle["versions"], numpy="0.0.0")),
        }
        for name, bad in cases.items():
            with self.subTest(case=name), self.assertRaises(ValueError):
                predictor._validate_bundle(bad)
        with self.assertRaises(ValueError):
            predictor._validate_bundle(None)

    def test_corrupt_model_reports_a_loading_error(self):
        path = self.root / "corrupt.joblib"
        path.write_bytes(b"this is not a saved model")
        with self.assertRaisesRegex(ValueError, "Could not load"):
            predictor.load_rail_model(path)


if __name__ == "__main__":
    unittest.main()
