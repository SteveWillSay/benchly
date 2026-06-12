"""USB device connection history — the 'USBDeview' job, from the registry."""

import winreg


def get_usb_history():
    devices = []
    devices += _enum("SYSTEM\\CurrentControlSet\\Enum\\USBSTOR", "Storage")
    devices += _enum("SYSTEM\\CurrentControlSet\\Enum\\USB", "Device")
    # de-dupe by (name, serial)
    seen, out = set(), []
    for d in devices:
        key = (d["name"].lower(), d["serial"])
        if key in seen:
            continue
        seen.add(key)
        out.append(d)
    out.sort(key=lambda d: (d["kind"] != "Storage", d["name"].lower()))
    return {"devices": out, "count": len(out)}


def _enum(path, kind):
    found = []
    try:
        root = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path)
    except OSError:
        return found
    with root:
        for i in range(winreg.QueryInfoKey(root)[0]):
            try:
                model_key_name = winreg.EnumKey(root, i)
            except OSError:
                continue
            # USB top level has vendor/product (VID_xxxx&PID_xxxx); skip hubs/roots
            if kind == "Device" and not model_key_name.upper().startswith("VID_"):
                continue
            try:
                model_key = winreg.OpenKey(root, model_key_name)
            except OSError:
                continue
            with model_key:
                for j in range(winreg.QueryInfoKey(model_key)[0]):
                    try:
                        serial = winreg.EnumKey(model_key, j)
                        inst = winreg.OpenKey(model_key, serial)
                    except OSError:
                        continue
                    with inst:
                        name = (_val(inst, "FriendlyName") or _val(inst, "DeviceDesc") or model_key_name)
                        if name and ";" in name:
                            name = name.split(";")[-1]
                        found.append({
                            "name": name,
                            "serial": serial.split("&")[0] if "&" in serial else serial,
                            "kind": kind,
                            "model": model_key_name.replace("&", " "),
                        })
    return found


def _val(key, name):
    try:
        v, _ = winreg.QueryValueEx(key, name)
        return str(v)
    except OSError:
        return None
