# -*- coding: utf-8 -*-
"""
PyAEDT HFSS Exporter

Output order (recommended reading order):
  01_variables_classified.txt
  02_antenna_smart_summary.txt
  03_tree_with_role.txt
  04_modeler_full_dump_clean.txt
  05_export_data.json
  00_manifest.txt

Notes:
- Runs from CPython with PyAEDT rather than the in-editor IronPython environment.
- Tries to attach to an existing AEDT session first, then falls back to opening a
  selected .aedt project.
- Keeps the original export structure and role-classification heuristics.
"""

from datetime import datetime
import argparse
import json
import os
import re
import tkinter as tk
from tkinter import filedialog

import psutil
from ansys.aedt.core import Hfss
from ansys.aedt.core.generic.general_methods import active_sessions
from ansys.aedt.core.generic.settings import settings as pyaedt_settings


# =========================================================
# CONFIG
# =========================================================
USE_ASCII_TREE = True
EXPORT_BASE_DIR_ENV = "HFSS_EXPORT_BASE_DIR"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_BASE_DIR = os.path.join(SCRIPT_DIR, "hfss_exports")
BASE_DIR = os.environ.get(EXPORT_BASE_DIR_ENV, DEFAULT_BASE_DIR)


# =========================================================
# TIME
# =========================================================
timestamp_file = datetime.now().strftime("%Y%m%d_%H%M%S")
timestamp_readable = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
WARNINGS = []
SUMMARY_SKIPPED_OBJECTS = []


# =========================================================
# SESSION HELPERS
# =========================================================
def parse_args():
    parser = argparse.ArgumentParser(
        description="Export HFSS/AEDT model variables, role summaries, and modeler trees."
    )
    parser.add_argument(
        "--output-dir",
        default=BASE_DIR,
        help=(
            "Base output directory. Defaults to %s or %s."
            % (EXPORT_BASE_DIR_ENV, DEFAULT_BASE_DIR)
        )
    )
    parser.add_argument(
        "--project",
        help="Path to a .aedt project. If omitted, the script first tries to attach to a running AEDT session."
    )
    parser.add_argument(
        "--design",
        help="Design name or zero-based design index to activate when --project is used."
    )
    parser.add_argument(
        "--attach-pid",
        type=int,
        help="Attach to a specific AEDT process ID instead of scanning all running AEDT sessions."
    )
    parser.add_argument(
        "--no-gui",
        action="store_true",
        help="Do not open a Tk file picker if no usable running AEDT session is found."
    )
    return parser.parse_args()


def add_warning(message):
    text = to_str(message) if "to_str" in globals() else str(message)
    if text not in WARNINGS:
        WARNINGS.append(text)


def safe_get(func, default=None, context=None):
    try:
        return func()
    except Exception as exc:
        if context:
            add_warning(context + ": " + type(exc).__name__ + ": " + to_str(exc))
        return default


def release_hfss_session(hfss, context):
    if hfss is None:
        return
    safe_get(
        lambda: hfss.release_desktop(close_projects=False, close_desktop=False),
        context=context
    )


def select_project_file(no_gui=False):
    if no_gui:
        add_warning("No project path was provided and GUI project selection is disabled.")
        return None

    root = tk.Tk()
    root.withdraw()
    file_path = filedialog.askopenfilename(
        title="Select HFSS Project (.aedt)",
        filetypes=[("AEDT files", "*.aedt")]
    )
    root.destroy()
    return file_path


def is_temp_project_name(name):
    if not name:
        return True
    return re.fullmatch(r"Project\d+", str(name)) is not None


def reset_pyaedt_connection_preference():
    try:
        pyaedt_settings.use_grpc_api = None
    except Exception:
        pass


def count_modeler_objects(hfss):
    oeditor = safe_get(lambda: hfss.modeler.oeditor, None)
    if oeditor is None:
        return 0

    names = set()
    for group in ["Solids", "Sheets", "Lines", "Unclassified", "Model", "NonModel"]:
        objs = safe_get(lambda group=group: list(oeditor.GetObjectsInGroup(group)), [])
        for obj_name in objs:
            names.add(to_str(obj_name))
    return len(names)


def find_running_aedt_pids():
    detected_sessions = safe_get(lambda: active_sessions(), {}, context="read active AEDT sessions") or {}
    pids = set(detected_sessions)

    for proc in psutil.process_iter(["pid", "name"]):
        try:
            name = proc.info["name"]
            if not name:
                continue
            nl = name.lower()
            if (
                "ansysedt" in nl
                or "electronicsdesktop" in nl
                or ("ansys" in nl and "edt" in nl)
            ):
                pids.add(proc.info["pid"])
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    def pid_sort_key(pid):
        session_port = detected_sessions.get(pid)
        if session_port == -1:
            priority = 0
        elif session_port is None:
            priority = 1
        else:
            priority = 2
        return (priority, -pid)

    return sorted(pids, key=pid_sort_key)


def try_attach_existing_aedt(attach_pid=None):
    pids = [attach_pid] if attach_pid else find_running_aedt_pids()
    if not pids:
        print("No running AEDT/HFSS session found.")
        return None

    print("Detected AEDT PID(s):", pids)
    for pid in pids:
        print("Trying PID =", pid)
        try:
            reset_pyaedt_connection_preference()
            hfss = Hfss(
                new_desktop=False,
                aedt_process_id=pid,
                close_on_exit=False
            )

            project_name = safe_get(lambda: hfss.project_name, None)
            design_name = safe_get(lambda: hfss.design_name, None)

            print("Connected to session.")
            print("Project :", project_name)
            print("Design  :", design_name)

            modeler_object_count = count_modeler_objects(hfss)
            print("Modeler objects:", modeler_object_count)

            if is_temp_project_name(project_name) and modeler_object_count == 0:
                print("Skipping temporary AEDT session without modeler objects.")
                release_hfss_session(hfss, "release temporary AEDT session")
                reset_pyaedt_connection_preference()
                continue

            return hfss
        except Exception as exc:
            print("Attach failed:", exc)
            add_warning("Attach failed for PID %s: %s: %s" % (pid, type(exc).__name__, to_str(exc)))
            reset_pyaedt_connection_preference()

    print("Could not attach to a usable AEDT session.")
    return None


def resolve_design_selection(design_list, design_selector=None):
    if not design_list:
        return None

    if design_selector is not None:
        selector = str(design_selector).strip()
        if selector.isdigit():
            idx = int(selector)
            if 0 <= idx < len(design_list):
                return design_list[idx]
            print("Design index out of range.")
            return None

        for design_name in design_list:
            if str(design_name) == selector:
                return design_name

        print("Design not found:", selector)
        return None

    if len(design_list) == 1:
        return design_list[0]

    print("\nAvailable Designs:")
    for i, design_name in enumerate(design_list):
        print(f"{i}: {design_name}")

    idx = input("Enter design index: ").strip()
    if not idx.isdigit():
        print("Invalid design index.")
        return None

    idx = int(idx)
    if idx < 0 or idx >= len(design_list):
        print("Design index out of range.")
        return None

    return design_list[idx]


def choose_design_from_project(project_path, design_selector=None):
    try:
        hfss = Hfss(project=project_path, close_on_exit=False)
    except Exception as exc:
        print("Failed to open project.")
        print("Error:", exc)
        add_warning("Failed to open project %s: %s: %s" % (project_path, type(exc).__name__, to_str(exc)))
        return None

    design_list = safe_get(lambda: hfss.design_list, None)
    if not design_list:
        print("No design found in project.")
        add_warning("No design found in project: " + to_str(project_path))
        release_hfss_session(hfss, "release project with no designs")
        return None

    selected_design = resolve_design_selection(design_list, design_selector)
    if selected_design is None:
        add_warning("No valid design selected from project: " + to_str(project_path))
        release_hfss_session(hfss, "release project after invalid design selection")
        return None

    print("\nSelected Design:", selected_design)

    try:
        hfss.set_active_design(selected_design)
    except Exception as exc:
        print("Failed to activate design.")
        print("Error:", exc)
        add_warning("Failed to activate design %s: %s: %s" % (selected_design, type(exc).__name__, to_str(exc)))
        release_hfss_session(hfss, "release project after design activation failure")
        return None

    return hfss


def open_project_mode(project_path=None, design_selector=None, no_gui=False):
    if project_path:
        print("\nOpening .aedt project...")
    else:
        print("\nOpening .aedt project...")
        project_path = select_project_file(no_gui=no_gui)

    if not project_path:
        print("No .aedt file selected.")
        return None

    print("Selected project:")
    print(project_path)
    return choose_design_from_project(project_path, design_selector)


def get_hfss_session(args):
    if args.project:
        return open_project_mode(args.project, args.design, args.no_gui)

    hfss = try_attach_existing_aedt(args.attach_pid)
    if hfss is not None:
        return hfss

    return open_project_mode(design_selector=args.design, no_gui=args.no_gui)


# =========================================================
# COMMON HELPERS
# =========================================================
def to_str(x):
    try:
        return str(x)
    except Exception:
        try:
            return repr(x)
        except Exception:
            return "<unprintable>"


def w(f, s=""):
    try:
        f.write(to_str(s) + "\n")
    except Exception:
        try:
            f.write("<write failed>\n")
        except Exception:
            pass


def to_float(x):
    try:
        return float(str(x))
    except Exception:
        return None


def json_safe(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, dict):
        return {to_str(key): json_safe(val) for key, val in value.items()}
    return to_str(value)


def get_obj_props(oeditor, obj_name):
    return safe_get(lambda: list(oeditor.GetProperties("Geometry3DAttributeTab", obj_name)), [])


def get_attr(oeditor, obj_name, attr_name):
    try:
        props = get_obj_props(oeditor, obj_name)
        if attr_name in props:
            return oeditor.GetPropertyValue("Geometry3DAttributeTab", obj_name, attr_name)
        return None
    except Exception:
        return None


def get_bbox(oeditor, obj_name):
    bb = safe_get(lambda: list(oeditor.GetObjectBoundingBox(obj_name)), None)
    if not bb or len(bb) != 6:
        return None

    vals = [to_float(x) for x in bb]
    if None in vals:
        return None

    xmin, ymin, zmin, xmax, ymax, zmax = vals
    return {
        "raw": bb,
        "xmin": xmin, "ymin": ymin, "zmin": zmin,
        "xmax": xmax, "ymax": ymax, "zmax": zmax,
        "dx": xmax - xmin,
        "dy": ymax - ymin,
        "dz": zmax - zmin,
        "cx": (xmin + xmax) / 2.0,
        "cy": (ymin + ymax) / 2.0,
        "cz": (zmin + zmax) / 2.0
    }


def get_node_key(obj, fallback_name):
    obj_path = safe_get(lambda: obj.GetObjPath(), "")
    return to_str(fallback_name) + " @ " + to_str(obj_path)


def get_object_identity(oeditor, obj_name):
    child = safe_get(lambda: oeditor.GetChildObject(obj_name), None)
    obj_path = safe_get(lambda: child.GetObjPath(), None) if child is not None else None
    if obj_path:
        return "path:" + to_str(obj_path).lower()
    return "name:" + to_str(obj_name).lower()


def get_operations(oeditor, obj_name):
    child = safe_get(lambda: oeditor.GetChildObject(obj_name), None)
    if child is None:
        return []

    ops = safe_get(lambda: list(child.GetChildNames()), [])
    return ops if ops else []


def get_operation_props(oeditor, obj_name):
    out = []
    child = safe_get(lambda: oeditor.GetChildObject(obj_name), None)
    if child is None:
        return out

    ops = safe_get(lambda: list(child.GetChildNames()), [])
    if not ops:
        return out

    for op_name in ops:
        op = safe_get(lambda op_name=op_name: child.GetChildObject(op_name), None)
        if op is None:
            continue

        props = safe_get(lambda: list(op.GetPropNames()), [])
        pairs = []
        for p in props:
            val = safe_get(lambda p=p: op.GetPropEvaluatedValue(p), None)
            if val is None:
                val = safe_get(lambda p=p: op.GetPropValue(p), None)
            pairs.append((to_str(p), val))

        out.append({
            "op_name": to_str(op_name),
            "props": pairs
        })

    return out


def get_primary_shape(op_names):
    s = " / ".join([to_str(x) for x in op_names]).lower()
    if "createcylinder" in s:
        return "cylinder"
    if "createbox" in s:
        return "box"
    if "createrectangle" in s:
        return "rectangle"
    if "createcircle" in s:
        return "circle"
    if "createpolyline" in s:
        return "polyline"
    return "unknown"


def material_family(material):
    if material is None:
        return "unknown"

    s = to_str(material).strip().lower()
    if "copper" in s or "pec" in s or "aluminum" in s or "gold" in s or "silver" in s or "metal" in s:
        return "conductor"
    if "fr4" in s or "substrate" in s or "rogers" in s or "dielectric" in s or "air" in s or "vacuum" in s:
        return "dielectric"
    return "other"


def detect_role(group_name, obj_name, bbox, material, op_names):
    name = to_str(obj_name).lower()
    group = to_str(group_name).lower()
    shape = get_primary_shape(op_names)
    matfam = material_family(material)

    dx = bbox["dx"] if bbox else None
    dy = bbox["dy"] if bbox else None
    dz = bbox["dz"] if bbox else None

    if "sub" in name or "fr4" in name or "airbox" in name or "diel" in name:
        if "airbox" in name:
            return "AIR_REGION"
        return "SUBSTRATE"

    if "gnd" in name or "ground" in name:
        return "GROUND"

    if "feed" in name or "port" in name or "probe" in name or "strip" in name or "line" in name:
        return "FEED"

    if "patch" in name or "radiat" in name:
        return "PATCH"

    if "short" in name or "shoring" in name:
        return "SHORTING_PIN"

    if "via" in name:
        return "VIA"

    if matfam == "dielectric":
        return "SUBSTRATE"

    if shape == "cylinder" and dz is not None and dx is not None and dy is not None:
        rxy = max(dx, dy)
        if dz > rxy * 1.5 and matfam == "conductor":
            return "VIA"

    if group == "sheets":
        if dx is not None and dy is not None and dz is not None:
            area_like = dx * dy
            thin = abs(dz) < 1e-6 or dz < 0.05
            if thin and area_like > 50:
                if matfam == "conductor" or matfam == "unknown":
                    return "GROUND"

    if group == "solids":
        if matfam == "conductor" and bbox:
            if dz is not None and dx is not None and dy is not None:
                if dz < min(dx, dy) * 0.15 and dx * dy > 20:
                    return "PATCH"
        if matfam == "dielectric":
            return "SUBSTRATE"

    return "OTHER"


# =========================================================
# 01 VARIABLES
# =========================================================
def is_formula(expr):
    if expr is None:
        return False
    s = to_str(expr).strip()
    for op in ["+", "-", "*", "/", "(", ")"]:
        if op in s:
            return True
    return False


def collect_variables(hfss):
    variables = safe_get(lambda: hfss.variable_manager.variables, {}) or {}
    out = []

    for name, var in variables.items():
        expr = safe_get(lambda var=var: var.expression, None)
        if expr is None:
            expr = safe_get(lambda var=var: str(var), "<unreadable>")
        out.append({
            "name": to_str(name),
            "expr": expr
        })

    return sorted(out, key=lambda item: item["name"].lower())


def export_variables(path, hfss):
    with open(path, "w", encoding="utf-8") as f:
        w(f, "HFSS VARIABLES CLASSIFIED (PyAEDT)")
        w(f, "=" * 80)
        w(f, "Project : " + to_str(safe_get(lambda: hfss.project_name, "<unknown>")))
        w(f, "Design  : " + to_str(safe_get(lambda: hfss.design_name, "<unknown>")))
        w(f, "")

        variable_items = collect_variables(hfss)
        basic_vars = []
        formula_vars = []

        if not variable_items:
            w(f, "[VARIABLES]")
            w(f, "-" * 80)
            w(f, "<no variables found>")
            return

        for item in variable_items:
            if is_formula(item["expr"]):
                formula_vars.append(item)
            else:
                basic_vars.append(item)

        w(f, "[SUMMARY]")
        w(f, "-" * 80)
        w(f, "Total Variables   : " + to_str(len(variable_items)))
        w(f, "Basic Variables   : " + to_str(len(basic_vars)))
        w(f, "Formula Variables : " + to_str(len(formula_vars)))
        w(f, "")

        w(f, "[BASIC VARIABLES]")
        w(f, "-" * 80)
        if basic_vars:
            for item in basic_vars:
                w(f, item["name"] + " = " + to_str(item["expr"]))
        else:
            w(f, "<none>")
        w(f, "")

        w(f, "[FORMULA VARIABLES]")
        w(f, "-" * 80)
        if formula_vars:
            for item in formula_vars:
                w(f, item["name"] + " = " + to_str(item["expr"]))
        else:
            w(f, "<none>")
        w(f, "")


# =========================================================
# 02 SMART SUMMARY
# =========================================================
def pick_key_params(op_infos):
    keywords = [
        "XSize", "YSize", "ZSize",
        "Width", "Height", "Length",
        "Radius", "Diameter",
        "Center_Position_X", "Center_Position_Y", "Center_Position_Z",
        "Center Position X", "Center Position Y", "Center Position Z",
        "Position", "X", "Y", "Z",
        "WhichAxis", "Axis"
    ]

    results = []
    seen = set()
    for op in op_infos:
        op_name = op["op_name"]
        for p, v in op["props"]:
            for k in keywords:
                if k.lower() in to_str(p).lower():
                    key = op_name + "::" + to_str(p)
                    if key not in seen:
                        seen.add(key)
                        results.append((op_name, p, v))
                    break
    return results


def dump_bbox_info(f, bbox, indent=0):
    if not bbox:
        return
    sp = " " * indent
    w(f, sp + "BBox:")
    w(f, sp + "  xmin = " + to_str(bbox["xmin"]))
    w(f, sp + "  ymin = " + to_str(bbox["ymin"]))
    w(f, sp + "  zmin = " + to_str(bbox["zmin"]))
    w(f, sp + "  xmax = " + to_str(bbox["xmax"]))
    w(f, sp + "  ymax = " + to_str(bbox["ymax"]))
    w(f, sp + "  zmax = " + to_str(bbox["zmax"]))
    w(f, sp + "  dx   = " + to_str(bbox["dx"]))
    w(f, sp + "  dy   = " + to_str(bbox["dy"]))
    w(f, sp + "  dz   = " + to_str(bbox["dz"]))
    w(f, sp + "  cx   = " + to_str(bbox["cx"]))
    w(f, sp + "  cy   = " + to_str(bbox["cy"]))
    w(f, sp + "  cz   = " + to_str(bbox["cz"]))


def collect_objects(oeditor):
    groups = ["Solids", "Sheets", "Lines", "Unclassified", "Model", "NonModel"]
    all_items = []
    seen = {}
    for g in groups:
        objs = safe_get(
            lambda g=g: list(oeditor.GetObjectsInGroup(g)),
            [],
            context="read objects in group " + g
        )
        if not objs:
            continue
        for obj_name in objs:
            if should_skip_top_level(obj_name):
                skip_name = to_str(obj_name)
                if skip_name not in SUMMARY_SKIPPED_OBJECTS:
                    SUMMARY_SKIPPED_OBJECTS.append(skip_name)
                continue

            identity = get_object_identity(oeditor, obj_name)
            if identity in seen:
                item = seen[identity]
                if g not in item["groups"]:
                    item["groups"].append(g)
                continue

            bbox = get_bbox(oeditor, obj_name)
            material = get_attr(oeditor, obj_name, "Material")
            solve_inside = get_attr(oeditor, obj_name, "Solve Inside")
            model = get_attr(oeditor, obj_name, "Model")
            color = get_attr(oeditor, obj_name, "Color")
            ops = get_operations(oeditor, obj_name)
            op_infos = get_operation_props(oeditor, obj_name)
            shape = get_primary_shape(ops)
            role = detect_role(g, obj_name, bbox, material, ops)
            all_items.append({
                "group": g,
                "groups": [g],
                "name": to_str(obj_name),
                "bbox": bbox,
                "material": material,
                "solve_inside": solve_inside,
                "model": model,
                "color": color,
                "ops": ops,
                "op_infos": op_infos,
                "shape": shape,
                "role": role
            })
            seen[identity] = all_items[-1]
    return all_items


def dump_role_section(f, title, items):
    w(f, "#" * 100)
    w(f, "[" + title + "]   Count = " + to_str(len(items)))
    w(f, "#" * 100)
    for item in items:
        w(f, "-" * 80)
        w(f, "Name      = " + item["name"])
        w(f, "Group     = " + to_str(item["group"]))
        if len(item.get("groups", [])) > 1:
            w(f, "Groups    = " + ", ".join([to_str(g) for g in item["groups"]]))
        w(f, "Role      = " + to_str(item["role"]))
        w(f, "Shape     = " + to_str(item["shape"]))
        w(f, "Material  = " + to_str(item["material"]))
        w(f, "SolveIn   = " + to_str(item["solve_inside"]))
        w(f, "Model     = " + to_str(item["model"]))
        w(f, "Color     = " + to_str(item["color"]))
        dump_bbox_info(f, item["bbox"], indent=0)
        if item["ops"]:
            w(f, "Operations:")
            for opn in item["ops"]:
                w(f, "  - " + to_str(opn))
        params = pick_key_params(item["op_infos"])
        if params:
            w(f, "KeyParams:")
            for op_name, p, v in params:
                w(f, "  " + to_str(op_name) + " :: " + to_str(p) + " = " + to_str(v))
        w(f, "")


def export_smart_summary(path, items, hfss):
    role_order = ["SUBSTRATE", "GROUND", "PATCH", "FEED", "SHORTING_PIN", "VIA", "AIR_REGION", "OTHER"]
    with open(path, "w", encoding="utf-8") as f:
        w(f, "HFSS ANTENNA SMART SUMMARY (PyAEDT)")
        w(f, "=" * 100)
        w(f, "Generated at: " + timestamp_readable)
        w(f, "Project      : " + to_str(safe_get(lambda: hfss.project_name, "<unknown>")))
        w(f, "Design       : " + to_str(safe_get(lambda: hfss.design_name, "<unknown>")))
        w(f, "")
        w(f, "[TOTAL OBJECT COUNT] " + to_str(len(items)))
        w(f, "")
        for role in role_order:
            section_items = [x for x in items if x["role"] == role]
            if section_items:
                dump_role_section(f, role, section_items)
        w(f, "=" * 100)
        w(f, "[RAW OBJECT LIST]")
        w(f, "=" * 100)
        for item in items:
            groups = ",".join([to_str(g) for g in item.get("groups", [item["group"]])])
            w(f, item["name"] + " | groups=" + groups + " | role=" + to_str(item["role"]) + " | shape=" + to_str(item["shape"]))


# =========================================================
# 03 TREE WITH ROLE
# =========================================================
if USE_ASCII_TREE:
    CONNECTOR_LAST = "\\-- "
    CONNECTOR_MID = "+-- "
    PREFIX_PIPE = "|   "
    PREFIX_EMPTY = "    "
else:
    CONNECTOR_LAST = "`-- "
    CONNECTOR_MID = "|-- "
    PREFIX_PIPE = "|   "
    PREFIX_EMPTY = "    "


def detect_role_simple(name):
    n = to_str(name).lower()
    if "patch" in n:
        return "PATCH"
    if "gnd" in n or "ground" in n:
        return "GROUND"
    if "feed" in n or "port" in n or "probe" in n or "line" in n:
        return "FEED"
    if "short" in n or "shoring" in n:
        return "SHORTING_PIN"
    if "via" in n:
        return "VIA"
    if "air" in n:
        return "AIR"
    if "fr4" in n or "sub" in n:
        return "SUBSTRATE"
    return ""


def dump_tree_with_role(f, obj, name, prefix="", is_last=True, visited=None):
    if visited is None:
        visited = set()

    role = detect_role_simple(name)
    label = to_str(name)
    if role:
        label += " [" + role + "]"

    connector = CONNECTOR_LAST if is_last else CONNECTOR_MID
    w(f, prefix + connector + label)

    node_key = to_str(name) + "_" + to_str(safe_get(lambda: obj.GetObjPath(), ""))
    if node_key in visited:
        return
    visited.add(node_key)

    children = safe_get(lambda: list(obj.GetChildNames()), [])
    if not children:
        return

    new_prefix = prefix + (PREFIX_EMPTY if is_last else PREFIX_PIPE)
    for i, child_name in enumerate(children):
        child_obj = safe_get(lambda cn=child_name: obj.GetChildObject(cn), None)
        if child_obj:
            dump_tree_with_role(f, child_obj, child_name, new_prefix, i == len(children) - 1, visited)
        else:
            w(f, new_prefix + CONNECTOR_LAST + to_str(child_name) + " <GetChildObject failed>")


def export_tree_with_role(path, oeditor, hfss):
    with open(path, "w", encoding="utf-8") as f:
        w(f, "HFSS TREE WITH ROLE (PyAEDT)")
        w(f, "=" * 80)
        w(f, "Generated at : " + timestamp_readable)
        w(f, "Project      : " + to_str(safe_get(lambda: hfss.project_name, "<unknown>")))
        w(f, "Design       : " + to_str(safe_get(lambda: hfss.design_name, "<unknown>")))
        w(f, "Tree Mode    : " + ("ASCII" if USE_ASCII_TREE else "Unicode"))
        w(f, "")

        top_names = safe_get(lambda: list(oeditor.GetChildNames()), [])
        for i, name in enumerate(top_names):
            obj = safe_get(lambda n=name: oeditor.GetChildObject(n), None)
            if obj:
                dump_tree_with_role(f, obj, name, "", i == len(top_names) - 1)
            else:
                w(f, to_str(name) + " <top-level GetChildObject failed>")


# =========================================================
# 04 CLEAN DUMP
# =========================================================
def should_skip_top_level(name):
    s = to_str(name)
    if s == "Region":
        return True
    if s.startswith("PML_Region_"):
        return True
    return False


def indent_str(n):
    return " " * n


def dump_obj_basic_info(f, oeditor, obj, name, indent):
    sp = indent_str(indent)
    obj_type = safe_get(lambda: obj.GetType(), None)
    obj_path = safe_get(lambda: obj.GetObjPath(), None)
    if obj_type is not None:
        w(f, sp + "Type = " + to_str(obj_type))
    if obj_path is not None:
        w(f, sp + "Path = " + to_str(obj_path))
    bb = safe_get(lambda: list(oeditor.GetObjectBoundingBox(name)), None)
    if bb:
        w(f, sp + "BoundingBox = " + to_str(bb))
    props = safe_get(lambda: list(oeditor.GetProperties("Geometry3DAttributeTab", name)), [])
    if props:
        w(f, sp + "[Geometry3DAttributeTab]")
        for p in props:
            val = safe_get(lambda p=p: oeditor.GetPropertyValue("Geometry3DAttributeTab", name, p), "<unreadable>")
            w(f, sp + "  " + to_str(p) + " = " + to_str(val))


def dump_prop_block(f, obj, indent):
    sp = indent_str(indent)
    props = safe_get(lambda: list(obj.GetPropNames()), [])
    if not props:
        return
    w(f, sp + "[Props]")
    for p in props:
        val = safe_get(lambda p=p: obj.GetPropEvaluatedValue(p), None)
        if val is None:
            val = safe_get(lambda p=p: obj.GetPropValue(p), "<unreadable>")
        w(f, sp + "  " + to_str(p) + " = " + to_str(val))


def dump_tree_clean(f, oeditor, obj, name, indent, visited):
    sp = indent_str(indent)
    w(f, sp + "[NODE] " + to_str(name))
    node_key = get_node_key(obj, name)
    if node_key in visited:
        w(f, sp + "  <visited>")
        return
    visited.add(node_key)
    dump_obj_basic_info(f, oeditor, obj, name, indent + 2)
    dump_prop_block(f, obj, indent + 2)
    child_names = safe_get(lambda: list(obj.GetChildNames()), [])
    if child_names:
        w(f, sp + "  [Children]")
        for cn in child_names:
            sub = safe_get(lambda cn=cn: obj.GetChildObject(cn), None)
            if sub is not None:
                dump_tree_clean(f, oeditor, sub, cn, indent + 4, visited)
            else:
                w(f, indent_str(indent + 4) + "[NODE] " + to_str(cn) + " <GetChildObject failed>")


def export_clean_dump(path, oeditor, hfss):
    with open(path, "w", encoding="utf-8") as f:
        w(f, "HFSS MODELER FULL DUMP CLEAN (PyAEDT)")
        w(f, "=" * 100)
        w(f, "Generated at: " + timestamp_readable)
        w(f, "Project      : " + to_str(safe_get(lambda: hfss.project_name, "<unknown>")))
        w(f, "Design       : " + to_str(safe_get(lambda: hfss.design_name, "<unknown>")))
        w(f, "")

        top_names = safe_get(lambda: list(oeditor.GetChildNames()), [])
        kept_names = [n for n in top_names if not should_skip_top_level(n)]
        skipped_names = [n for n in top_names if should_skip_top_level(n)]

        w(f, "[TOP LEVEL CHILDREN - KEPT]")
        for n in kept_names:
            w(f, "  - " + to_str(n))
        w(f, "")

        w(f, "[TOP LEVEL CHILDREN - SKIPPED]")
        for n in skipped_names:
            w(f, "  - " + to_str(n))
        w(f, "")

        w(f, "=" * 100)
        w(f, "[FULL TREE FROM EDITOR ROOT - CLEAN]")
        w(f, "=" * 100)

        visited = set()
        for n in kept_names:
            obj = safe_get(lambda n=n: oeditor.GetChildObject(n), None)
            if obj is not None:
                dump_tree_clean(f, oeditor, obj, n, 0, visited)
                w(f, "")
            else:
                w(f, "[NODE] " + to_str(n) + " <GetChildObject failed>")
                w(f, "")


# =========================================================
# 05 JSON EXPORT
# =========================================================
def build_role_counts(items):
    counts = {}
    for item in items:
        role = item["role"]
        counts[role] = counts.get(role, 0) + 1
    return counts


def serialize_variables(hfss):
    out = []
    for item in collect_variables(hfss):
        expr = item["expr"]
        out.append({
            "name": item["name"],
            "expression": to_str(expr),
            "kind": "formula" if is_formula(expr) else "basic"
        })
    return out


def serialize_operation_props(op_infos):
    out = []
    for op in op_infos:
        out.append({
            "op_name": to_str(op.get("op_name", "")),
            "props": [
                {
                    "name": to_str(prop_name),
                    "value": json_safe(prop_value)
                }
                for prop_name, prop_value in op.get("props", [])
            ]
        })
    return out


def serialize_key_params(item):
    return [
        {
            "operation": to_str(op_name),
            "name": to_str(prop_name),
            "value": json_safe(prop_value)
        }
        for op_name, prop_name, prop_value in pick_key_params(item.get("op_infos", []))
    ]


def serialize_objects(items):
    out = []
    for item in items:
        out.append({
            "name": item["name"],
            "primary_group": item["group"],
            "groups": [to_str(group) for group in item.get("groups", [item["group"]])],
            "role": item["role"],
            "shape": item["shape"],
            "material": json_safe(item["material"]),
            "solve_inside": json_safe(item["solve_inside"]),
            "model": json_safe(item["model"]),
            "color": json_safe(item["color"]),
            "bbox": json_safe(item["bbox"]),
            "operations": [to_str(op) for op in item.get("ops", [])],
            "key_parameters": serialize_key_params(item),
            "operation_properties": serialize_operation_props(item.get("op_infos", []))
        })
    return out


def build_json_payload(file_map, items, hfss, output_dir):
    multi_group_count = sum(1 for item in items if len(item.get("groups", [])) > 1)
    return {
        "schema_version": 1,
        "generated_at": timestamp_readable,
        "generator": "PyAEDT HFSS Exporter",
        "project": to_str(safe_get(lambda: hfss.project_name, "<unknown>")),
        "design": to_str(safe_get(lambda: hfss.design_name, "<unknown>")),
        "output_dir": output_dir,
        "object_counts": {
            "deduplicated_objects": len(items),
            "multi_group_objects": multi_group_count,
            "summary_skipped": len(SUMMARY_SKIPPED_OBJECTS),
            "summary_skipped_objects": [to_str(name) for name in SUMMARY_SKIPPED_OBJECTS]
        },
        "role_counts": build_role_counts(items),
        "variables": serialize_variables(hfss),
        "objects": serialize_objects(items),
        "warnings": [to_str(warning) for warning in WARNINGS],
        "files": {key: path for key, path in file_map.items()}
    }


def export_json(path, file_map, items, hfss, output_dir):
    payload = build_json_payload(file_map, items, hfss, output_dir)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")


# =========================================================
# 00 MANIFEST
# =========================================================
def export_manifest(path, file_map, items, hfss, output_dir):
    counts = build_role_counts(items)

    with open(path, "w", encoding="utf-8") as f:
        w(f, "HFSS EXPORT MANIFEST (PyAEDT)")
        w(f, "=" * 80)
        w(f, "Generated at : " + timestamp_readable)
        w(f, "Project      : " + to_str(safe_get(lambda: hfss.project_name, "<unknown>")))
        w(f, "Design       : " + to_str(safe_get(lambda: hfss.design_name, "<unknown>")))
        w(f, "Output Dir   : " + output_dir)
        w(f, "")
        w(f, "[RECOMMENDED READING ORDER]")
        w(f, "1. Variables -> design intent")
        w(f, "2. Smart Summary -> functional structure")
        w(f, "3. Tree With Role -> build hierarchy")
        w(f, "4. Clean Dump -> detailed debug")
        w(f, "5. JSON Export -> structured data for AI/tools")
        w(f, "")
        w(f, "[OBJECT COUNTS]")
        multi_group_count = sum(1 for item in items if len(item.get("groups", [])) > 1)
        w(f, "  Deduplicated Objects = " + to_str(len(items)))
        w(f, "  Multi-Group Objects  = " + to_str(multi_group_count))
        w(f, "  Summary Skipped      = " + to_str(len(SUMMARY_SKIPPED_OBJECTS)))
        if SUMMARY_SKIPPED_OBJECTS:
            preview = SUMMARY_SKIPPED_OBJECTS[:12]
            w(f, "  Skipped Names        = " + ", ".join([to_str(name) for name in preview]))
            remaining = len(SUMMARY_SKIPPED_OBJECTS) - len(preview)
            if remaining > 0:
                w(f, "  Skipped Names Extra  = " + to_str(remaining) + " more")
        w(f, "")
        w(f, "[ROLE COUNTS]")
        for k in ["SUBSTRATE", "GROUND", "PATCH", "FEED", "SHORTING_PIN", "VIA", "AIR_REGION", "OTHER"]:
            if k in counts:
                w(f, "  " + k + " = " + to_str(counts[k]))
        w(f, "")
        w(f, "[EXPORT WARNINGS]")
        if WARNINGS:
            for warning in WARNINGS:
                w(f, "  - " + warning)
        else:
            w(f, "  <none>")
        w(f, "")
        w(f, "[FILES]")
        for key in ["variables", "summary", "tree", "clean", "json", "manifest"]:
            w(f, "  - " + file_map[key])


# =========================================================
# MAIN
# =========================================================
def main():
    args = parse_args()
    print("=== PyAEDT HFSS Exporter ===")

    hfss = get_hfss_session(args)
    if hfss is None:
        print("Could not get an HFSS session.")
        return 1

    oeditor = safe_get(lambda: hfss.modeler.oeditor, None)
    if oeditor is None:
        print("Could not access the 3D Modeler editor.")
        return 1

    base_dir = os.path.abspath(os.path.expandvars(os.path.expanduser(args.output_dir)))
    os.makedirs(base_dir, exist_ok=True)
    output_dir = os.path.join(base_dir, "hfss_export_" + timestamp_file)
    os.makedirs(output_dir, exist_ok=True)

    print("Connected!")
    print("Project :", safe_get(lambda: hfss.project_name, "<unknown>"))
    print("Design  :", safe_get(lambda: hfss.design_name, "<unknown>"))

    items = collect_objects(oeditor)
    if not items:
        add_warning("No modeler objects were collected from the expected 3D Modeler groups.")

    file_map = {
        "variables": os.path.join(output_dir, "01_variables_classified_" + timestamp_file + ".txt"),
        "summary": os.path.join(output_dir, "02_antenna_smart_summary_" + timestamp_file + ".txt"),
        "tree": os.path.join(output_dir, "03_tree_with_role_" + timestamp_file + ".txt"),
        "clean": os.path.join(output_dir, "04_modeler_full_dump_clean_" + timestamp_file + ".txt"),
        "json": os.path.join(output_dir, "05_export_data_" + timestamp_file + ".json"),
        "manifest": os.path.join(output_dir, "00_manifest_" + timestamp_file + ".txt")
    }

    export_variables(file_map["variables"], hfss)
    export_smart_summary(file_map["summary"], items, hfss)
    export_tree_with_role(file_map["tree"], oeditor, hfss)
    export_clean_dump(file_map["clean"], oeditor, hfss)
    export_json(file_map["json"], file_map, items, hfss, output_dir)
    export_manifest(file_map["manifest"], file_map, items, hfss, output_dir)

    print("Done!")
    print("Folder :", output_dir)
    print("Files  :")
    print("  " + file_map["variables"])
    print("  " + file_map["summary"])
    print("  " + file_map["tree"])
    print("  " + file_map["clean"])
    print("  " + file_map["json"])
    print("  " + file_map["manifest"])
    if WARNINGS:
        print("Warnings:")
        for warning in WARNINGS:
            print("  - " + warning)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
