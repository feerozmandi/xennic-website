"""Publish only non-secret resource observations as GitHub check annotations."""
import re
import sys
from pathlib import Path

lines = Path(sys.argv[1]).read_text().splitlines()
for prefix in ('BUILD_OBSERVATION ', 'Image size bytes: ', 'idle '):
    for line in lines:
        if line.startswith(prefix):
            print(f'::notice title=PreviewResource::{line}', flush=True)

for kind, service in [('migration', None), ('representative', '-app-'), ('representative', '-postgres-')]:
    found = []
    for line in lines:
        if not line.startswith(kind + ' ') or (service and service not in line):
            continue
        m = re.search(r'([\d.]+)\s*(KiB|MiB|GiB)\s*/', line)
        if m:
            value = float(m[1]) * {'KiB': 1 / 1024, 'MiB': 1, 'GiB': 1024}[m[2]]
            found.append(value)
    label = kind + (f' {service.strip("-")}' if service else '')
    print(f'::notice title=PreviewResource::{label} sampled_peak_MiB={max(found):.2f} samples={len(found)}' if found
          else f'::warning title=PreviewResource::{label} no samples captured', flush=True)
