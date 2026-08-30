# Getting a stack of SD cards onto the field drive

Walkthrough of `copydata.py`. Reference material — codec table, archive layout,
all options — is in [`README_copydata.md`](README_copydata.md).

Three things in one pass: **copy** each card into its own deployment folder
filed by site and grid, **shrink** every WAV to about an eighth without losing a
sample, and **check** the copy so you can reformat the card without crossing
your fingers.

Plug in the cards and the destination drive. Nothing else to prepare — the tool
finds the cards itself and never writes to one. You need `python3` and
`wavpack`; if something is missing it says so.

## 1. Look

```
python3 utils/copydata.py list
```

Reads the WAV headers, shows what it found and where each thing would go.
Writes nothing. Worth doing once to spot a card that did not mount, or a logger
that recorded far less than expected.

## 2. Copy

```
python3 utils/copydata.py copy /media/you/FIELD_HDD/iriri26
```

Prints a plan, asks once, then works. Cards are read in parallel, one file at a
time each.

```
  TOTAL: 7 files, 23.4 MB
  skipping 1 empty (0-byte) wav(s) -- the file the logger had open
  codec: wavpack -f
  verify: spot check 5 of 7 files (71.4%)
  estimated on destination: ~3.0 MB  (free: 28.8 GB)
```

Then walk away. Expect roughly card speed; compression is not the bottleneck.

## 3. Read the last lines

```
copied   : 7 files, 23.4 MB read -> 3.0 MB written
ratio    : 0.126 (87.4% saved)

Spot check passed: 5 of 7 files were read back and re-hashed.
Every file's source hash is in the manifest, so any of them can still be
proven -- but the rest are NOT yet confirmed on the destination.
```

Read that literally, both ways. For the checked files the drive holds exactly
what the card held. The rest are written and hashed, but not yet read back —
that is step 4.

If you see `FAILED (n)`: **do not reformat the cards.** Run the same command
again; finished files are skipped and only the broken ones retried.

## 4. Prove the rest

The spot check is sized to catch a card or drive going bad — 5% of each
deployment, evenly spread. It is not proof of every file. That is one more
command:

```
python3 utils/copydata.py verify /media/you/FIELD_HDD/iriri26 \
    --only-unverified --jobs 4
```

It reads the destination, not the cards, so **unplug them first** and run it
over supper. Expect roughly half the time the copy took. You want
`bad: 0   missing: 0`. Anything else and the cards are still the only good copy.

## 5. Only now, reformat

Ejecting and reformatting are left to you. The tool never deletes anything.

## Getting `.wav` files back

```
python3 utils/copydata.py restore DEST ./unpacked --only site01/grid01
```

`--only` matters: one deployment is ~270 GB unpacked. Each restored file is
checked against its stored checksum on the way out.

Often you do not need this. `wvunpack` seeks, so a reader can pull a window
straight out of a `.wv`: a 10 s window costs 0.19 s whether it starts at 0 s or
4 min in, and a full 300 s file decodes in 5.9 s (~50x realtime).

```
wvunpack -q -y --skip=00:02:00 --until=+00:00:10 -o - FILE.wav.wv
```

Note the header of a *partial* decode is synthetic and carries no `LIST`/`INFO`
metadata. That metadata is not lost — wavpack keeps the original RIFF header in
the first 8 KB of the `.wv`, and `copy_manifest.jsonl` has the same fields
already parsed.

## The commands

| | |
|---|---|
| `list` | what is on the cards, where it would go |
| `copy DEST` | copy, compress, spot-check |
| `verify DEST` | prove the drive against the manifest, cards not needed |
| `restore DEST OUT` | back to plain `.wav` |

## Worth knowing

* The drive is filed by site and grid: `DEST/site01/grid01/<session>/`.
* Copied files are read-only. Resume and `verify` still work; `--no-protect`
  turns it off.
* Re-running `copy` is safe and resumes.
* In a hurry: `--verify none` skips the spot check, `--verify full` reads
  everything back and roughly doubles the run.
