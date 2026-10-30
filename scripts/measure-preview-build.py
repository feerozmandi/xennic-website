"""Observe whole-runner memory/disk during an isolated Docker build, not VPS capacity."""
import os
import shutil
import subprocess
import time


def available():
    with open('/proc/meminfo', encoding='utf-8') as f:
        for line in f:
            if line.startswith('MemAvailable:'):
                return int(line.split()[1]) * 1024
    raise RuntimeError('MemAvailable unavailable')

start = time.monotonic()
start_free = shutil.disk_usage('.').free
initial = available()
minimum = initial
minimum_disk = start_free
build = subprocess.Popen(['docker', 'compose', '-f', 'compose.preview.yml', 'build', 'app'])
while build.poll() is None:
    minimum = min(minimum, available())
    minimum_disk = min(minimum_disk, shutil.disk_usage('.').free)
    time.sleep(0.25)
print(f'BUILD_OBSERVATION cpu_count={os.cpu_count()} elapsed_seconds={time.monotonic()-start:.1f} '
      f'host_initial_available_bytes={initial} host_min_available_bytes={minimum} '
      f'host_available_drop_bytes={max(0, initial-minimum)} host_disk_used_delta_bytes={max(0, start_free-minimum_disk)}', flush=True)
print('Host-wide sampled observation, not build-process peak; includes unrelated runner activity and cache.', flush=True)
raise SystemExit(build.returncode)
