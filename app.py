"""Benchly — the IT technician's one-stop workstation triage bench.

Entry point: creates the WebView2 window and exposes the Python API bridge.
"""

import ctypes
import functools
import os
import subprocess
import sys
import threading

import webview

from backend import (metrics, sysinfo, storage, network, security, software, events, report,
                     repair, devices, schedtasks, crashes, baseline, updates, browser_ext,
                     speedtest, settings, vt, netscan, temps, drivers, memdiag, batterytrend,
                     remote, fleet, diag, restore, autoruns, threats, runbooks, debloat,
                     reliability, cleanup, usbhistory, backupaudit, tweaks, domain)

APP_NAME = "Benchly"
APP_VERSION = "1.7.0"


def resource_path(rel: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


class Api:
    """Methods callable from JS via window.pywebview.api.*  (each runs in a thread)."""

    def __init__(self):
        self._window = None

    # --- meta ---------------------------------------------------------------
    def app_info(self):
        import platform
        import socket
        return {"name": APP_NAME, "version": APP_VERSION,
                "is_admin": security.is_admin(), "frozen": hasattr(sys, "_MEIPASS"),
                "hostname": socket.gethostname(),
                "os_quick": f"{platform.system()} {platform.release()} · {platform.version()}"}

    def relaunch_as_admin(self, page=None):
        try:
            page_args = f" --page {page}" if page and str(page).isalpha() else ""
            if hasattr(sys, "_MEIPASS"):
                exe, args = sys.executable, page_args.strip()
            else:
                exe, args = sys.executable, f'"{os.path.abspath(__file__)}"{page_args}'
            rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, args, None, 1)
            if rc > 32:
                threading.Timer(0.4, lambda: self._window and self._window.destroy()).start()
                return {"ok": True}
            return {"ok": False, "error": "Elevation was cancelled."}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def open_path(self, path):
        # Reveal in Explorer only — never the bare `explorer <path>` open verb
        # (which would run an .exe). Files are selected; directories are opened.
        try:
            full = os.path.abspath(str(path))
            if os.path.isfile(full):
                subprocess.Popen(["explorer", "/select,", full])
                return {"ok": True}
            if os.path.isdir(full):
                subprocess.Popen(["explorer", full])
                return {"ok": True}
            return {"ok": False, "error": "Path not found."}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def open_in_browser(self, path):
        # Hardened: this is bridge-reachable, and os.startfile() would EXECUTE an
        # .exe/.bat/.lnk. Allow only web links and Benchly's own report files.
        try:
            p = str(path)
            if p.startswith(("http://", "https://")):
                os.startfile(p)
                return {"ok": True}
            full = os.path.normpath(os.path.abspath(p))
            outdir = os.path.normpath(report._out_dir())
            if full.lower().startswith(outdir.lower() + os.sep) and full.lower().endswith((".html", ".pdf")):
                os.startfile(full)
                return {"ok": True}
            return {"ok": False, "error": "Refused: only web links or Benchly report files can be opened."}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def open_settings(self, uri):
        """Open a Windows Settings deep link (ms-settings: URIs only)."""
        try:
            if not str(uri).startswith("ms-settings:"):
                return {"ok": False, "error": "Only ms-settings: links are allowed."}
            os.startfile(uri)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # --- live ----------------------------------------------------------------
    def get_metrics(self):
        return metrics.get_metrics()

    def get_processes(self):
        return metrics.get_processes()

    def kill_process(self, pid):
        return metrics.kill_process(pid)

    # --- deep dive -------------------------------------------------------------
    def get_inventory(self, refresh=False):
        return sysinfo.get_inventory(refresh=bool(refresh))

    def get_storage(self, refresh=False):
        return storage.get_storage(refresh=bool(refresh))

    def list_drives(self):
        return storage.list_drives()

    def analyze_folder(self, path):
        return storage.analyze_folder(path)

    # --- network ----------------------------------------------------------------
    def get_network_info(self):
        return network.get_network_info()

    def get_public_ip(self):
        return network.get_public_ip()

    def run_ping(self, host, count=4):
        return network.run_ping(host, count)

    def run_traceroute(self, host):
        return network.run_traceroute(host)

    def dns_lookup(self, host):
        return network.dns_lookup(host)

    def port_test(self, host, port):
        return network.port_test(host, port)

    def get_connections(self):
        return network.get_connections()

    def flush_dns(self):
        return network.flush_dns()

    def lookup_domain(self, query):
        return domain.lookup_domain(query)

    # --- audit / software / events ----------------------------------------------
    def get_health(self, refresh=False):
        return security.get_health(refresh=bool(refresh))

    def get_installed(self):
        return software.get_installed()

    def get_startup(self):
        return software.get_startup()

    def get_services(self):
        return software.get_services()

    def get_hotfixes(self):
        return software.get_hotfixes()

    def get_events(self, days=7):
        return events.get_events(days=int(days))

    # --- repair toolbox ------------------------------------------------------------
    def list_repair_tools(self):
        return repair.list_tools()

    def start_repair(self, tool_id):
        return repair.start_tool(tool_id)

    def get_repair_job(self, job_id, offset=0):
        return repair.get_job(job_id, int(offset))

    def cancel_repair(self, job_id):
        return repair.cancel_job(job_id)

    # --- devices & printers ----------------------------------------------------------
    def get_problem_devices(self):
        return devices.get_problem_devices()

    def get_printers(self):
        return devices.get_printers()

    def purge_print_queue(self):
        return devices.purge_print_queue()

    # --- audits ------------------------------------------------------------------------
    def get_scheduled_tasks(self):
        return schedtasks.get_tasks()

    def get_crashes(self):
        return crashes.get_crashes()

    def get_extensions(self):
        return browser_ext.get_extensions()

    def get_pending_updates(self):
        return updates.get_pending_updates()

    # --- baseline ------------------------------------------------------------------------
    def save_baseline(self):
        return baseline.save_baseline()

    def get_baseline_info(self):
        return baseline.get_baseline_info()

    def compare_baseline(self):
        return baseline.compare_baseline()

    # --- speed test -----------------------------------------------------------------------
    def run_speedtest(self):
        return speedtest.run_speedtest()

    # --- security hub / VirusTotal ----------------------------------------------------------
    def get_setting(self, key):
        return settings.get(key)

    def set_setting(self, key, value):
        return settings.set_value(key, value)

    def pick_file(self):
        try:
            result = self._window.create_file_dialog(webview.OPEN_DIALOG)
            if result:
                return {"ok": True, "path": result[0]}
            return {"ok": False, "error": "cancelled"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def vt_hash_file(self, path):
        return vt.hash_file(path)

    def vt_check_hash(self, file_hash):
        return vt.check_hash(file_hash)

    # --- LAN toolkit -------------------------------------------------------------------------
    def list_subnets(self):
        return netscan.list_subnets()

    def start_subnet_scan(self, network):
        return netscan.start_subnet_scan(network)

    def get_scan_job(self, job_id):
        return netscan.get_scan_job(job_id)

    def port_profile(self, host):
        return netscan.port_profile(host)

    def wol_machines(self):
        return netscan.wol_machines()

    def wol_save(self, machines):
        return netscan.wol_save(machines)

    def wol_send(self, mac):
        return netscan.wol_send(mac)

    def dhcp_dns_health(self):
        return netscan.dhcp_dns_health()

    # --- deep diver -----------------------------------------------------------------------------
    def get_sensors(self):
        return temps.get_sensors()

    def get_driver_audit(self):
        return drivers.get_driver_audit()

    def launch_memory_test(self):
        return memdiag.launch_memory_test()

    def get_memory_results(self):
        return memdiag.get_memory_results()

    def get_battery_history(self):
        return batterytrend.get_history()

    # --- fleet ---------------------------------------------------------------------------------------
    def remote_snapshot(self, host, user="", password=""):
        return remote.remote_snapshot(host, user, password)

    def compare_reports(self, path_a, path_b):
        return fleet.compare_reports(path_a, path_b)

    def get_ticket_summary(self):
        return report.build_ticket_summary()

    # --- restore points ----------------------------------------------------------------------
    def restore_status(self):
        return restore.status()

    def create_restore_point(self, description="Benchly checkpoint"):
        return restore.create_point(description)

    def open_restore_ui(self):
        return restore.open_restore_ui()

    # --- autoruns / persistence ----------------------------------------------------------------
    def get_autoruns(self):
        return autoruns.get_autoruns()

    # --- consumer safety -----------------------------------------------------------------------
    def remote_access_audit(self):
        return threats.remote_access_audit()

    def hijack_scan(self):
        return threats.hijack_scan()

    # --- guided runbooks -----------------------------------------------------------------------
    def list_runbooks(self):
        return runbooks.list_runbooks()

    def run_runbook_step(self, runbook_id, step_id):
        return runbooks.run_step(runbook_id, step_id)

    # --- process deep inspect ------------------------------------------------------------------
    def process_detail(self, pid):
        return metrics.process_detail(pid)

    def find_lockers(self, path):
        return metrics.find_lockers(path)

    # --- debloat / privacy ---------------------------------------------------------------------
    def list_appx(self):
        return debloat.list_appx()

    def remove_appx(self, full_names):
        return debloat.remove_appx(full_names)

    def get_tweaks(self):
        return tweaks.get_tweaks()

    def set_tweak(self, key, enable=True):
        return tweaks.set_tweak(key, bool(enable))

    def set_power_plan(self, which):
        return tweaks.set_power_plan(which)

    def restart_explorer(self):
        return tweaks.restart_explorer()

    # --- reliability ---------------------------------------------------------------------------
    def get_reliability(self):
        return reliability.get_reliability()

    # --- cleanup -------------------------------------------------------------------------------
    def scan_junk(self):
        return cleanup.scan_junk()

    def clean_junk(self, category_ids):
        return cleanup.clean_junk(category_ids)

    def find_large_files(self, path, min_mb=100):
        return cleanup.find_large_files(path, int(min_mb))

    def start_duplicate_scan(self, path):
        return cleanup.start_duplicate_scan(path)

    def get_duplicate_job(self, job_id):
        return cleanup.get_duplicate_job(job_id)

    def recycle_files(self, paths):
        return cleanup.recycle_files(paths)

    # --- USB history / backup ------------------------------------------------------------------
    def get_usb_history(self):
        return usbhistory.get_usb_history()

    def get_backup_posture(self):
        return backupaudit.get_posture()

    # --- report -------------------------------------------------------------------
    def start_report(self):
        return report.start_report()

    def get_report_job(self, job_id):
        return report.get_report_job(job_id)


def _enable_dark_titlebar(window):
    """Dark title bar + fully rounded Win11 window corners to match the UI."""
    try:
        import webview.platforms.winforms  # noqa: F401  (ensures native window exists)
        hwnd = window.native.Handle.ToInt32()
        dwm = ctypes.windll.dwmapi

        dark = ctypes.c_int(1)
        for attr in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE (20, or 19 pre-20H1)
            if dwm.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(dark), ctypes.sizeof(dark)) == 0:
                break

        # DWMWA_WINDOW_CORNER_PREFERENCE (33) = DWMWCP_ROUND (2)
        corner = ctypes.c_int(2)
        dwm.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(corner), ctypes.sizeof(corner))
    except Exception:
        pass


def _prewarm():
    """Warm the slow caches in the background so deep pages open instantly."""
    for fn in (sysinfo.get_inventory, storage.get_storage, security.get_health,
               batterytrend.record):
        try:
            fn()
        except Exception:
            pass


def _instrument(api):
    """Wrap every public bridge method: record the call for the watchdog and
    make sure a backend exception is logged and returned as data, never raised
    into the WebView2 bridge (a wedged bridge is worse than a failed call)."""
    for name in dir(api):
        if name.startswith("_"):
            continue
        fn = getattr(api, name)
        if not callable(fn):
            continue

        @functools.wraps(fn)
        def wrapper(*args, _fn=fn, _name=name, **kwargs):
            diag.note_call(_name)
            try:
                return _fn(*args, **kwargs)
            except Exception as e:
                diag.log.exception("api.%s failed", _name)
                return {"ok": False, "error": f"{type(e).__name__}: {e}"}

        setattr(api, name, wrapper)


def main():
    diag.install(APP_VERSION)
    threading.Thread(target=_prewarm, daemon=True).start()
    api = Api()
    _instrument(api)
    url = resource_path(os.path.join("ui", "index.html"))
    # Optional start page, e.g. `Benchly.exe --page health`
    hash_parts = []
    if "--page" in sys.argv:
        try:
            hash_parts.append(sys.argv[sys.argv.index("--page") + 1])
        except IndexError:
            pass
    if "--turbo" in sys.argv:        # 20× polling cadence for soak-testing
        hash_parts.append("turbo")
    if "--theme" in sys.argv:        # e.g. `Benchly.exe --theme icloud`
        try:
            hash_parts.append(sys.argv[sys.argv.index("--theme") + 1])
        except IndexError:
            pass
    if hash_parts:
        url += "#" + ",".join(hash_parts)
    window = webview.create_window(
        title=APP_NAME,
        url=url,
        js_api=api,
        width=1400,
        height=880,
        min_size=(1080, 700),
        background_color="#0a0e16",
    )
    api._window = window
    webview.start(_enable_dark_titlebar, window, gui="edgechromium", debug=False)


if __name__ == "__main__":
    main()
