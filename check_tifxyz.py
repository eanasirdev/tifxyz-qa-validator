#!/usr/bin/env python3
"""
     Help menu:
        python check_tifxyz.py --help
"""

import argparse
import math
import os
import sys
import argparse
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


def print_status(level: str, message: str) -> None:
    """Prints formatted, color-coded status messages to stdout."""
    if level == "PASS":
        tag = f"{COLOR_PASS}[PASS]{COLOR_RESET}"
    elif level == "WARNING":
        tag = f"{COLOR_WARN}[WARNING]{COLOR_RESET}"
    elif level == "FAIL":
        tag = f"{COLOR_FAIL}[FAIL]{COLOR_RESET}"
    elif level == "INFO":
        tag = f"{COLOR_INFO}[INFO]{COLOR_RESET}"
    else:
        tag = f"[{level}]"
    print(f"{tag} {message}")


def validate_file(file_path: str) -> bool:
    """Checks if the file exists and is non-empty."""
    if not os.path.exists(file_path):
        print_status("FAIL", f"File does not exist: {file_path}")
        return False

    if not os.path.isfile(file_path):
        print_status("FAIL", f"Path is not a regular file: {file_path}")
        return False

    file_size = os.path.getsize(file_path)
    if file_size == 0:
        print_status("FAIL", f"File is empty (0 bytes): {file_path}")
        return False

    print_status(
        "PASS",
        f"File exists and is readable ({file_size / (1024 * 1024):.2f} MB)",
    )
    return True


def parse_line_coords(line: str, ext: str):
    """
    Extracts numerical X, Y, Z tokens from a line based on file format.
    Returns (x, y, z) tuple or raises ValueError.
    """
    cleaned = line.strip()
    if not cleaned:
        return None  # Skip empty lines

    # Wavefront OBJ parsing
    if ext == ".obj":
        if cleaned.startswith("v "):
            parts = cleaned.split()
            if len(parts) < 4:
                raise ValueError(
                    f"Malformed vertex definition (expected 3 coords, got {len(parts)-1})"
                )
            return float(parts[1]), float(parts[2]), float(parts[3])
        return None  # Ignore non-vertex lines (faces, normals, textures, comments)

    # Standard ASCII/TIFXYZ/XYZ parsing (space, comma, or tab delimited)
    if cleaned.startswith("#") or cleaned.startswith("//"):
        return None  # Comment lines

    # Normalize delimiters (commas to spaces)
    normalized = cleaned.replace(",", " ")
    parts = normalized.split()

    if len(parts) < 3:
        raise ValueError(
            f"Insufficient coordinate fields (expected at least 3, got {len(parts)})"
        )

    return float(parts[0]), float(parts[1]), float(parts[2])


def validate_coordinates(file_path: str, max_coord_limit: float):
    """
    Streams file line-by-line, computing bounding box and detecting format/numerical errors.
    """
    _, ext = os.path.splitext(file_path.lower())

    min_x = min_y = min_z = float("inf")
    max_x = max_y = max_z = float("-inf")

    total_lines = 0
    valid_points = 0
    nan_inf_errors = 0
    format_errors = 0

    first_errors = []

    print_status("INFO", f"Parsing file structure for format extension '{ext}'...")

    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            for line_idx, line in enumerate(f, start=1):
                total_lines += 1

                try:
                    coords = parse_line_coords(line, ext)
                    if coords is None:
                        continue

                    x, y, z = coords

                    # Flag NaN or Infinity
                    if (
                        math.isnan(x)
                        or math.isnan(y)
                        or math.isnan(z)
                        or math.isinf(x)
                        or math.isinf(y)
                        or math.isinf(z)
                    ):
                        nan_inf_errors += 1
                        if len(first_errors) < 5:
                            first_errors.append(
                                f"Line {line_idx}: NaN or Inf encountered -> ({x}, {y}, {z})"
                            )
                        continue

                    # Update bounding box streaming values
                    if x < min_x:
                        min_x = x
                    if x > max_x:
                        max_x = x
                    if y < min_y:
                        min_y = y
                    if y > max_y:
                        max_y = y
                    if z < min_z:
                        min_z = z
                    if z > max_z:
                        max_z = z

                    valid_points += 1

                except ValueError as ve:
                    format_errors += 1
                    if len(first_errors) < 5:
                        first_errors.append(
                            f"Line {line_idx}: Formatting error -> {str(ve)}"
                        )

    except Exception as e:
        print_status("FAIL", f"Failed to read file due to system error: {str(e)}")
        return None

    # Print structural evaluation results
    if format_errors > 0 or nan_inf_errors > 0:
        print_status(
            "FAIL",
            f"Parsing encountered errors: {format_errors} invalid syntax lines, {nan_inf_errors} NaN/Inf values.",
        )
        for err in first_errors:
            print(f"       -> {err}")
    else:
        print_status(
            "PASS",
            f"Successfully parsed {valid_points:,} valid 3D points from {total_lines:,} lines.",
        )

    if valid_points == 0:
        print_status(
            "FAIL", "No valid 3D coordinate points were extracted from file."
        )
        return None

    return {
        "valid_points": valid_points,
        "format_errors": format_errors,
        "nan_inf_errors": nan_inf_errors,
        "bbox": (min_x, max_x, min_y, max_y, min_z, max_z),
    }


def evaluate_bounding_box(bbox, allow_negative: bool, max_coord_limit: float):
    """
    Evaluates computed bounding box coordinates against domain constraints.
    Returns list of warning strings.
    """
    min_x, max_x, min_y, max_y, min_z, max_z = bbox
    warnings = []

    print(
        f"\n{COLOR_BOLD}=== 3D Bounding Box Spatial Summary ==={COLOR_RESET}"
    )
    print(f"  X Range: [{min_x:12.3f}  to  {max_x:12.3f}]  (Delta: {max_x - min_x:.3f})")
    print(f"  Y Range: [{min_y:12.3f}  to  {max_y:12.3f}]  (Delta: {max_y - min_y:.3f})")
    print(f"  Z Range: [{min_z:12.3f}  to  {max_z:12.3f}]  (Delta: {max_z - min_z:.3f})")
    print("-" * 50)

    # Check negative coordinate bounds
    if not allow_negative:
        if min_x < 0 or min_y < 0 or min_z < 0:
            warnings.append(
                f"Negative coordinates detected (Min X: {min_x:.2f}, Y: {min_y:.2f}, Z: {min_z:.2f})."
            )

    # Check unrealistically large magnitudes
    largest_val = max(
        abs(min_x),
        abs(max_x),
        abs(min_y),
        abs(max_y),
        abs(min_z),
        abs(max_z),
    )
    if largest_val > max_coord_limit:
        warnings.append(
            f"Coordinate magnitude ({largest_val:.2f}) exceeds realistic threshold limit ({max_coord_limit:.2f})."
        )

    return warnings


def main():
    parser = argparse.ArgumentParser(
        description="QA/Validation script for spatial mesh/point files (.tifxyz, .xyz, .obj)."
    )
    parser.add_argument(
        "filepath", help="Path to the coordinate file (.tifxyz, .xyz, or .obj)"
    )
    parser.add_argument(
        "--max-coord",
        type=float,
        default=100000.0,
        help="Threshold for unrealistically large coordinate values (default: 100000.0)",
    )
    parser.add_argument(
        "--allow-negative",
        action="store_true",
        help="Suppress warnings when negative coordinates are present.",
    )

    args = parser.parse_args()

    print(f"\n{COLOR_BOLD}Starting Spatial Validation: {args.filepath}{COLOR_RESET}\n" + "=" * 50)

    # Step 1: File Existence & Non-empty check
    if not validate_file(args.filepath):
        print(f"\n{COLOR_BOLD}FINAL VERDICT:{COLOR_RESET} {COLOR_FAIL}[FAIL]{COLOR_RESET}")
        sys.exit(1)

    # Step 2: Coordinate & Syntax Validation
    result = validate_coordinates(args.filepath, args.max_coord)

    if result is None or result["format_errors"] > 0 or result["nan_inf_errors"] > 0:
        print(f"\n{COLOR_BOLD}FINAL VERDICT:{COLOR_RESET} {COLOR_FAIL}[FAIL]{COLOR_RESET}")
        sys.exit(1)

    # Step 3: Bounding Box Evaluation & Bounds Warnings
    bbox_warnings = evaluate_bounding_box(
        result["bbox"], args.allow_negative, args.max_coord
    )

    if bbox_warnings:
        for warn in bbox_warnings:
            print_status("WARNING", warn)
        print(f"\n{COLOR_BOLD}FINAL VERDICT:{COLOR_RESET} {COLOR_WARN}[WARNING]{COLOR_RESET} (Passes schema check, but triggered spatial warnings)")
        sys.exit(0)

    print_status("PASS", "All spatial QA checks passed successfully with zero errors or warnings.")
    print(f"\n{COLOR_BOLD}FINAL VERDICT:{COLOR_RESET} {COLOR_PASS}[PASS]{COLOR_RESET}")
    sys.exit(0)


if __name__ == "__main__":
    main()
