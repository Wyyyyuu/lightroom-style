#!/usr/bin/env python3
"""Request fresh, read-only diagnostics from the Lightroom plugin. No UI automation."""
import argparse
import json
import os
import sys
import time
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", type=Path, help="Override the Lightroom appData/PhotoStyleMatchBridge directory")
    parser.add_argument("--plugin-dir", type=Path, help="Optional plugin folder for reading startup errors after a timeout")
    parser.add_argument("--timeout", type=float, default=15)
    args = parser.parse_args()
    if not 1 <= args.timeout <= 60:
        parser.error("timeout must be between 1 and 60 seconds")
    if args.state_dir:
        root = args.state_dir.resolve()
    elif os.environ.get("APPDATA"):
        root = Path(os.environ["APPDATA"]) / "Adobe" / "Lightroom" / "PhotoStyleMatchBridge"
    else:
        parser.error("Provide --state-dir outside Windows")
    root.mkdir(parents=True, exist_ok=True)
    previous = {path.name for path in root.glob("*.json.ready")}
    request = root / "refresh.request"
    try:
        with request.open("x", encoding="utf-8") as handle:
            handle.write("refresh\n")
    except FileExistsError:
        pass  # A read-only refresh is already waiting for the plugin.
    deadline = time.monotonic() + args.timeout
    while time.monotonic() < deadline:
        current = sorted(root.glob("*.json.ready"), key=lambda path: path.stat().st_mtime_ns, reverse=True)
        for ready in current:
            if ready.name in previous or ready.name.startswith("loaded-"):
                continue
            response = ready.with_suffix("")
            data = json.loads(response.read_text(encoding="utf-8"))
            if ready.name.startswith("error-"):
                print(json.dumps({"connected": False, "plugin_error": data, "response_path": str(response)}, ensure_ascii=False, indent=2))
                return 3
            if ready.name.startswith("diagnostic-"):
                print(json.dumps({"connected": True, "scope": "read-only SDK response; editing/export not verified", "response_path": str(response), "diagnostic": data}, ensure_ascii=False, indent=2))
                return 0
        time.sleep(0.25)
    plugin = args.plugin_dir or root.parent / "Modules" / "PhotoStyleBridge.lrplugin"
    startup_log = plugin / "bridge-startup.log"
    failure = {"connected": False, "reason": "No fresh Lightroom SDK response within timeout; this does not prove the plugin is disabled", "state_directory": str(root), "startup_log_path": str(startup_log), "next_step": "If already enabled, inspect the startup log and reload the plugin, then close Plug-in Manager and retry"}
    try:
        if startup_log.is_file():
            failure["startup_log_tail"] = startup_log.read_text(encoding="utf-8", errors="replace").splitlines()[-12:]
            failure["startup_log_note"] = "Historical log tail, not a fresh SDK response"
    except OSError as error:
        failure["startup_log_read_error"] = str(error)
    print(json.dumps(failure, ensure_ascii=False, indent=2))
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError) as error:
        print(f"Bridge probe failed: {error}", file=sys.stderr)
        sys.exit(3)
