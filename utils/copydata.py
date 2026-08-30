#!/usr/bin/env python3
"""Copy, organise, compress and verify logger SD cards in the field.

A longer-running alternative to ``copydata.sh`` for large card sets.
Plug in the SD cards and the destination drive,
run this, walk away. Every WAV is streamed off its card, compressed losslessly,
written into a per-deployment folder on the destination, and hashed on the way
past -- that hash costs nothing extra, because the file is being read anyway.

A spread of those files is then read back and re-hashed on the spot
(``--verify sample``, the default: 5% of each deployment, plus every sidecar and
sidecar). Reading *everything* back inline doubles the run -- about
12 h rather than 6 h on four 500 GB cards, all of it with the cards still in the
reader -- so the default is sized to catch a card or a destination going bad
while it is happening, and the exhaustive pass is left for afterwards::

    copydata.py verify DEST --only-unverified --jobs 4

That pass does not need the cards, so it runs once they are back in your pocket.
Run it before you reformat anything: ``--verify sample`` defers the proof, it
does not skip it.

Design notes for the field
--------------------------
* **Standard library only.** No ``pip install`` on a laptop in the Amazon.
  The only external programs are the compressor binaries -- ``wavpack`` /
  ``wvunpack`` by default, with ``zstd`` as the fallback for WAVs an audio
  codec cannot represent -- and ``--codec none`` needs nothing at all.
* **WavPack by default** because on these 16ch/48kHz logger WAVs it saves more
  than ``gzip -6`` *and* runs ~3.5x faster per core, and ``wvunpack`` restores a
  byte-identical ``.wav`` including the logger's custom ``LIST``/``INFO``
  chunk. See ``--help`` for the measured codec table, and
  ``utils/README_copydata.md`` for the full comparison.
* **Never writes to a source card.** The only destructive thing this script can
  do is overwrite a file it previously wrote itself, and only with
  ``--overwrite``.
* **Resumable.** Re-running skips files the manifest records as completely
  written, so an interrupted transfer costs you only the file it died on.
  (Written, not verified: under the default spot check most files are never
  read back, and those must not be copied a second time.)
* **Fails loudly.** An empty card list, a full destination or a
  failed round-trip check is an error you get told about, not a silent success.

Typical use::

    python3 copydata.py copy /run/media/me/FIELD_HDD/flona2025
    python3 copydata.py verify /run/media/me/FIELD_HDD/flona2025 \
        --only-unverified --jobs 4          # before reformatting any card
    python3 copydata.py restore /run/media/me/FIELD_HDD/flona2025 ./unpacked

Run ``python3 copydata.py <command> --help`` for the full option list.
"""

from __future__ import annotations

import argparse
import errno
import functools
import hashlib
import json
import math
import os
import re
import shutil
import struct
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, NoReturn, Optional, Sequence, Tuple

MANIFEST_NAME = "copy_manifest.jsonl"
LOG_DIR_NAME = "copy_logs"
CHUNK = 1 << 22  # 4 MiB streaming chunk
WAV_SUFFIXES = {".wav"}

# --------------------------------------------------------------------------
# logging
# --------------------------------------------------------------------------


class Tee:
    """Print to stdout and, once a destination is known, to a log file."""

    def __init__(self) -> None:
        self._fh: Optional[object] = None
        self._lock = threading.Lock()

    def open(self, dest: Path) -> None:
        d = dest / LOG_DIR_NAME
        d.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
        self._fh = open(d / f"copy_{stamp}.log", "a", encoding="utf-8")

    def __call__(self, msg: str = "") -> None:
        with self._lock:
            print(msg, flush=True)
            if self._fh is not None:
                self._fh.write(msg + "\n")
                self._fh.flush()


log = Tee()


def die(msg: str, code: int = 1) -> NoReturn:
    log(f"ERROR: {msg}")
    raise SystemExit(code)


def human(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024 or unit == "TB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{int(n)} B"
        n /= 1024
    return f"{n:.1f} TB"


def hms(seconds: float) -> str:
    seconds = int(max(seconds, 0))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}h{m:02d}m{s:02d}s" if h else f"{m}m{s:02d}s"


# --------------------------------------------------------------------------
# codecs
# --------------------------------------------------------------------------


@functools.lru_cache(maxsize=1)
def wavpack_has_threads() -> bool:
    """Whether the installed wavpack understands ``--threads``.

    The flag only exists from wavpack 5.7.0 on; older builds abort with
    "unknown option" instead of ignoring it.
    """
    try:
        r = subprocess.run(
            ["wavpack", "--help"], capture_output=True, text=True, check=False
        )
    except OSError:
        return False
    return "--threads" in (r.stdout + r.stderr)


@dataclass(frozen=True)
class Codec:
    """A lossless compressor.

    ``stream`` codecs read the WAV on stdin and write to stdout, which lets us
    hash the source during the single read pass. ``wavpack`` is file-to-file
    because it needs to seek its own output.
    """

    name: str
    suffix: str
    default_level: int
    levels: Tuple[int, ...]
    stream: bool = True
    binary: str = ""

    def compress_cmd(self, level: int, threads: int, dst: Path) -> List[str]:
        if self.name == "zstd":
            return ["zstd", f"-{level}", "--long", f"-T{threads}", "-q", "-c"]
        if self.name == "xz":
            return ["xz", f"-{level}", f"-T{threads}", "--block-size=16MiB", "-c"]
        if self.name == "gzip":
            return ["gzip", f"-{level}", "-c"]
        if self.name == "wavpack":
            flags = {1: ["-f"], 2: [], 3: ["-h"], 4: ["-h", "-x4"], 5: ["-hh", "-x6"]}[level]
            if wavpack_has_threads():
                flags.append(f"--threads={min(threads, 12)}")
            return ["wavpack", *flags, "-q", "-y", "-o", str(dst)]
        raise AssertionError(self.name)

    def decompress_cmd(self, src: Path, dst: Optional[Path] = None) -> List[str]:
        if self.name == "zstd":
            return ["zstd", "-dq", "--long", "-c", str(src)]
        if self.name == "xz":
            return ["xz", "-dc", str(src)]
        if self.name == "gzip":
            return ["gzip", "-dc", str(src)]
        if self.name == "wavpack":
            return ["wvunpack", "-q", "-y", "-o", str(dst) if dst else "-", str(src)]
        raise AssertionError(self.name)


CODECS: Dict[str, Codec] = {
    "zstd": Codec("zstd", ".zst", 12, tuple(range(1, 20)), binary="zstd"),
    "xz": Codec("xz", ".xz", 6, tuple(range(0, 10)), binary="xz"),
    "gzip": Codec("gzip", ".gz", 6, tuple(range(1, 10)), binary="gzip"),
    # wavpack "levels" are our own 1..5 shorthand for -f / default / -h / -hx4 / -hhx6
    "wavpack": Codec("wavpack", ".wv", 1, (1, 2, 3, 4, 5), stream=False, binary="wavpack"),
    "none": Codec("none", "", 0, (0,), binary=""),
}


WAVPACK_FLAGS = {1: "-f", 2: "(default)", 3: "-h", 4: "-h -x4", 5: "-hh -x6"}


def describe_codec(codec: Codec, level: int) -> str:
    """Human-readable codec spec -- wavpack levels are our own 1..5 shorthand."""
    if codec.name == "none":
        return "none (plain copy)"
    if codec.name == "wavpack":
        return f"wavpack {WAVPACK_FLAGS.get(level, level)}"
    return f"{codec.name} -{level}"


def require_codec(codec: Codec) -> None:
    if codec.name == "none":
        return
    missing = [b for b in {codec.binary, *(["wvunpack"] if codec.name == "wavpack" else [])} if not shutil.which(b)]
    if missing:
        die(
            f"codec '{codec.name}' needs {', '.join(missing)} on PATH but it is not installed.\n"
            f"       Install it, or pick another codec with --codec "
            f"({', '.join(CODECS)}). '--codec none' needs no external tools."
        )


# --------------------------------------------------------------------------
# WAV / RIFF inspection
# --------------------------------------------------------------------------


@dataclass
class WavInfo:
    """What we can learn from a logger WAV without reading the samples."""

    channels: int = 0
    rate: int = 0
    bits: int = 0
    data_bytes: int = 0
    info: Dict[str, str] = field(default_factory=dict)

    @property
    def logger_mac(self) -> str:
        return self.info.get("IMAC", "")

    @property
    def datetime_str(self) -> str:
        return self.info.get("DTIM", "")

    @property
    def duration_s(self) -> float:
        frame = self.channels * self.bits // 8
        return self.data_bytes / (self.rate * frame) if self.rate and frame else 0.0


def read_wav_info(path: Path) -> Optional[WavInfo]:
    """Parse the RIFF chunk table. Returns None if this is not a RIFF/WAVE file.

    Deliberately tolerant: a header that disagrees with the file size gives the
    duration from the bytes that are actually there rather than raising, so one
    odd file cannot stop a card from being read.
    """
    try:
        size = path.stat().st_size
        with open(path, "rb") as f:
            head = f.read(12)
            if len(head) < 12 or head[:4] != b"RIFF" or head[8:12] != b"WAVE":
                return None
            wi = WavInfo()
            pos = 12
            while pos + 8 <= size:
                f.seek(pos)
                hdr = f.read(8)
                if len(hdr) < 8:
                    break
                cid, csize = hdr[:4], int.from_bytes(hdr[4:8], "little")
                if cid == b"fmt " and csize >= 16:
                    _fmt, ch, rate, _br, _al, bits = struct.unpack("<HHIIHH", f.read(16))
                    wi.channels, wi.rate, wi.bits = ch, rate, bits
                elif cid == b"LIST" and csize <= (1 << 20):
                    body = f.read(csize)
                    if body[:4] == b"INFO":
                        off = 4
                        while off + 8 <= len(body):
                            key = body[off : off + 4].decode("ascii", "replace")
                            n = int.from_bytes(body[off + 4 : off + 8], "little")
                            val = body[off + 8 : off + 8 + n].split(b"\0")[0]
                            wi.info[key] = val.decode("utf-8", "replace")
                            off += 8 + n + (n & 1)
                elif cid == b"data":
                    available = size - (pos + 8)
                    wi.data_bytes = min(csize, max(available, 0))
                    break  # data is last; do not scan past it
                pos += 8 + csize + (csize & 1)
            return wi
    except OSError:
        return None


def logger_tag(wi: Optional[WavInfo], filename: str) -> str:
    """A short, stable id for the logger that wrote a file.

    Prefers the Teensy MAC from the WAV metadata (unique per board and immune
    to a dead RTC); falls back to the ``loggerNN`` filename prefix.
    """
    if wi and wi.logger_mac:
        return "mac" + wi.logger_mac.replace(":", "")[-6:]
    # <site>-<grid>-<dev>-<timestamp>: the third field is the device. Taking the
    # first field instead would tag every logger on a site identically, which is
    # exactly backwards for telling two of them apart.
    parts = filename.split("-")
    if len(parts) >= 4 and re.fullmatch(r"[A-Za-z]+\d+", parts[2]):
        return parts[2].lower()
    m = re.match(r"([A-Za-z]+)(\d+)[-_]", filename)
    if m:
        return f"{m.group(1).lower()}{int(m.group(2)):02d}"
    return "unknown"


# --------------------------------------------------------------------------
# source discovery
# --------------------------------------------------------------------------


@dataclass
class Source:
    mount: Path          # where the card is mounted
    label: str           # mountpoint basename -- unique per card, used for grouping/naming
    volume: str = ""     # filesystem label, for display only (often "NO NAME")
    size_hint: str = ""

    @property
    def display(self) -> str:
        return f"{self.mount}" + (f" ({self.volume})" if self.volume and self.volume != self.label else "")


SYSTEM_MOUNTS = {"/", "/boot", "/boot/efi", "/home", "/usr", "/var", "/tmp", "/nix", "/srv", "/opt"}
PROBE_MAX_DEPTH = 4
PROBE_MAX_ENTRIES = 20000
PROBE_MAX_SECONDS = 5.0


def looks_like_card(mount: Path) -> bool:
    """Cheap, *bounded* check for 'does this mount hold logger WAVs?'.

    Auto-detection must never wander into a multi-terabyte archive disk, so the
    probe gives up after a few thousand entries / a few seconds / four levels
    deep. A real SD card has its WAVs within a directory or two of the root, so
    a card always trips this long before the budget runs out. Explicit
    --source paths skip the probe entirely.
    """
    t0 = time.time()
    seen = 0
    root_depth = len(mount.parts)
    for dirpath, dirnames, filenames in os.walk(mount):
        if len(Path(dirpath).parts) - root_depth >= PROBE_MAX_DEPTH:
            dirnames[:] = []
        dirnames[:] = [d for d in dirnames if not d.startswith(".")
                       and d not in {"System Volume Information", "$RECYCLE.BIN", "lost+found"}]
        for fn in filenames:
            if fn.lower().endswith(".wav"):
                return True
            seen += 1
            if seen > PROBE_MAX_ENTRIES:
                return False
        if time.time() - t0 > PROBE_MAX_SECONDS:
            return False
    return False


def _lsblk_mounts() -> List[Tuple[Path, str, bool, str, str]]:
    """(mountpoint, label, removable_or_hotplug, transport, size) via lsblk."""
    if not shutil.which("lsblk"):
        return []
    try:
        out = subprocess.run(
            ["lsblk", "-J", "-o", "PATH,MOUNTPOINT,MOUNTPOINTS,RM,HOTPLUG,TRAN,SIZE,LABEL,TYPE"],
            capture_output=True, text=True, timeout=20,
        )
        data = json.loads(out.stdout or "{}")
    except (OSError, ValueError, subprocess.SubprocessError):
        return []

    found: List[Tuple[Path, str, bool, str, str]] = []

    def walk(nodes, inherited_tran=""):
        for n in nodes:
            tran = n.get("tran") or inherited_tran
            mps = n.get("mountpoints") or ([n["mountpoint"]] if n.get("mountpoint") else [])
            removable = bool(n.get("rm")) or bool(n.get("hotplug"))
            for mp in mps:
                if mp:
                    found.append((Path(mp), n.get("label") or Path(mp).name,
                                  removable, tran or "", n.get("size") or ""))
            walk(n.get("children") or [], tran)

    walk(data.get("blockdevices") or [])
    return found


def discover_sources(dest: Path, explicit: Sequence[str]) -> List[Source]:
    """Find candidate SD cards, never including the destination's own device."""
    if explicit:
        srcs = []
        for s in explicit:
            p = Path(s).resolve()
            if not p.is_dir():
                die(f"--source {s} is not a directory")
            srcs.append(Source(p, p.name, p.name))
        return srcs

    try:
        dest_dev = dest.stat().st_dev
    except OSError:
        dest_dev = -1  # destination not created yet; nothing to exclude
    candidates: List[Source] = []
    seen = set()

    for mount, label, removable, tran, size in _lsblk_mounts():
        if not mount.is_dir():
            continue
        try:
            if mount.stat().st_dev == dest_dev:
                continue  # same filesystem as the destination -- never a source
        except OSError:
            continue
        if not (removable or tran in {"usb", "mmc"}):
            continue
        if str(mount) in SYSTEM_MOUNTS or str(mount).startswith(("/boot/", "/snap/", "/var/", "/usr/", "/nix/")):
            continue
        if str(mount) in seen:
            continue
        seen.add(str(mount))
        candidates.append(Source(mount, mount.name, label, size))

    if not candidates:  # lsblk unavailable or unhelpful -- fall back to the usual mount roots
        user = os.environ.get("USER") or os.environ.get("LOGNAME") or ""
        roots = [Path(f"/run/media/{user}"), Path(f"/media/{user}")]
        for base in (Path("/run/media"), Path("/media")):
            if base.is_dir():
                roots.extend(d for d in sorted(base.iterdir()) if d.is_dir())
        for root in roots:
            if not root.is_dir():
                continue
            for child in sorted(root.iterdir()):
                if not child.is_dir():
                    continue
                try:
                    if child.stat().st_dev == dest_dev or str(child) in seen:
                        continue
                except OSError:
                    continue
                seen.add(str(child))
                candidates.append(Source(child, child.name, child.name))

    # Probe and de-duplicate AFTER the fallback, so fallback-discovered mounts
    # get the same treatment as lsblk-discovered ones.
    candidates = [c for c in candidates if looks_like_card(c.mount)]
    seen_labels: Dict[str, int] = {}
    for c in candidates:
        n = seen_labels.get(c.label, 0)
        seen_labels[c.label] = n + 1
        if n:  # two cards can mount under the same basename; keep names unique
            c.label = f"{c.label}_{n + 1}"
    return candidates


# --------------------------------------------------------------------------
# planning
# --------------------------------------------------------------------------


@dataclass
class Item:
    src: Path
    rel_dir: str          # destination sub-directory
    name: str             # destination file name (before codec suffix)
    size: int
    mtime: float
    is_wav: bool
    wav: Optional[WavInfo] = None
    source_label: str = ""
    sample_verify: bool = False   # read this one back when --verify sample


def scan_source(src: Source, keep_empty: bool = False,
                follow_symlinks: bool = False) -> Tuple[List[Item], List[Path]]:
    """Walk one card and decide where each file belongs on the destination.

    Returns (items, skipped_empty). A 0-byte WAV is the file the logger had just
    opened when power was cut, so there is normally exactly one per deployment
    and it never contains anything. Those are dropped by default -- pass
    ``keep_empty`` to copy them anyway.
    """
    items: List[Item] = []
    skipped_empty: List[Path] = []
    for dirpath, dirnames, filenames in os.walk(src.mount, followlinks=follow_symlinks):
        dirnames[:] = [d for d in sorted(dirnames)
                       if not d.startswith(".") and d not in {"System Volume Information", "$RECYCLE.BIN", "lost+found"}]
        for fn in sorted(filenames):
            if fn.startswith("."):
                continue
            p = Path(dirpath) / fn
            try:
                st = p.stat()
            except OSError:
                continue
            if not p.is_file():
                continue
            rel = p.relative_to(src.mount)
            rel_dir = str(rel.parent) if str(rel.parent) != "." else ""
            is_wav = p.suffix.lower() in WAV_SUFFIXES
            if is_wav and st.st_size == 0 and not keep_empty:
                skipped_empty.append(p)
                continue
            wav = read_wav_info(p) if is_wav else None
            items.append(Item(p, rel_dir, fn, st.st_size, st.st_mtime, is_wav, wav, src.label))
    return items, skipped_empty


# <site>-<grid>-<dev>-<timestamp>, e.g. site01-grid02-dev03-20260826T175746.
# The trailing .* lets a collision suffix (see assign_destinations) ride along.
SESSION_RE = re.compile(
    r"^(?P<site>[^-]+)-(?P<grid>[^-]+)-(?P<dev>[^-]+)-(?P<stamp>\d{8}T\d{4,6}.*)$"
)


def session_subpath(folder: str) -> str:
    """Where one deployment folder belongs under the destination.

    The field drive is filed site / grid / session, so everything recorded on
    one grid sits together and a site is one directory to copy or archive. A
    folder named to the convention is nested accordingly; its own name is kept
    intact rather than trimmed, so a session directory still says what it is
    when it is moved somewhere else on its own.

    Anything that does not match -- the older ``loggerNN-<timestamp>`` names,
    or a hand-made directory -- is left at the top level rather than guessed
    at, which keeps old cards and new cards working in the same run.
    """
    m = SESSION_RE.match(folder)
    if not m:
        return folder
    return os.path.join(m.group("site"), m.group("grid"), folder)


def assign_destinations(per_source: Dict[str, List[Item]], nest: bool = True) -> None:
    """Give every deployment folder a unique destination path.

    The old shell script rsync'd every card into one flat destination, so two
    cards holding a same-named folder silently overwrote each other -- a real
    risk here because a logger with a dead RTC names its folder from an epoch
    date (there is a ``...20000101T0000-1`` in the 2025 data already, and two
    such loggers would collide exactly).

    A *group* is one (card, top-level folder) pair, and it moves as a unit so
    that the ``-sensors.csv`` / ``-blinks.csv`` sidecars stay next to the WAVs
    they describe. Only groups that actually clash get renamed, so in the
    normal case the destination looks exactly like the cards did.
    """
    groups: Dict[Tuple[str, str], List[Item]] = {}
    for items in per_source.values():
        for it in items:
            top = it.rel_dir.split(os.sep)[0] if it.rel_dir else ""
            groups.setdefault((it.source_label, top), []).append(it)

    # Identify each group by the logger that wrote its WAVs (Teensy MAC), which
    # survives a wrong clock; fall back to the card it came from.
    group_tag: Dict[Tuple[str, str], str] = {}
    for key, items in groups.items():
        counts: Dict[str, int] = {}
        for it in items:
            if it.is_wav and it.wav:
                t = logger_tag(it.wav, it.name)
                counts[t] = counts.get(t, 0) + 1
        group_tag[key] = max(counts, key=counts.get) if counts else ""

    by_folder: Dict[str, List[Tuple[str, str]]] = {}
    for key in groups:
        by_folder.setdefault(key[1], []).append(key)

    for top, keys in by_folder.items():
        needs_suffix = len(keys) > 1 or top == ""
        if not needs_suffix:
            continue
        used: Dict[str, int] = {}
        for key in sorted(keys):
            card_label, _ = key
            card = _slug(card_label)
            tag = group_tag[key] or card
            if top:
                base = f"{top}__{tag}"
            else:
                # files loose at the card root: name the folder after the card,
                # and only add the logger tag when it says something new
                base = card if tag == card else f"{card}__{tag}"
            n = used.get(base, 0)
            used[base] = n + 1
            name = base if n == 0 else f"{base}_{n + 1}"
            for it in groups[key]:
                parts = it.rel_dir.split(os.sep) if it.rel_dir else []
                if parts:
                    parts[0] = name
                    it.rel_dir = os.sep.join(parts)
                else:
                    it.rel_dir = name

    # File the deployment folders site/grid/session. This runs last, over every
    # item rather than only the renamed ones, so a folder that needed a
    # collision suffix is still filed under the site and grid it belongs to.
    if not nest:
        return
    for items in per_source.values():
        for it in items:
            parts = it.rel_dir.split(os.sep) if it.rel_dir else []
            if not parts:
                continue
            nested = session_subpath(parts[0])
            if nested != parts[0]:
                it.rel_dir = os.sep.join([nested] + parts[1:])


def mark_verify_sample(per_source: Dict[str, List[Item]], percent: float) -> int:
    """Pick which files get read back when ``--verify sample`` is used.

    Full verification roughly doubles a copy: on four 500 GB cards it is the
    difference between about 5 h and about 12 h. Sampling keeps the half that
    is already free -- every file is hashed on its way off the card no matter
    what, so the manifest can prove any of them later -- and spends the
    expensive read-back where it is most likely to reveal a problem:

    * ``percent`` of each deployment's WAVs, evenly spaced from the first to
      the last, so a card or a destination that degrades part-way through
      shows up wherever it starts going wrong;
    * every non-WAV sidecar -- together ~0.007% of a deployment, so free.

    A share rather than a count, because deployment folders vary by three
    orders of magnitude: a 20 min test writes 4 files, a 3 day recording at
    5 min per file writes ~864. Never fewer than three, so even a short folder
    gets its first, middle and last checked.

    Returns how many files were marked.
    """
    groups: Dict[Tuple[str, str], List[Item]] = {}
    for items in per_source.values():
        for it in items:
            if it.is_wav:
                groups.setdefault((it.source_label, it.rel_dir), []).append(it)
            else:
                it.sample_verify = True
    for items in groups.values():
        items.sort(key=lambda i: i.name)
        n = len(items)
        k = min(max(3, math.ceil(n * percent / 100.0)), n)
        if k <= 0:
            continue
        picks = {0} if k == 1 else {round(i * (n - 1) / (k - 1)) for i in range(k)}
        for i in picks:
            items[i].sample_verify = True
    return sum(1 for items in per_source.values() for it in items if it.sample_verify)


def _slug(text: str) -> str:
    """Filesystem-safe short form of a card label/mountpoint name."""
    return re.sub(r"[^A-Za-z0-9._-]+", "_", text).strip("_") or "card"


# --------------------------------------------------------------------------
# manifest
# --------------------------------------------------------------------------


class Manifest:
    """Append-only JSONL record of every file written, with its source hash.

    This is what makes the transfer resumable and what ``verify`` / ``restore``
    check against. Treat it as part of the archive: without it you have files
    but no proof they match the cards.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self.by_dst: Dict[str, dict] = {}
        self._lock = threading.Lock()
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except ValueError:
                        continue
                    self.by_dst[rec["dst"]] = rec

    def already_done(self, dst_rel: str, size: int, mtime: float) -> bool:
        """Whether this exact source file has already been written completely.

        A record is only appended after the atomic rename, so its presence
        means the destination file is whole -- which is what makes a re-run
        resumable. It deliberately does *not* require ``verified``: under
        ``--verify sample`` most files are written but not read back, and those
        must not be copied a second time on the next run. Use ``is_verified``
        to ask the stronger question.
        """
        rec = self.by_dst.get(dst_rel)
        return bool(
            rec
            and rec.get("src_bytes") == size
            and abs(rec.get("src_mtime", -1) - mtime) < 2  # FAT32 has 2 s resolution
        )

    def is_verified(self, dst_rel: str) -> bool:
        """Whether the written file was read back and re-hashed successfully."""
        rec = self.by_dst.get(dst_rel)
        return bool(rec and rec.get("verified"))

    def unverified(self) -> List[str]:
        return sorted(k for k, r in self.by_dst.items() if not r.get("verified"))

    def append(self, rec: dict) -> None:
        with self._lock:
            self.by_dst[rec["dst"]] = rec
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, sort_keys=True) + "\n")


# --------------------------------------------------------------------------
# transfer
# --------------------------------------------------------------------------


class Stats:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.files = 0
        self.skipped = 0
        self.verified = 0
        self.src_bytes = 0
        self.out_bytes = 0
        self.errors: List[str] = []
        self.empty: List[str] = []
        self.out_of_space = False
        self.protect_failed = False
        self.t0 = time.time()

    def add(self, src_bytes: int, out_bytes: int) -> int:
        """Record one finished file; returns its 1-based index for the log line."""
        with self.lock:
            self.files += 1
            self.src_bytes += src_bytes
            self.out_bytes += out_bytes
            return self.files


def _sha256_stream(fh) -> Tuple[str, int]:
    h, n = hashlib.sha256(), 0
    for chunk in iter(lambda: fh.read(CHUNK), b""):
        h.update(chunk)
        n += len(chunk)
    return h.hexdigest(), n


def compress_to(src: Path, tmp: Path, codec: Codec, level: int, threads: int) -> Tuple[str, int]:
    """Stream ``src`` through the codec into ``tmp``; return (sha256, bytes read).

    The source is read exactly once: we hash each chunk on its way into the
    compressor's stdin. Reading the card twice would roughly double the slowest
    part of the whole job.
    """
    if codec.name == "none":
        h = hashlib.sha256()
        n = 0
        with open(src, "rb") as fi, open(tmp, "wb") as fo:
            for chunk in iter(lambda: fi.read(CHUNK), b""):
                h.update(chunk)
                n += len(chunk)
                fo.write(chunk)
        return h.hexdigest(), n

    errf = tmp.with_suffix(tmp.suffix + ".err")
    cmd = codec.compress_cmd(level, threads, tmp)
    if codec.stream:
        stdout_target = open(tmp, "wb")
        proc_out = stdout_target
    else:  # wavpack writes its own output file; it still accepts WAV on stdin
        cmd = cmd + ["-"]
        stdout_target = None
        proc_out = subprocess.DEVNULL

    h = hashlib.sha256()
    n = 0
    try:
        with open(errf, "wb") as fe:
            p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=proc_out, stderr=fe)
            try:
                with open(src, "rb") as fi:
                    for chunk in iter(lambda: fi.read(CHUNK), b""):
                        h.update(chunk)
                        n += len(chunk)
                        p.stdin.write(chunk)
            except BrokenPipeError:
                pass  # the codec bailed out; its stderr below says why
            finally:
                try:
                    p.stdin.close()
                except (OSError, ValueError):
                    pass
            rc = p.wait()
    finally:
        if stdout_target is not None:
            stdout_target.close()

    if rc != 0:
        msg = errf.read_text(errors="replace")[:300] if errf.exists() else ""
        errf.unlink(missing_ok=True)
        raise RuntimeError(f"{codec.name} exited {rc}: {msg.strip()}")
    errf.unlink(missing_ok=True)
    return h.hexdigest(), n


def verify_roundtrip(dst: Path, codec: Codec, expect_sha: str) -> bool:
    """Decompress what we just wrote and re-hash it against the source hash.

    This is the whole point of the exercise: it proves the bytes on the
    destination decode back to exactly what was on the card, so the card can be
    reformatted. A size check would not catch a silently corrupted sector.
    """
    if codec.name == "none":
        with open(dst, "rb") as f:
            return _sha256_stream(f)[0] == expect_sha
    p = subprocess.Popen(codec.decompress_cmd(dst), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
        got, _ = _sha256_stream(p.stdout)
    finally:
        p.stdout.close()
        p.wait()
    return p.returncode == 0 and got == expect_sha


def effective_codec(it: Item, codec: Codec) -> Codec:
    """Which codec actually gets used for this one file.

    Sidecar CSVs are ~0.007% of a deployment, so they are stored plain and stay
    directly readable. An audio codec additionally needs a WAV whose format
    wavpack can represent losslessly; anything else falls back to a
    general-purpose codec rather than being silently mangled.
    """
    if not it.is_wav:
        return CODECS["none"]
    if codec.stream:
        return codec
    if it.wav is None or it.wav.bits not in (8, 16, 24, 32) or not it.wav.channels:
        return CODECS["zstd"] if shutil.which("zstd") else CODECS["none"]
    return codec


def transfer_item(
    it: Item, dest: Path, codec: Codec, level: int, threads: int,
    manifest: Manifest, stats: Stats, *, verify: str, overwrite: bool, dry_run: bool,
    protect: bool = True,
) -> None:
    eff = effective_codec(it, codec)
    # a fallback codec gets its own default level, not the requested codec's
    eff_level = level if eff.name == codec.name else eff.default_level
    out_rel = os.path.join(it.rel_dir, it.name + eff.suffix) if it.rel_dir else it.name + eff.suffix
    out_path = dest / out_rel

    if manifest.already_done(out_rel, it.size, it.mtime) and out_path.exists():
        with stats.lock:
            stats.skipped += 1
        return
    if out_path.exists() and not overwrite and not manifest.already_done(out_rel, it.size, it.mtime):
        with stats.lock:
            stats.errors.append(f"{out_rel}: exists but is not a recorded copy of {it.src} (use --overwrite)")
        return
    if dry_run:
        with stats.lock:
            stats.skipped += 1
        return

    out_path.parent.mkdir(parents=True, exist_ok=True)
    if overwrite and out_path.exists():
        # a previous run may have write-protected it; os.replace needs the
        # directory, not the file, but be explicit rather than rely on that
        try:
            os.chmod(out_path, 0o644)
        except OSError:
            pass
    # wavpack silently appends ".wv" when -o does not already end in it, so the
    # temp name has to carry the codec suffix. The leading dot also keeps
    # partials out of any later scan of this directory.
    tmp = out_path.with_name("." + out_path.name + ".partial"
                             + ("" if eff.stream else eff.suffix))
    t0 = time.time()
    try:
        sha, nbytes = compress_to(it.src, tmp, eff, eff_level, threads)
        if nbytes != it.size:
            # A failing card can return a short read without raising. The hash
            # would then cover only what we got, so verification would happily
            # pass on a short copy -- catch it here instead.
            raise RuntimeError(f"read {nbytes} bytes but the card reported {it.size}; "
                               f"source file may be failing or changing")
        do_verify = verify == "full" or (verify == "sample" and it.sample_verify)
        if do_verify and not verify_roundtrip(tmp, eff, sha):
            raise RuntimeError("round-trip verification FAILED (decompressed bytes != source)")
        os.replace(tmp, out_path)
        os.utime(out_path, (it.mtime, it.mtime))
        if protect:
            # Field data cannot be re-recorded, so take the write bits off as
            # soon as the file is final. Only the *files*: leaving the
            # directories writable is what still lets an interrupted run
            # resume into them and lets 'verify' rewrite the manifest --
            # a recursive chmod would lock the archive against its own tools.
            try:
                os.chmod(out_path, 0o444)
            except OSError:
                with stats.lock:
                    stats.protect_failed = True
    except Exception as exc:  # noqa: BLE001 - one bad file must not kill the run
        tmp.unlink(missing_ok=True)
        with stats.lock:
            if isinstance(exc, OSError) and exc.errno == errno.ENOSPC:
                stats.out_of_space = True
            stats.errors.append(f"{it.src}: {exc}")
        log(f"  !! {it.src.name}: {exc}")
        return

    out_bytes = out_path.stat().st_size
    index = stats.add(nbytes, out_bytes)
    if do_verify:
        with stats.lock:
            stats.verified += 1
    if it.is_wav and it.size == 0:
        with stats.lock:
            stats.empty.append(out_rel)

    manifest.append({
        "dst": out_rel,
        "src": str(it.src),
        "src_card": it.source_label,
        "src_bytes": it.size,
        "src_mtime": it.mtime,
        "sha256": sha,
        "out_bytes": out_bytes,
        "codec": f"{eff.name}:{eff_level}" if eff.name != "none" else "none",
        "verified": do_verify,
        "wav": ({
            "channels": it.wav.channels, "rate": it.wav.rate, "bits": it.wav.bits,
            "duration_s": round(it.wav.duration_s, 3),
            "logger": logger_tag(it.wav, it.name), **it.wav.info,
        } if it.wav else None),
        "copied_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    })

    dt = max(time.time() - t0, 1e-6)
    with stats.lock:
        total_mb = stats.src_bytes / 2**20
        elapsed = time.time() - stats.t0
    tick = " OK" if (do_verify and verify == "sample") else ""
    log(f"  [{index}] {out_rel}  {human(it.size)} -> {human(out_bytes)} "
        f"({100 * out_bytes / max(it.size, 1):.0f}%)  {it.size / 2**20 / dt:.0f} MB/s"
        f"   [{total_mb / max(elapsed, 1e-6):.0f} MB/s avg]{tick}")


# --------------------------------------------------------------------------
# commands
# --------------------------------------------------------------------------


def summarise_plan(per_source: Dict[str, List[Item]]) -> Tuple[int, int]:
    total_files = total_bytes = 0
    for label, items in sorted(per_source.items()):
        wavs = [i for i in items if i.is_wav]
        other = len(items) - len(wavs)
        nbytes = sum(i.size for i in items)
        secs = sum(i.wav.duration_s for i in wavs if i.wav)
        loggers = sorted({logger_tag(i.wav, i.name) for i in wavs if i.wav})
        log(f"\n  {label}:")
        log(f"    {len(wavs)} wav + {other} other = {human(nbytes)}, {hms(secs)} of audio")
        if loggers:
            log(f"    logger(s): {', '.join(loggers)}")
        folders = sorted({(i.rel_dir or '<card root>') for i in items})
        log(f"    -> {', '.join(folders[:6])}{' ...' if len(folders) > 6 else ''}")
        total_files += len(items)
        total_bytes += nbytes
    return total_files, total_bytes


def cmd_copy(args: argparse.Namespace) -> int:
    dest = Path(args.dest).resolve()
    dest.mkdir(parents=True, exist_ok=True)
    log.open(dest)
    log(f"copydata  {datetime.now().isoformat(timespec='seconds')}")
    log(f"destination: {dest}")

    codec = CODECS[args.codec]
    level = args.level if args.level is not None else codec.default_level
    if level not in codec.levels:
        die(f"--level {level} is not valid for codec '{codec.name}' (allowed: {codec.levels})")
    require_codec(codec)

    sources = discover_sources(dest, args.source)
    if not sources:
        die("no SD cards found.\n"
            "       Nothing was copied. Check that the cards are mounted (lsblk), or\n"
            "       name them explicitly:  --source /path/to/card  (repeatable).")

    log(f"\nScanning {len(sources)} source(s) -- reading WAV headers, this takes a moment...")
    per_source: Dict[str, List[Item]] = {}
    empty_skipped: List[Path] = []
    for s in sources:
        items, skipped = scan_source(s, keep_empty=args.keep_empty)
        empty_skipped.extend(skipped)
        if not items:
            log(f"  {s.display}: empty, ignoring")
            continue
        per_source[s.display] = items
    if not per_source:
        die("the detected cards contain no files. Nothing was copied.")

    assign_destinations(per_source, nest=not args.flat)
    n_sample = (mark_verify_sample(per_source, args.sample_percent)
                if args.verify == "sample" else 0)
    total_files, total_bytes = summarise_plan(per_source)

    # measured on flona2025 logger WAVs (see utils/README_copydata.md);
    # rounded up so the space check never under-books the destination
    ratio_guess = {"none": 1.0, "gzip": 0.17, "zstd": 0.19 if level <= 12 else 0.12,
                   "xz": 0.10, "wavpack": 0.13 if level <= 3 else 0.12}[codec.name]
    need = int(total_bytes * ratio_guess)
    free = shutil.disk_usage(dest).free
    log(f"\n  TOTAL: {total_files} files, {human(total_bytes)}")
    if empty_skipped:
        log(f"  skipping {len(empty_skipped)} empty (0-byte) wav(s) -- the file the logger "
            f"had open\n           when power was cut. Pass --keep-empty to copy them.")
    log(f"  codec: {describe_codec(codec, level)}")
    if args.verify == "sample":
        log(f"  verify: spot check {n_sample} of {total_files} files "
            f"({100 * n_sample / max(total_files, 1):.1f}%) -- ~{args.sample_percent:g}% of "
            f"each deployment's wavs, evenly spaced, plus every sidecar")
    log(f"  estimated on destination: ~{human(need)}  (free: {human(free)})")
    if need > free * 0.97:
        die(f"not enough free space on {dest}: need ~{human(need)}, have {human(free)}. "
            f"Nothing was copied.")

    if not args.yes and not args.dry_run:
        try:
            resp = input(f"\nCopy to {dest}? [Y/n] ").strip().lower()
        except EOFError:
            resp = "n"
        if resp not in {"", "y", "yes"}:
            log("Aborted; nothing was copied.")
            return 0

    manifest = Manifest(dest / MANIFEST_NAME)
    stats = Stats()
    n_cards = len(per_source)
    threads = args.codec_threads if args.codec_threads > 0 else max(1, (os.cpu_count() or 4) // max(n_cards, 1))
    log(f"\nCopying: {n_cards} card(s) in parallel, {threads} codec thread(s) each, "
        f"verify={args.verify}\n")

    def worker(label: str, items: List[Item]) -> None:
        log(f"-> {label}: {len(items)} files")
        for it in items:
            transfer_item(it, dest, codec, level, threads, manifest, stats,
                          verify=args.verify, overwrite=args.overwrite, dry_run=args.dry_run,
                          protect=not args.no_protect)

    workers = [threading.Thread(target=worker, args=(k, v), daemon=True) for k, v in sorted(per_source.items())]
    for w in workers:
        w.start()
    for w in workers:
        w.join()

    elapsed = time.time() - stats.t0
    log("\n" + "=" * 72)
    log(f"copied   : {stats.files} files, {human(stats.src_bytes)} read -> {human(stats.out_bytes)} written")
    if stats.src_bytes:
        log(f"ratio    : {stats.out_bytes / stats.src_bytes:.3f} "
            f"({100 * (1 - stats.out_bytes / stats.src_bytes):.1f}% saved)")
    log(f"skipped  : {stats.skipped} (already verified, or --dry-run)")
    log(f"elapsed  : {hms(elapsed)}  ({stats.src_bytes / 2**20 / max(elapsed, 1e-6):.0f} MB/s from cards)")
    if stats.empty:
        log(f"\nempty wavs ({len(stats.empty)}) -- 0 bytes; normally the file the logger had")
        log("just opened when it was stopped. Copied anyway.")
        for e in stats.empty[:10]:
            log(f"  - {e}")
    if stats.protect_failed:
        log("\nNOTE: could not make the copied files read-only -- the destination "
            "filesystem\n      (exFAT/NTFS/vfat) does not carry unix permissions. "
            "The data is fine;\n      it just is not protected against being "
            "overwritten later.")
    if stats.out_of_space:
        log(f"\nTHE DESTINATION FILLED UP. {human(shutil.disk_usage(dest).free)} free on {dest}.")
        log("Free space or use a bigger drive, then re-run -- verified files are skipped.")
    if stats.errors:
        log(f"\nFAILED ({len(stats.errors)}):")
        for e in stats.errors[:40]:
            log(f"  - {e}")
        log("\nDO NOT reformat the cards. Re-run to retry the failed files.")
        return 1
    if args.dry_run:
        log("\nDry run -- nothing was written.")
        return 0
    if args.verify == "full":
        log("\nAll files verified: every one was read back, decoded and re-hashed against\n"
            "the hash taken while reading the card.")
        log("The cards can be reformatted once you are happy with the summary above.")
    elif args.verify == "sample":
        log(f"\nSpot check passed: {stats.verified} of {stats.files} files were read back "
            f"and re-hashed.")
        log("Every file's source hash is in the manifest, so any of them can still be\n"
            "proven -- but the rest are NOT yet confirmed on the destination.")
        log(f"Before reformatting any card, run:\n"
            f"  python3 {Path(sys.argv[0]).name} verify {dest}")
    else:
        log(f"\nNOTE: --verify {args.verify}; run "
            f"'python3 {Path(sys.argv[0]).name} verify {dest}' before reformatting any card.")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    dest = Path(args.dest).resolve()
    log.open(dest)
    man = Manifest(dest / MANIFEST_NAME)
    if not man.by_dst:
        die(f"no manifest at {dest / MANIFEST_NAME}")
    todo = sorted(man.by_dst.items())
    if args.only_unverified:
        todo = [(rel, rec) for rel, rec in todo if not rec.get("verified")]
        log(f"Verifying the {len(todo)} file(s) not already verified during the copy, "
            f"of {len(man.by_dst)} under {dest}\n")
    else:
        log(f"Verifying {len(todo)} files under {dest}\n")
    jobs = args.jobs if args.jobs > 0 else min(4, os.cpu_count() or 1)
    log(f"  {jobs} file(s) at a time\n")

    bad: List[str] = []
    missing: List[str] = []
    checked: List[dict] = []
    ok = 0
    lock = threading.Lock()
    t0 = time.time()

    def check(entry: Tuple[str, dict]) -> None:
        nonlocal ok
        rel, rec = entry
        path = dest / rel
        if not path.exists():
            with lock:
                missing.append(rel)
            return
        cname = rec.get("codec", "none").split(":")[0]
        codec = CODECS.get(cname, CODECS["none"])
        good = verify_roundtrip(path, codec, rec["sha256"])
        with lock:
            # record what we actually found, both ways: a file that fails here
            # must lose any earlier "verified" claim, or --only-unverified would
            # skip a file we already know is bad
            rec["verified"] = good
            rec["checked_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            checked.append(rec)
            if good:
                ok += 1
            else:
                bad.append(rel)
                log(f"  !! {rel}: CONTENT MISMATCH")

    with ThreadPoolExecutor(max_workers=jobs) as ex:
        list(ex.map(check, todo))

    # write the outcomes back so a later run neither redoes proven files nor
    # trusts a file that just failed
    if not args.no_record:
        for rec in checked:
            man.append(rec)

    log(f"\nok: {ok}   bad: {len(bad)}   missing: {len(missing)}   ({hms(time.time() - t0)})")
    for rel in missing[:40]:
        log(f"  missing: {rel}")
    return 1 if (bad or missing) else 0


def cmd_restore(args: argparse.Namespace) -> int:
    src = Path(args.dest).resolve()
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    log.open(out)
    man = Manifest(src / MANIFEST_NAME)
    if not man.by_dst:
        die(f"no manifest at {src / MANIFEST_NAME}")
    todo = [(rel, rec) for rel, rec in sorted(man.by_dst.items())
            if not args.only or args.only in rel]
    log(f"Restoring {len(todo)} files from {src} -> {out}\n")
    ok = skipped = 0
    errs: List[str] = []
    for rel, rec in todo:
        p = src / rel
        cname = rec.get("codec", "none").split(":")[0]
        codec = CODECS.get(cname, CODECS["none"])
        target = out / (rel[: -len(codec.suffix)] if codec.suffix and rel.endswith(codec.suffix) else rel)
        if target.exists() and not args.overwrite:
            log(f"  skip (exists): {target}")
            skipped += 1
            continue
        if not p.exists():
            # the archive is missing a file the manifest lists -- report it and
            # keep going, because the other 40000 files are still restorable
            log(f"  !! {rel}: not in the archive")
            errs.append(rel)
            continue
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                # a previous restore may have left it read-only
                try:
                    os.chmod(target, 0o644)
                except OSError:
                    pass
            if codec.name == "none":
                shutil.copy2(p, target)
            elif codec.name == "wavpack":
                subprocess.run(codec.decompress_cmd(p, target), check=False,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                with open(target, "wb") as fo:
                    subprocess.run(codec.decompress_cmd(p), check=False, stdout=fo, stderr=subprocess.DEVNULL)
            # what we restore is a working copy, not the archive: copy2 would
            # otherwise carry the archive's read-only mode over and make the
            # unpacked wavs awkward to work with
            try:
                os.chmod(target, 0o644)
            except OSError:
                pass
            with open(target, "rb") as f:
                got, _ = _sha256_stream(f)
        except Exception as exc:  # noqa: BLE001 - one bad file must not end the run
            log(f"  !! {rel}: {exc}")
            errs.append(rel)
            continue
        if got != rec["sha256"]:
            log(f"  !! {rel}: restored file does not match manifest hash")
            errs.append(rel)
        else:
            ok += 1
            log(f"  ok  {target.relative_to(out)}  ({human(target.stat().st_size)})")
    log(f"\n{ok}/{len(todo)} restored and hash-checked."
        + (f"  skipped (already there): {skipped}" if skipped else "")
        + (f"  FAILED: {len(errs)}" if errs else ""))
    for rel in errs[:40]:
        log(f"  - {rel}")
    return 1 if errs else 0


def cmd_list(args: argparse.Namespace) -> int:
    dest = Path(args.dest).resolve() if args.dest else Path.cwd()
    sources = discover_sources(dest, args.source)
    if not sources:
        log("No SD cards detected.")
        return 1
    per_source = {}
    for s in sources:
        items, _ = scan_source(s)
        if items:
            per_source[s.display] = items
    if not per_source:
        log("Detected media, but none of it holds any files.")
        return 1
    assign_destinations(per_source, nest=not args.flat)
    n, b = summarise_plan(per_source)
    log(f"\n  TOTAL: {n} files, {human(b)}")
    return 0


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="copydata.py",
        description="Copy, organise, compress and verify logger SD cards.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "codec cheat-sheet -- measured on flona2025 16ch/48kHz logger WAVs.\n"
            "'saved' is the mean over a busy grid, a half-dead-channel grid and a\n"
            "quiet line recording; 'MB/s/core' is compression throughput per CPU core:\n"
            "\n"
            "  --codec wavpack          88.6% saved    ~90 MB/s/core   default; output stays an audio file\n"
            "  --codec zstd --level 3   84.7% saved   ~250 MB/s/core   when the cards are unusually fast\n"
            "  --codec gzip             86.6% saved    ~27 MB/s/core   worse than wavpack on BOTH axes\n"
            "  --codec zstd --level 19  90.4% saved     ~1 MB/s/core   archival\n"
            "  --codec xz               91.5% saved     ~1 MB/s/core   archival, smallest\n"
            "\n"
            "In the field the SD cards are the bottleneck, so wavpack is effectively\n"
            "free. The xz / zstd-19 tier costs ~100x the CPU for another ~3 points --\n"
            "do that at the lab: 'restore' to .wav, then 'copy --codec xz'.\n"
            "\n"
            "examples:\n"
            "  copydata.py list\n"
            "  copydata.py copy /run/media/me/FIELD_HDD/flona2025\n"
            "  copydata.py copy DEST --source /run/media/me/CARD1\n"
            "  copydata.py verify DEST\n"
            "  copydata.py restore DEST ./unpacked\n"
        ),
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_flat_opt(sp):
        sp.add_argument("--flat", action="store_true",
                        help="do not file deployments under site/grid; put each folder at "
                             "the top level of the destination, as before the "
                             "<site>-<grid>-<dev>-<timestamp> convention")

    def add_source_opts(sp):
        sp.add_argument("--source", action="append", default=[], metavar="DIR",
                        help="explicit source directory (repeatable); disables auto-detection")

    c = sub.add_parser("copy", help="copy + compress + verify (the main command)")
    c.add_argument("dest", help="destination directory on the field hard drive")
    add_source_opts(c)
    add_flat_opt(c)
    c.add_argument("--codec", choices=sorted(CODECS), default="wavpack",
                   help="compressor for WAVs (default: wavpack -- best ratio per CPU second "
                        "on this data, and the output stays a real audio file). 'none' = plain copy")
    c.add_argument("--level", type=int, default=None,
                   help="codec level; default is the codec's own (wavpack 1, zstd 12, xz 6)")
    c.add_argument("--verify", choices=("full", "sample", "none"), default="sample",
                   help="'sample' (default) reads back a spread of each deployment (see "
                        "--sample-percent) plus every sidecar; 'full' "
                        "reads back every file, which roughly doubles the run; 'none' reads "
                        "back nothing. Every file is hashed while being read either way, so "
                        "'verify --only-unverified' proves the rest later without needing "
                        "the cards -- do that before reformatting one")
    c.add_argument("--sample-percent", type=float, default=5.0, metavar="P",
                   help="with --verify sample: what share of each deployment folder's wavs "
                        "to read back, evenly spaced first..last (default: 5). Never fewer "
                        "than 3 per folder, so short folders still get first/middle/last")
    c.add_argument("--codec-threads", type=int, default=0, metavar="N",
                   help="threads per compressor; 0 = auto (cores / number of cards)")
    c.add_argument("--overwrite", action="store_true",
                   help="replace destination files that are not verified copies")
    c.add_argument("--keep-empty", action="store_true",
                   help="copy 0-byte WAVs too; by default they are skipped (they are the "
                        "file the logger had open when power was cut)")
    c.add_argument("--no-protect", action="store_true",
                   help="leave the copied files writable; by default each one is set to "
                        "read-only (0444) the moment it is complete, so a stray write "
                        "cannot silently corrupt data that cannot be recorded again, and "
                        "an interactive 'rm' stops to ask. It is a guard against accidents, "
                        "not against 'rm -rf'. Directories stay writable, so resuming, "
                        "'verify' and further copies into the same archive still work")
    c.add_argument("--dry-run", action="store_true", help="scan and plan, write nothing")
    c.add_argument("-y", "--yes", action="store_true", help="do not ask for confirmation")
    c.set_defaults(func=cmd_copy)

    v = sub.add_parser("verify", help="re-check a destination against its manifest")
    v.add_argument("dest")
    v.add_argument("--jobs", type=int, default=0, metavar="N",
                   help="files to check at a time; 0 = auto (min(4, cores))")
    v.add_argument("--only-unverified", action="store_true",
                   help="skip files already verified during the copy -- the natural "
                        "follow-up to 'copy --verify sample'")
    v.add_argument("--no-record", action="store_true",
                   help="do not write the results back into the manifest")
    v.set_defaults(func=cmd_verify)

    r = sub.add_parser("restore", help="decompress an archive back to plain .wav")
    r.add_argument("dest", help="the copied archive directory")
    r.add_argument("out", help="where to write the .wav files")
    r.add_argument("--only", default="", help="only restore paths containing this substring")
    r.add_argument("--overwrite", action="store_true")
    r.set_defaults(func=cmd_restore)

    ls = sub.add_parser("list", help="show what is on the cards and where it would go")
    ls.add_argument("dest", nargs="?", default=None, help="destination (to exclude it from sources)")
    add_source_opts(ls)
    add_flat_opt(ls)
    ls.set_defaults(func=cmd_list)
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        log("\nInterrupted. Partial files were discarded; re-run to resume.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
