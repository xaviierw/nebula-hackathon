"""Real browser smoke test; --simulated-auth uses test-only auth/Firestore mocks.

Start Vite first. Live mode also needs the shared API and local SHM_TEST_EMAIL /
SHM_TEST_PASSWORD. Simulation intercepts Firebase JS only in this browser and
sends HTTP to a temporary instance of the shared app; production has no bypass.
"""
import argparse
from contextlib import ExitStack
import csv
import re
import sys
import socket
import threading
import time
from unittest.mock import patch
import math
import os
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

HERE = Path(__file__).resolve().parents[1]
OUTPUT = HERE/'outputs/app_smoke'
sys.path.insert(0, str(HERE.parent))


def simulated_api(stack):
    import uvicorn
    from fastapi.middleware.cors import CORSMiddleware
    import main as shared_main
    from app.firebase import get_db
    from app.services import cache, datasets, runs, users

    stack.enter_context(patch.object(shared_main, 'init_firebase', lambda _: None))
    def verify(token):
        if token != 'browser-test-only-token':
            raise ValueError('Invalid simulated token')
        return {'uid': 'browser-test', 'email': 'browser@example.test'}
    stack.enter_context(patch('app.deps.verify_token', verify))
    stored = {}
    stack.enter_context(patch.object(cache, 'get', lambda db, key: stored.get(key)))
    stack.enter_context(patch.object(cache, 'put', lambda db, key, **kw: stored.__setitem__(key, kw['payload'])))
    stack.enter_context(patch.object(datasets, 'touch', lambda *a, **kw: None))
    stack.enter_context(patch.object(runs, 'record', lambda *a, **kw: 'browser-run'))
    stack.enter_context(patch.object(users, 'upsert', lambda *a: {}))
    app = shared_main.create_app()
    app.dependency_overrides[get_db] = lambda: object()
    # Only this test process exposes the shared app with simulated services.
    app.add_middleware(CORSMiddleware, allow_origins=['http://127.0.0.1:5173'],
                       allow_methods=['*'], allow_headers=['*'])
    sock = socket.socket()
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=port, log_level='warning'))
    thread = threading.Thread(target=lambda: server.run(sockets=[sock]), daemon=True)
    thread.start()
    def stop():
        server.should_exit = True
        thread.join(timeout=5)
        sock.close()
    stack.callback(stop)
    for _ in range(100):
        if server.started: break
        time.sleep(.05)
    assert server.started, 'Simulated shared API did not start'
    return f'http://127.0.0.1:{port}'


def install_browser_simulation(page, client):
    page.route(re.compile(r'/src/auth/firebase\.ts'), lambda route: route.fulfill(
        content_type='application/javascript', body="""
        export const authConfigurationError = '';
        export const firebaseAuth = { currentUser: null, authStateReady: async () => {} };
        """))
    page.route(re.compile(r'/node_modules/\.vite/deps/firebase_auth\.js'), lambda route: route.fulfill(
        content_type='application/javascript', body="""
        const user = { uid: 'browser-test', getIdToken: async () => 'browser-test-only-token' };
        export function onAuthStateChanged(auth, callback) {
          auth.callback = callback;
          setTimeout(() => {
            auth.currentUser = sessionStorage.getItem('browser-test-auth') ? user : null;
            callback(auth.currentUser);
          }, 100);
          return () => { auth.callback = null; };
        }
        export async function signInWithEmailAndPassword(auth) {
          sessionStorage.setItem('browser-test-auth', 'yes');
          auth.currentUser = user;
          await auth.callback?.(user);
          return { user };
        }
        export async function signOut(auth) {
          sessionStorage.removeItem('browser-test-auth');
          auth.currentUser = null;
          await auth.callback?.(null);
        }
        """))
    # Continue the original browser upload so Chromium retains file parts;
    # Playwright post_data_buffer intentionally omits file bodies.
    page.route(re.compile(r'^http://127\.0\.0\.1:5173/api/'),
               lambda route: route.continue_(url=client + '/api' + route.request.url.split('/api', 1)[1]))



def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--simulated-auth', action='store_true')
    args = parser.parse_args()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    files = sorted((HERE/'dataset_shm/SHM/Test').glob('*.csv'))
    assert len(files) == 16
    with ExitStack() as stack, sync_playwright() as p:
        client = simulated_api(stack) if args.simulated_auth else None
        browser = p.chromium.launch(channel=os.environ.get('SHM_BROWSER_CHANNEL', 'msedge'), headless=True)
        page = browser.new_page(viewport={'width': 1280, 'height': 1000}, accept_downloads=True)
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        if client is not None:
            install_browser_simulation(page, client)
        page.goto('http://127.0.0.1:5173/subsystem/shm')
        page.get_by_label('Email', exact=True).fill('browser@example.test' if args.simulated_auth else os.environ['SHM_TEST_EMAIL'])
        page.get_by_label('Password', exact=True).fill('test-only-password' if args.simulated_auth else os.environ['SHM_TEST_PASSWORD'])
        page.get_by_role('button', name='Log In').click()
        expect(page).to_have_url(re.compile('/home$'))
        page.goto('http://127.0.0.1:5173/subsystem/shm')
        page.reload()
        expect(page.get_by_role('heading', name='Structural health monitoring')).to_be_visible()
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
    print(('SIMULATED auth/Firestore. ' if args.simulated_auth else 'LIVE Firebase auth. ') + 'Browser passed: 16 real uploads, exact CSV parity, invalid input, stale-download protection, drag/drop, mobile layout.')


if __name__ == '__main__':
    main()
