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
                     reliability, cleanup, usbhistory, backupaudit, tweaks, domain,
                     winget, certaudit, mailcheck, urlcheck, listeners, wifi, slowsnap,
                     selfupdate, power, shellrepair, gremlins,
                     defender, persistence, execevidence, hardening,
                     bitlocker, avcheck, helpercard, display, rescue,
                     links, netperf, virt,
                     pendingreboot, wuhistory, boottime,
                     licensing, identity, grouppolicy, timesync, baseline_policy,
                     firewall, credentials,
                     envaudit, runtimes, audio,
                     errdecode, profiles, filehash, hosts, minidump,
                     policies, corpagents, corpnet, appupdates)

APP_NAME = "Benchly"
APP_VERSION = "2.14.0"


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

    def folder_types(self, path):
        return storage.folder_types(path)

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

    def unmask_url(self, url):
        return urlcheck.unmask_url(url)

    def scan_wifi(self):
        return wifi.scan_wifi()

    # --- app updates (winget) ---------------------------------------------------
    def winget_available(self):
        return {"ok": True, "available": winget.available()}

    def list_app_updates(self):
        return winget.list_updates()

    def update_app(self, pkg_id):
        return winget.update_one(pkg_id)

    def update_all_apps(self):
        return winget.update_all_job()

    def get_update_all_job(self, job_id, offset=0):
        return winget.get_update_all_job(job_id, offset)

    # --- software version check (no winget; official sources) -------------------
    def start_version_check(self):
        return appupdates.start_check()

    def get_version_check(self, job_id):
        return appupdates.get_check(job_id)

    # --- phishing & trust triage ------------------------------------------------
    def audit_certs(self):
        return certaudit.audit_certs()

    def analyze_headers(self, raw):
        return mailcheck.analyze_headers(raw)

    def get_listeners(self):
        return listeners.get_listeners()

    # --- performance snapshot ---------------------------------------------------
    def start_snapshot(self, window=30):
        return slowsnap.start_snapshot(window)

    def get_snapshot(self, job_id):
        return slowsnap.get_snapshot(job_id)

    # --- self update ------------------------------------------------------------
    def check_update(self):
        return selfupdate.check_update(APP_VERSION)

    def download_update(self):
        return selfupdate.download_update()

    def update_status(self, job_id):
        return selfupdate.update_status(job_id)

    def apply_update(self):
        return selfupdate.apply_update()

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

    # --- pending reboot / WU history / boot time (Bundle E) -------------------------
    def pending_reboot(self):
        return pendingreboot.pending_reboot()

    def restart_now(self):
        return pendingreboot.restart_now()

    def wu_history(self, limit=40):
        return wuhistory.wu_history(int(limit))

    def wu_health(self):
        return wuhistory.wu_health()

    def boot_performance(self):
        return boottime.boot_performance()

    # --- workplace: identity, licensing, policy, time, managed baseline (Bundle F) ---
    def licensing_status(self):
        return licensing.licensing_status()

    def identity_status(self):
        return identity.identity_status()

    def gpo_results(self):
        return grouppolicy.gpo_results()

    def time_status(self):
        return timesync.time_status()

    def time_resync(self):
        return timesync.time_resync()

    def baseline_read(self):
        return baseline_policy.read_baseline()

    def baseline_apply(self, key, value):
        return baseline_policy.apply_policy(key, value)

    def baseline_clear(self, key):
        return baseline_policy.clear_policy(key)

    def baseline_export(self):
        return baseline_policy.export_baseline()

    # --- corporate: applied policies, agents, update/proxy/network (read-only) ---------
    def applied_policies(self):
        return policies.applied_policies()

    def corp_agents(self):
        return corpagents.corp_agents()

    def corp_network(self):
        return corpnet.corp_network()

    # --- network & sharing deep (Bundle G) -------------------------------------------
    def firewall_overview(self):
        return firewall.firewall_overview()

    def firewall_inbound(self):
        return firewall.inbound_allows()

    def firewall_disable_rule(self, name):
        return firewall.disable_rule(name)

    def network_profiles(self):
        return network.network_profiles()

    def set_network_category(self, interface, category):
        return network.set_network_category(interface, category)

    def mapped_drives(self):
        return credentials.mapped_drives()

    def stored_credentials(self):
        return credentials.stored_credentials()

    def remove_credential(self, target):
        return credentials.remove_credential(target)

    def dns_cache(self):
        return network.dns_cache()

    def winsock_catalog(self):
        return network.winsock_catalog()

    # --- power / storage / runtime forensics (Bundle H) ------------------------------
    def battery_report(self):
        return power.battery_report()

    def energy_report(self, duration=30):
        return power.energy_report(int(duration))

    def storage_deep(self):
        return storage.storage_deep()

    def env_audit(self):
        return envaudit.env_audit()

    def clean_path(self, scope):
        return envaudit.clean_path(scope)

    def runtimes_inventory(self):
        return runtimes.runtimes_inventory()

    def audio_status(self):
        return audio.audio_status()

    def restart_audio(self):
        return audio.restart_audio()

    # --- devices & printers ----------------------------------------------------------
    def get_problem_devices(self):
        return devices.get_problem_devices()

    def get_printers(self):
        return devices.get_printers()

    def purge_print_queue(self):
        return devices.purge_print_queue()

    def printer_doctor(self):
        return devices.printer_doctor()

    def printer_clear_offline(self, name):
        return devices.printer_clear_offline(name)

    def printer_testpage(self, name):
        return devices.printer_testpage(name)

    # --- power / sleep / wake -----------------------------------------------------------
    def power_overview(self):
        return power.power_overview()

    def wake_history(self, days=7):
        return power.wake_history(days)

    def set_device_wake(self, name, enable):
        return power.set_device_wake(name, enable)

    def disarm_wake_task(self, task_path):
        return power.disarm_wake_task(task_path)

    # --- cache & shell repair -----------------------------------------------------------
    def list_shell_repairs(self):
        return shellrepair.list_repairs()

    def run_shell_repair(self, key):
        return shellrepair.run_repair(key)

    # --- gremlin hunters ----------------------------------------------------------------
    def disk_cpu_culprit(self, window=8):
        return gremlins.disk_cpu_culprit(window)

    def usb_drop_history(self, days=7):
        return gremlins.usb_drop_history(days)

    def mark_freeze(self, window_secs=90):
        return gremlins.mark_freeze(window_secs)

    # --- security & IR v2 ---------------------------------------------------------------
    def audit_defender(self):
        return defender.audit_defender()

    def remove_exclusion(self, kind, value):
        return defender.remove_exclusion(kind, value)

    def map_persistence(self):
        return persistence.map_persistence()

    def recent_execution(self, days=14):
        return execevidence.recent_execution(days)

    def hardening_scorecard(self):
        return hardening.scorecard()

    def apply_control(self, key):
        return hardening.apply_control(key)

    def asr_rules(self):
        return hardening.asr_rules()

    def set_asr(self, rule_id, mode):
        return hardening.set_asr(rule_id, mode)

    def post_scam_check(self):
        return threats.post_scam_check()

    def reset_proxy(self):
        return threats.reset_proxy()

    # --- helper (family) ----------------------------------------------------------------
    def helper_card(self):
        return helpercard.helper_card()

    def bitlocker_status(self):
        return bitlocker.bitlocker_status()

    def get_recovery_key(self, mount):
        return bitlocker.get_recovery_key(mount)

    def av_check(self):
        return avcheck.av_check()

    def set_av_permission(self, cap, raw, nonpackaged, allow):
        return avcheck.set_av_permission(cap, raw, nonpackaged, allow)

    def set_av_global(self, cap, allow):
        return avcheck.set_av_global(cap, allow)

    def detect_display(self):
        return display.detect_display()

    def set_text_scale(self, percent):
        return display.set_text_scale(percent)

    def rescue_scan(self):
        return rescue.rescue_scan()

    def rescue_start(self, dest):
        return rescue.rescue_start(dest)

    def rescue_status(self, job_id, offset=0):
        return rescue.rescue_status(job_id, offset)

    def apply_quiet_mode(self):
        return tweaks.apply_quiet_mode()

    # --- home lab / power user ----------------------------------------------------------
    def display_links(self):
        return links.display_links()

    def gpu_forensics(self):
        return temps.gpu_forensics()

    def smart_predict(self):
        return storage.smart_predict()

    def bufferbloat_test(self):
        return netperf.bufferbloat_test()

    def virt_health(self):
        return virt.virt_health()

    def compact_vhdx(self, path):
        return virt.compact_vhdx(path)

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

    # --- error-code decoder / profile health (Bundle I) ----------------------------------------
    def decode_error(self, code):
        return errdecode.decode(code)

    def detect_profiles(self):
        return profiles.detect_profiles()

    # --- quick tools / forensics (Bundle J) ----------------------------------------------------
    def hash_file(self, path):
        return filehash.hash_file(path)

    def view_hosts(self):
        return hosts.view_hosts()

    def smart_attributes(self):
        return storage.smart_attributes()

    def analyze_minidumps(self):
        return minidump.analyze_latest()

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


_DETACHED = 0x00000008 | 0x00000200   # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP


def _apply_update_mode():
    """Relaunched as `--apply-update <new_exe> <target>` (possibly elevated via UAC) to
    finish a self-update: wait for the old instance to release the exe, copy the freshly
    downloaded build over it, and relaunch. Runs instead of the UI. Logs to
    %TEMP%\\benchly-update.log so a failed swap can be diagnosed in the field."""
    if "--apply-update" not in sys.argv:
        return False
    import time
    import shutil
    import tempfile
    args = sys.argv[sys.argv.index("--apply-update") + 1:][:2]
    logp = os.path.join(tempfile.gettempdir(), "benchly-update.log")

    def log(msg):
        try:
            with open(logp, "a", encoding="mbcs", errors="replace") as f:
                f.write(msg + "\n")
        except Exception:
            pass

    if len(args) < 2:
        log("apply-update: missing arguments"); return True
    new_exe, target = args
    log(f"apply-update: new={new_exe} target={target} pid={os.getpid()}")
    for attempt in range(180):   # the old instance is exiting; retry until the exe unlocks
        try:
            shutil.copyfile(new_exe, target)
            log("apply-update: swapped in the new build")
            break
        except Exception as e:
            if attempt % 10 == 0:
                log(f"apply-update: target still locked ({attempt}s): {e}")
            time.sleep(1)
    else:
        log("apply-update: FAILED — target stayed locked for 180s"); return True
    try:
        subprocess.Popen([target], creationflags=_DETACHED, close_fds=True)
        log("apply-update: relaunched")
    except Exception as e:
        log(f"apply-update: relaunch failed: {e}")
    return True


def main():
    if _apply_update_mode():
        return
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
    if "--theme" in sys.argv:        # e.g. `Benchly.exe --theme frost`
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
