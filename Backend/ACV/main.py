# Manage file path, loops & outputs
import pandas as pd
import os

# Import our custom modules
from data_utils import standardize_column_names, sanitize_sensor_data, calculate_train_ambient_ref
from analytics import calculate_shortfall_and_rank, combined_borda_rank
from validation import permutation_test, cooling_delivered_ranking  # NEW

AMBIENT_QUANTILE = 0.5  # was a fixed AMBIENT_THRESHOLD = 26.0 — now per-file adaptive


def load_and_prepare(filepath):
    """Shared loading + cleaning, used by both scoring and validation checks
    so they always see the exact same dataframe."""
    df_preview = pd.read_excel(filepath, nrows=0)
    if len(df_preview.columns) > 100:
        return None, "Skipped (Rich Schema)"

    raw_df = pd.read_excel(filepath)
    df = standardize_column_names(raw_df)
    df = sanitize_sensor_data(df)
    df = calculate_train_ambient_ref(df)
    return df, "Loaded"


def process_acv_file(filepath, ambient_quantile=AMBIENT_QUANTILE):
    """Universal pipeline to load, clean, and score a single ACV Excel file."""
    try:
        df, status_msg = load_and_prepare(filepath)
        if df is None:
            return None, status_msg
        ranked_string = calculate_shortfall_and_rank(df, ambient_quantile)
        return ranked_string, "Processed"
    except Exception as e:
        return None, f"Error: {str(e)}"


def evaluate_training_set(train_dir, labels_file, ambient_quantile=AMBIENT_QUANTILE):
    print("\n--- Evaluating Training Set ---")
    labels_df = pd.DataFrame()
    if os.path.exists(labels_file):
        labels_df = pd.read_csv(labels_file)

    files = [os.path.join(train_dir, f"acv_case_0{i}.xlsx") for i in range(1, 7)]

    for filepath in files:
        if not os.path.exists(filepath):
            continue

        filename = os.path.basename(filepath)
        ranked_string, status_msg = process_acv_file(filepath, ambient_quantile)

        if ranked_string is None:
            print(f"{filename} -> {status_msg}")
            continue

        predicted_fault = ranked_string.split('|')[0]
        actual_fault = "Unknown"

        if not labels_df.empty and 'filename' in labels_df.columns:
            match = labels_df[labels_df['filename'] == filename]
            if not match.empty:
                actual_fault = str(match['faulty_car'].values[0]).zfill(2)

        status = "PASS" if predicted_fault == actual_fault else ("FAIL" if actual_fault != "Unknown" else "UNVERIFIED")
        print(f"{filename} -> Predicted: {predicted_fault} | Actual: {actual_fault} | {status} | Full Rank: {ranked_string}")


def run_validation_checks(test_file, top_pick, ambient_quantile=AMBIENT_QUANTILE, n_permutations=500):
    """NEW: sanity-checks on the test file's top prediction before submitting —
    a permutation test (is the margin statistically meaningful?) and an independent
    cross-check feature (does a differently-derived signal agree?).
    n_permutations=500 for quick iteration; bump to 2000+ before finalizing."""
    print("\n--- Validation Checks on Test Prediction ---")
    df, status_msg = load_and_prepare(test_file)
    if df is None:
        print(f"Could not run checks: {status_msg}")
        return

    observed, p_value = permutation_test(df, top_pick, n_permutations=n_permutations,
                                          demand_quantile=ambient_quantile)
    if observed is None:
        print("Permutation test could not be run (check column names / gating).")
    else:
        print(f"Permutation test — car {top_pick}: observed residual = {observed:.3f}°C, "
              f"p-value = {p_value:.4f}  (n={n_permutations})")

    cross_check = cooling_delivered_ranking(df, demand_quantile=ambient_quantile)
    print("Cross-check ranking (independent 'cooling delivered' feature):")
    print(cross_check.to_string())
    agrees = cross_check.index[0] == top_pick
    print(f"Cross-check top pick {'MATCHES' if agrees else 'DISAGREES WITH'} "
          f"primary top pick (car {top_pick}).")


def generate_submission(test_file, output_path, ambient_quantile=AMBIENT_QUANTILE):
    print("\n--- Generating Test Predictions ---")
    if not os.path.exists(test_file):
        print(f"Test file not found at: {test_file}")
        return

    filename = os.path.basename(test_file)
    try:
        df, status_msg = load_and_prepare(test_file)
        if df is None:
            print(f"Failed to process test file: {status_msg}")
            return
        # NEW: use the Borda-combined ranking (shortfall + cooling-delivered) as the
        # submitted prediction, rather than the single shortfall feature alone.
        ranked_string, features_agree = combined_borda_rank(df, ambient_quantile)
    except Exception as e:
        print(f"Failed to process test file: Error: {str(e)}")
        return

    if ranked_string:
        submission_df = pd.DataFrame({'file_id': [filename], 'ranked_cars': [ranked_string]})
        submission_df.to_csv(output_path, index=False)
        print(f"Successfully ranked {filename}: {ranked_string}")
        print(f"Saved submission file to: {output_path}")
        if not features_agree:
            print("WARNING: shortfall and cooling-delivered features disagree on the top "
                  "pick — this file's prediction is less confident than usual, worth a manual look.")

        # run the sanity checks on the top pick before you trust the file
        top_pick = ranked_string.split('|')[0]
        run_validation_checks(test_file, top_pick, ambient_quantile)
    else:
        print("Failed to process test file: empty ranking produced")


if __name__ == "__main__":
    # --- Configuration ---
    CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
    TRAIN_DIR = os.path.join(CURRENT_DIR, "Train")
    TEST_FILE = os.path.join(CURRENT_DIR, "Test", "acv_test_case.xlsx")
    LABELS_FILE = os.path.join(CURRENT_DIR, "Train_Labels.csv")
    OUTPUT_CSV = os.path.join(CURRENT_DIR, "acv_predictions.csv")

    # --- Execution ---
    evaluate_training_set(TRAIN_DIR, LABELS_FILE)
    generate_submission(TEST_FILE, OUTPUT_CSV)