#!/usr/bin/env python3
"""
Spatial Mesh QA Validator for Vesuvius Challenge data.

Supports three distinct input modes, each validated with the checks that
actually make sense for that format:

  1. tifxyz DIRECTORY  - the real VC3D quadmesh format: a folder containing
     x.tif / y.tif / z.tif (float grid layers, one value per mesh vertex)
     and usually a meta.json. Requires the optional `numpy` + `tifffile`
     packages (see README) - without them this mode cannot run correctly,
     and the script says so rather than guessing.
  2. .obj file          - Wavefront mesh. Only `v ` vertex lines are
     extracted and checked; face/normal/texture lines are read but NOT
     validated (see README for scope).
  3. .xyz / generic text - a plain whitespace- or comma-delimited list of
     X Y Z points per line. This is a generic point-cloud sanity check,
     not a mesh/topology check.

Help menu:
    python check_tifxyz.py --help
"""

import argparse
import json
import math
import os
import sys

# Enable ANSI escape sequences on Windows Command Prompt
os.system('')

# Terminal Color Definitions (ANSI)
COLOR_PASS = "\033[92m"
COLOR_WARN = "\033[93m"
COLOR_FAIL = "\033[91m"
COLOR_INFO = "\033[96m"
COLOR_BOLD = "\033[1m"
COLOR_RESET = "\033[0m"

REQUIRED_TIF_LAYERS = ("x.tif", "y.tif", "z.tif")


def print_status(level: str, message: str) -> None:
    """Prints formatted, color-coded status messages to stdout."""
    tags = {
        "PASS": f"{COLOR_PASS}[PASS]{COLOR_RESET}",
        "WARNING": f"{COLOR_WARN}[WARNING]{COLOR_RESET}",
        "FAIL": f"{COLOR_FAIL}[FAIL]{COLOR_RESET}",
        "INFO": f"{COLOR_INFO}[INFO]{COLOR_RESET}",
    }
    print(f"{tags.get(level, f'[{level}]')} {message}")


def final_verdict(level: str) -> None:
    color = {"PASS": COLOR_PASS, "WARNING": COLOR_WARN, "FAIL": COLOR_FAIL}[level]
    print(f"\n{COLOR_BOLD}FINAL VERDICT:{COLOR_RESET} {color}[{level}]{COLOR_RESET}")


# --------------------------------------------------------------------------
# Mode detection
# --------------------------------------------------------------------------

def detect_mode(path: str):
    """
    Returns one of: 'tifxyz_dir', 'obj', 'xyz_text', or None (with a printed
    explanation) if the input can't be meaningfully classified.
    """
    if os.path.isdir(path):
        return "tifxyz_dir"

    if os.path.isfile(path):
        _, ext = os.path.splitext(path.lower())
        if ext == ".obj":
            return "obj"
        if ext == ".tifxyz":
            # A real tifxyz is a directory of TIFF layers, never a single
            # flat file. Rather than silently parsing this as generic text
            # (which was the old, misleading behavior), say so plainly.
            print_status(
                "FAIL",
                "'.tifxyz' is a directory-based format (x.tif, y.tif, z.tif, "
                "meta.json), not a single flat file. You passed a single file "
                f"with a '.tifxyz' extension: {path}",
            )
            print_status(
                "INFO",
                "If you meant to validate a generic XYZ point list, rename it "
                "to '.xyz' or pass it explicitly - this tool no longer treats "
                "'.tifxyz' files as plain text, since that doesn't match the "
                "real Vesuvius Challenge / VC3D format.",
            )
            return None
        # .xyz and anything else falls back to generic point-list parsing
        return "xyz_text"

    print_status("FAIL", f"Path does not exist: {path}")
    return None


# --------------------------------------------------------------------------
# Mode 1: real tifxyz directory (x.tif / y.tif / z.tif [+ meta.json])
# --------------------------------------------------------------------------

def validate_tifxyz_dir(dir_path: str, max_coord_limit: float, allow_negative: bool):
    """
    Validates a real tifxyz quadmesh directory:
      - presence of x.tif / y.tif / z.tif (+ optional meta.json)
      - the three layers form a consistent grid (same shape/dtype)
      - NaN masks agree across x/y/z (a real corruption signal - a vertex
        that's defined in one channel but undefined in another means the
        grid is broken, whereas NaNs that agree across all three are just
        the normal "outside the mesh" masking that tifxyz uses)
      - no Inf values anywhere
      - bounding box computed only over valid (non-NaN) vertices
    """
    print_status("INFO", f"Detected directory input - validating as tifxyz quadmesh: {dir_path}")

    missing = [name for name in REQUIRED_TIF_LAYERS if not os.path.isfile(os.path.join(dir_path, name))]
    if missing:
        print_status(
            "FAIL",
            f"Directory is missing required tifxyz layer(s): {', '.join(missing)}",
        )
        return None
    print_status("PASS", "Found x.tif, y.tif, and z.tif layers.")

    meta_path = os.path.join(dir_path, "meta.json")
    if os.path.isfile(meta_path):
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            print_status("PASS", f"meta.json present and valid JSON ({len(meta)} top-level key(s)).")
        except (json.JSONDecodeError, OSError) as e:
            print_status("WARNING", f"meta.json present but could not be parsed: {e}")
    else:
        print_status("WARNING", "No meta.json found alongside the TIFF layers (often present in real segments).")

    # Real TIFF decoding requires numpy + tifffile. This is the honest
    # trade-off for actually supporting the format instead of faking it:
    # we no longer claim "zero dependencies" for this mode. .obj and .xyz
    # validation below remain pure standard library.
    try:
        import numpy as np
        import tifffile
    except ImportError:
        print_status(
            "FAIL",
            "tifxyz directory validation requires the optional 'numpy' and "
            "'tifffile' packages, which are not installed.",
        )
        print_status("INFO", "Install with: pip install numpy tifffile")
        return None

    layers = {}
    for name in REQUIRED_TIF_LAYERS:
        layer_path = os.path.join(dir_path, name)
        try:
            layers[name] = tifffile.imread(layer_path)
        except Exception as e:
            print_status("FAIL", f"Failed to read {name}: {e}")
            return None

    x, y, z = layers["x.tif"], layers["y.tif"], layers["z.tif"]

    # Grid topology check: this is the actual "quadmesh" guarantee tifxyz
    # is supposed to provide, and it's the check a plain point-list
    # validator has no way to make.
    if not (x.shape == y.shape == z.shape):
        print_status(
            "FAIL",
            f"Layer shapes do not match - x.tif: {x.shape}, y.tif: {y.shape}, "
            f"z.tif: {z.shape}. A valid tifxyz grid requires identical shapes "
            "across all three layers.",
        )
        return None
    print_status("PASS", f"x/y/z layer shapes agree - grid is {x.shape[1]}x{x.shape[0]} vertices.")

    if not (x.dtype.kind == "f" and y.dtype.kind == "f" and z.dtype.kind == "f"):
        print_status(
            "WARNING",
            f"Expected floating-point layers, got dtypes x:{x.dtype} y:{y.dtype} z:{z.dtype}.",
        )

    nan_x, nan_y, nan_z = np.isnan(x), np.isnan(y), np.isnan(z)
    nan_agree = nan_x == nan_y
    nan_agree &= nan_x == nan_z
    inconsistent_nan = int(np.count_nonzero(~nan_agree))

    if inconsistent_nan > 0:
        print_status(
            "FAIL",
            f"{inconsistent_nan:,} vertex position(s) have NaN in some layers "
            "but not others - the grid is inconsistently masked, which usually "
            "indicates a corrupted or partially-written segment.",
        )
        return None

    valid_mask = ~nan_x  # NaN status agrees across layers, so any one works
    total_vertices = x.size
    valid_vertices = int(np.count_nonzero(valid_mask))
    masked_vertices = total_vertices - valid_vertices

    if masked_vertices > 0:
        print_status(
            "INFO",
            f"{masked_vertices:,} / {total_vertices:,} grid cells are masked "
            "(NaN) outside the traced surface - this is expected for tifxyz "
            "and is not treated as an error.",
        )

    if valid_vertices == 0:
        print_status("FAIL", "Every vertex in the grid is masked - no valid surface data found.")
        return None

    inf_count = int(
        np.count_nonzero(np.isinf(x[valid_mask]))
        + np.count_nonzero(np.isinf(y[valid_mask]))
        + np.count_nonzero(np.isinf(z[valid_mask]))
    )
    if inf_count > 0:
        print_status("FAIL", f"{inf_count:,} Inf value(s) found among valid (non-NaN) vertices.")
        return None

    print_status(
        "PASS",
        f"{valid_vertices:,} valid vertices, zero NaN/Inf inconsistencies or errors.",
    )

    bbox = (
        float(np.min(x[valid_mask])), float(np.max(x[valid_mask])),
        float(np.min(y[valid_mask])), float(np.max(y[valid_mask])),
        float(np.min(z[valid_mask])), float(np.max(z[valid_mask])),
    )

    return {"valid_points": valid_vertices, "format_errors": 0, "nan_inf_errors": 0, "bbox": bbox}


# --------------------------------------------------------------------------
# Mode 2 & 3: .obj vertices / generic .xyz text - stdlib only
# --------------------------------------------------------------------------

def parse_line_coords(line: str, mode: str):
    """
    Extracts numerical X, Y, Z tokens from one line.
    Returns (x, y, z) tuple, None (skip line), or raises ValueError.
    """
    cleaned = line.strip()
    if not cleaned:
        return None

    if mode == "obj":
        if cleaned.startswith("v "):
            parts = cleaned.split()
            if len(parts) < 4:
                raise ValueError(
                    f"Malformed vertex definition (expected 3 coords, got {len(parts)-1})"
                )
            return float(parts[1]), float(parts[2]), float(parts[3])
        return None  # f/vn/vt/comment lines: read, but not validated (see README)

    # xyz_text mode
    if cleaned.startswith("#") or cleaned.startswith("//"):
        return None
    normalized = cleaned.replace(",", " ")
    parts = normalized.split()
    if len(parts) < 3:
        raise ValueError(
            f"Insufficient coordinate fields (expected at least 3, got {len(parts)})"
        )
    return float(parts[0]), float(parts[1]), float(parts[2])


def validate_point_file(file_path: str, mode: str):
    """Streams an .obj or .xyz-style text file line-by-line."""
    min_x = min_y = min_z = float("inf")
    max_x = max_y = max_z = float("-inf")

    total_lines = 0
    valid_points = 0
    nan_inf_errors = 0
    format_errors = 0
    first_errors = []

    label = "OBJ vertex" if mode == "obj" else "XYZ point"
    print_status("INFO", f"Parsing as {label} list (point-level checks only, no mesh topology).")

    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            for line_idx, line in enumerate(f, start=1):
                total_lines += 1
                try:
                    coords = parse_line_coords(line, mode)
                    if coords is None:
                        continue
                    x, y, z = coords

                    if any(math.isnan(v) or math.isinf(v) for v in (x, y, z)):
                        nan_inf_errors += 1
                        if len(first_errors) < 5:
                            first_errors.append(f"Line {line_idx}: NaN or Inf encountered -> ({x}, {y}, {z})")
                        continue

                    min_x, max_x = min(min_x, x), max(max_x, x)
                    min_y, max_y = min(min_y, y), max(max_y, y)
                    min_z, max_z = min(min_z, z), max(max_z, z)
                    valid_points += 1

                except ValueError as ve:
                    format_errors += 1
                    if len(first_errors) < 5:
                        first_errors.append(f"Line {line_idx}: Formatting error -> {ve}")

    except OSError as e:
        print_status("FAIL", f"Failed to read file due to system error: {e}")
        return None

    if format_errors > 0 or nan_inf_errors > 0:
        print_status(
            "FAIL",
            f"Parsing encountered errors: {format_errors} invalid syntax lines, "
            f"{nan_inf_errors} NaN/Inf values.",
        )
        for err in first_errors:
            print(f"       -> {err}")
    else:
        print_status("PASS", f"Successfully parsed {valid_points:,} valid points from {total_lines:,} lines.")

    if valid_points == 0:
        print_status("FAIL", "No valid 3D coordinate points were extracted from file.")
        return None

    return {
        "valid_points": valid_points,
        "format_errors": format_errors,
        "nan_inf_errors": nan_inf_errors,
        "bbox": (min_x, max_x, min_y, max_y, min_z, max_z),
    }


# --------------------------------------------------------------------------
# Shared bounding-box evaluation
# --------------------------------------------------------------------------

def evaluate_bounding_box(bbox, allow_negative: bool, max_coord_limit: float):
    min_x, max_x, min_y, max_y, min_z, max_z = bbox
    warnings = []

    print(f"\n{COLOR_BOLD}=== 3D Bounding Box Spatial Summary ==={COLOR_RESET}")
    print(f"  X Range: [{min_x:12.3f}  to  {max_x:12.3f}]  (Delta: {max_x - min_x:.3f})")
    print(f"  Y Range: [{min_y:12.3f}  to  {max_y:12.3f}]  (Delta: {max_y - min_y:.3f})")
    print(f"  Z Range: [{min_z:12.3f}  to  {max_z:12.3f}]  (Delta: {max_z - min_z:.3f})")
    print("-" * 50)

    if not allow_negative and (min_x < 0 or min_y < 0 or min_z < 0):
        warnings.append(
            f"Negative coordinates detected (Min X: {min_x:.2f}, Y: {min_y:.2f}, Z: {min_z:.2f})."
        )

    largest_val = max(abs(min_x), abs(max_x), abs(min_y), abs(max_y), abs(min_z), abs(max_z))
    if largest_val > max_coord_limit:
        warnings.append(
            f"Coordinate magnitude ({largest_val:.2f}) exceeds realistic threshold limit ({max_coord_limit:.2f})."
        )

    return warnings


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description=(
            "QA/validation for Vesuvius Challenge spatial data: real tifxyz "
            "quadmesh directories, .obj vertex lists, and generic .xyz point files."
        )
    )
    parser.add_argument(
        "path",
        help="Path to a tifxyz directory (containing x.tif/y.tif/z.tif), or an .obj/.xyz file.",
    )
    parser.add_argument(
        "--max-coord", type=float, default=100000.0,
        help="Threshold for unrealistically large coordinate values (default: 100000.0)",
    )
    parser.add_argument(
        "--allow-negative", action="store_true",
        help="Suppress warnings when negative coordinates are present.",
    )
    args = parser.parse_args()

    print(f"\n{COLOR_BOLD}Starting Spatial Validation: {args.path}{COLOR_RESET}\n" + "=" * 50)

    mode = detect_mode(args.path)
    if mode is None:
        final_verdict("FAIL")
        sys.exit(1)

    if mode == "tifxyz_dir":
        result = validate_tifxyz_dir(args.path, args.max_coord, args.allow_negative)
    else:
        result = validate_point_file(args.path, mode)

    if result is None or result["format_errors"] > 0 or result["nan_inf_errors"] > 0:
        final_verdict("FAIL")
        sys.exit(1)

    bbox_warnings = evaluate_bounding_box(result["bbox"], args.allow_negative, args.max_coord)

    if bbox_warnings:
        for warn in bbox_warnings:
            print_status("WARNING", warn)
        print(
            f"\n{COLOR_BOLD}FINAL VERDICT:{COLOR_RESET} {COLOR_WARN}[WARNING]{COLOR_RESET} "
            "(Passes schema check, but triggered spatial warnings)"
        )
        sys.exit(0)

    print_status("PASS", "All spatial QA checks passed successfully with zero errors or warnings.")
    final_verdict("PASS")
    sys.exit(0)


if __name__ == "__main__":
    main()
