# `copydata.py`

Copies logger SD cards onto the field drive: compress, sort, verify. An
alternative to `copydata.sh` for card sets big enough that you want the copy to
prove itself. Standard library only — no `pip install` on a field laptop. Needs
`wavpack`/`wvunpack`; `zstd` as fallback, `--codec none` needs nothing.

New to it: start with the [tutorial](TUTORIAL_copydata.md).

## Use

```
python3 utils/copydata.py list                                    # what is on the cards
python3 utils/copydata.py copy /media/me/HDD/iriri26
python3 utils/copydata.py verify /media/me/HDD/iriri26 --only-unverified --jobs 4
python3 utils/copydata.py restore DEST ./unpacked                 # back to plain .wav
```

`copy` is resumable: re-running skips every file the manifest records as fully
written, so an interruption costs you only the file it died on.

## Verification

Every file is sha256'd while it streams off the card. That hash is free — it is
the same read — and it goes into `copy_manifest.jsonl` on the drive. Reading
files *back* is what costs time:

| `--verify` | reads back | 4 x 500 GB |
|---|---|---|
| `sample` (default) | 5% of each deployment, every sidecar, every truncated wav | ~6.3 h |
| `full` | everything | ~12 h |
| `none` | nothing | ~6 h |

`sample` does not give up proof, it defers it. `verify` checks the drive against
the stored hashes and does not need the cards, so run it once they are out of
the reader — but before reformatting anything.

`--sample-percent P` (default 5) is a share and not a count because folders
differ by three orders of magnitude: a 20 min test is 4 files, a 3 day recording
at 5 min per file is ~864. At the default that 3 day folder gets 44 probes, one
per ~1.7 h of recording.

## Codec

`wavpack -f` is the default. Measured on three flona2025 WAVs (16 ch, 48 kHz,
16-bit, 461 MB) spanning a busy night grid, a grid with 8 dead channels, and a
quiet line recording:

| codec | saved | compress MB/s/core | decompress |
|---|---|---|---|
| `zstd -3` | 84.7 % | ~258 | ~700 |
| `gzip -6` | 86.6 % | ~27 | ~660 |
| **`wavpack -f`** | **88.6 %** | **~93** | ~88 |
| `wavpack -h -x4` | 89.2 % | ~3.5 | ~90 |
| `xz -6` | 91.5 % | ~0.9 | ~143 |

`gzip` is beaten on both axes. These are not general-purpose bytes — the
recordings use only 3-11 of their 16 bits, so per-channel prediction plus Rice
coding fits them better than an LZ matcher. `wavpack -f` also beats wavpack's
own default level here. FLAC is not an option at all: the format caps at 8
channels. `xz` is the smallest but runs at ~1 MB/s/core, slower than the cards
themselves — use it at the lab (`restore`, then `copy --codec xz`).

In the field the cards are the bottleneck, so the compression is free.

## What ends up on the drive

Sessions are named `<site>-<grid>-<dev>-<timestamp>` and are filed to match:

```
DEST/
├── copy_manifest.jsonl        # per file: source, sha256, codec, WAV metadata
├── copy_logs/
├── site01/grid01/site01-grid01-dev01-20260826T175746/
│   ├── site01-grid01-dev01-20260826T175746.wav.wv
│   └── site01-grid01-dev01-20260826T175746-sensors.csv   # sidecars stay plain
├── site02/grid01/site02-grid01-dev01-20260827T090000__mac1b9999/   # only on a real collision
└── logger24A-20260826T1757/   # name does not parse: left at the top level
```

A folder whose name does not match the convention is left at the top level
rather than filed under a guessed site, so old and new cards can be copied in
one run. `--flat` turns the nesting off.

The manifest is part of the archive. Without it you have files but no proof they
match the cards, and `verify` and `restore` have nothing to check against.

## Worth knowing

* **Never writes to a card, never deletes anything.** Ejecting and reformatting
  stay manual, on purpose.
* **Copied files are read-only (`0444`).** Files only, not directories, so
  resume and `verify` still work. `--no-protect` disables it. Does nothing on
  exFAT/NTFS — the summary says so rather than pretending.
* **The custom `LIST`/`INFO` chunk survives.** `wvunpack` reconstructs a
  byte-identical `.wav`, `DTIM` included. It can also be read without decoding:
  wavpack keeps the original RIFF header in the first 8 KB of the `.wv`.
* **Truncated WAVs fall back to `zstd`.** WavPack `-i` *corrects* the declared
  length, so the file would no longer be the file that was on the card.
  Reported in the summary.
* **0-byte WAVs are skipped** (`--keep-empty` to copy them). A scan of 23,699
  flona2025 WAVs found 61, always the last file of a deployment.
* **`verify --jobs N`** checks N files at a time (default `min(4, cores)`) and
  writes each outcome back, so a file that fails loses any earlier "verified"
  claim.
* **`--codec-threads`** defaults to `cores / cards`, which keeps each card
  streaming sequentially — the right pattern for SD cards and a spinning drive.
