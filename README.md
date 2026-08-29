# TIFXYZ & Spatial Mesh QA Validator

A lightweight, zero-dependency Python QA tool designed to validate 3D coordinate files (`.tifxyz`, `.xyz`, `.obj`) before running processing or segmentation pipelines in the Vesuvius Challenge.

## Features
- **File Integrity:** Verifies file presence and non-zero byte size.
- **Syntax & Numerical Validation:** Streams line-by-line data to detect formatting errors, missing fields, `NaN`, and `Inf` values without high memory usage.
- **Bounding Box Diagnostics:** Automatically computes 3D bounding boxes (X, Y, Z) and alerts on out-of-bound or unexpected negative coordinates.
- **Pipeline Ready:** Returns deterministic exit codes (`0` for PASS/WARNING, `1` for FAIL) for seamless integration into automated scripts and CI/CD pipelines.
- **Cross-Platform:** Works natively across Windows, macOS, and Linux with colored terminal output.

## Installation

No external libraries or dependencies are required. Runs out-of-the-box with Python 3.7+.

```bash
git clone https://github.com/eanasirdev/tifxyz-qa-validator.git
cd tifxyz-qa-validator
```

## Usage

### Basic Usage

Validate a spatial coordinate file:

```bash
python check_tifxyz.py path/to/data.tifxyz
```

# Custom Bounds Check

Validate mesh files with custom coordinate thresholds.

```bash
python check_tifxyz.py path/to/mesh.obj --max-coord 500000 --allow-negative
```

## Sample Output

```plaintext
Starting Spatial Validation: sample.tifxyz
==================================================
[PASS] File exists and is readable (0.01 MB)
[INFO] Parsing file structure for format extension '.tifxyz'...
[PASS] Successfully parsed 3 valid 3D points from 3 lines.

=== 3D Bounding Box Spatial Summary ===
  X Range: [     100.500  to       102.500]  (Delta: 2.000)
  Y Range: [     200.000  to       210.200]  (Delta: 10.200)
  Z Range: [     300.250  to       302.750]  (Delta: 2.500)
--------------------------------------------------
[PASS] All spatial QA checks passed successfully with zero errors or warnings.

FINAL VERDICT: [PASS]
```
