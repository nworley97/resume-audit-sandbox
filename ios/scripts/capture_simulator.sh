#!/usr/bin/env bash
# Run on the cloud Mac after building. No credentials or real user data are used.
set -euo pipefail
mkdir -p build/artifacts
xcrun simctl list devices available --json > build/artifacts/simulators.json
SIMULATOR_ID=$(python3 - <<'PY'
import json
from pathlib import Path
devices = json.loads(Path('build/artifacts/simulators.json').read_text())['devices']
phones = [d for runtime, group in devices.items() if 'iOS' in runtime
          for d in group if d.get('isAvailable') and d['name'].startswith('iPhone')]
if not phones:
    raise SystemExit('No available iPhone simulator on this build image')
# Match the 393 x 852 Figma canvas where the installed runtimes allow it.
preferred = ['iPhone 16', 'iPhone 15', 'iPhone 14 Pro']
phone = next((d for name in preferred for d in phones if d['name'] == name),
             sorted(phones, key=lambda d: d['name'])[-1])
Path('build/artifacts/device.txt').write_text(phone['name'] + '\n')
print(phone['udid'])
PY
)
trap 'xcrun simctl shutdown "$SIMULATOR_ID" >/dev/null 2>&1 || true' EXIT
xcrun simctl boot "$SIMULATOR_ID"
xcrun simctl bootstatus "$SIMULATOR_ID" -b
xcrun simctl status_bar "$SIMULATOR_ID" override --time '9:41' --batteryState charged --batteryLevel 100
xcrun simctl install "$SIMULATOR_ID" build/DerivedData/Build/Products/Debug-iphonesimulator/AlteraSF.app
xcrun simctl ui "$SIMULATOR_ID" appearance light
xcrun simctl launch "$SIMULATOR_ID" com.alterasf.dashboard
sleep 5
xcrun simctl io "$SIMULATOR_ID" screenshot build/artifacts/sign-in-light.png
xcrun simctl ui "$SIMULATOR_ID" appearance dark
sleep 2
xcrun simctl io "$SIMULATOR_ID" screenshot build/artifacts/sign-in-dark.png
