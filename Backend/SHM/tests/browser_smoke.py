"""Optional live-browser check. Start API and Vite first; not part of pytest.

python Backend/SHM/tests/browser_smoke.py
Requires playwright and an installed Microsoft Edge (or set SHM_BROWSER_CHANNEL).
Uses the supplied local Test directory and writes only ignored outputs/app_smoke.
"""
import csv
import math
import os
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

HERE = Path(__file__).resolve().parents[1]
OUTPUT = HERE/'outputs/app_smoke'


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    files = sorted((HERE/'dataset_shm/SHM/Test').glob('*.csv'))
    assert len(files) == 16
    with sync_playwright() as p:
        browser = p.chromium.launch(channel=os.environ.get('SHM_BROWSER_CHANNEL', 'msedge'), headless=True)
        page = browser.new_page(viewport={'width': 1280, 'height': 1000}, accept_downloads=True)
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto('http://127.0.0.1:5173/subsystem/shm')
        page.get_by_role('button', name='Log In').click()
        page.goto('http://127.0.0.1:5173/subsystem/shm')
        chooser = page.get_by_label('Choose stress CSV files', exact=True)
        chooser.set_input_files([str(file) for file in files])
        page.get_by_role('button', name='Estimate fatigue damage').click()
        download = page.get_by_role('button', name='Download shm_predictions.csv')
        expect(download).to_be_enabled(timeout=180000)
        assert page.get_by_role('cell', name='Complete', exact=True).count() == 16
        page.screenshot(path=str(OUTPUT/'results.png'), full_page=True)
        with page.expect_download() as event:
            download.click()
        assert event.value.suggested_filename == 'shm_predictions.csv'
        output_csv = OUTPUT/'shm_predictions.csv'
        event.value.save_as(output_csv)
        with output_csv.open(newline='') as stream:
            reader = csv.DictReader(stream)
            assert reader.fieldnames == ['file_id', 'prediction']
            rows = list(reader)
        assert len(rows) == 16 and {r['file_id'] for r in rows} == {f.name for f in files}
        with (HERE/'outputs/grouped/final/shm_predictions.csv').open(newline='') as stream:
            expected = {r['file_id']: float(r['prediction']) for r in csv.DictReader(stream)}
        for row in rows:
            assert math.isclose(float(row['prediction']), expected[row['file_id']], rel_tol=1e-12)

        # Replacing inputs invalidates the successful batch; malformed CSVs
        # cannot lead to a silently partial competition submission.
        chooser.set_input_files({'name': 'bad.csv', 'mimeType': 'text/csv', 'buffer': b'stress\n1\n'})
        expect(download).to_be_disabled()
        page.get_by_role('button', name='Estimate fatigue damage').click()
        expect(page.get_by_role('alert')).to_contain_text('581,120', timeout=30000)
        expect(download).to_be_disabled()

        # Exercise native drag/drop and a small viewport.
        page.set_viewport_size({'width': 390, 'height': 844})
        transfer = page.evaluate_handle("""() => {
            const data = new DataTransfer();
            data.items.add(new File(['1\\n2\\n'], 'dropped.csv', {type: 'text/csv'}));
            return data;
        }""")
        page.get_by_role('region', name='Upload stress recordings').dispatch_event('drop', {'dataTransfer': transfer})
        expect(page.get_by_role('rowheader', name='dropped.csv')).to_be_visible()
        page.screenshot(path=str(OUTPUT/'mobile.png'), full_page=True)
        assert not errors, errors
        browser.close()
    print('Browser passed: 16 real uploads, exact CSV parity, invalid input, stale-download protection, drag/drop, mobile layout.')


if __name__ == '__main__':
    main()
