# Drive Recovery for Windows

A small Python desktop tool for inspecting old-drive images and carving file
candidates. No third-party Python packages are required. This is an initial
signature-based recovery tool, not a replacement for Recuva's filesystem analysis.

## Start on Windows

1. Install Python 3.10 or newer from https://www.python.org/downloads/windows/.
   Include Tcl/Tk and the Python launcher (normally included).
2. Copy `recovery.py`, `recovery_gui.py`, and `Start Recovery.bat` into a folder
   on your healthy working drive. Do not install onto the drive being recovered.
3. Double-click `Start Recovery.bat`, or run `py -3 recovery_gui.py`.
4. Browse to an image of the old drive and click **Scan only**.
5. To copy candidates, select a folder on a different healthy drive. The tool
   creates a new `RecoveredFiles` subfolder; choose a new name if it already exists.
   Click **Scan and recover copies**. Open copies to check their contents.

If Windows asks to initialize or format an old drive, cancel. Do not run repairs
or CHKDSK on the original before imaging it. Do not save recovered files or images
onto the physical drive being examined. A write blocker provides stronger source
protection than software read-only access alone.

## Make an image first

Use a trusted disk-imaging tool such as FTK Imager to create a **raw/dd** image
on another healthy physical drive with enough free space for the entire old drive.
Select the correct source physical disk by model, capacity, and serial number.
Scan the resulting `.img`, `.dd`, or raw image file with this program. E01, VHD,
compressed images, and split images are not supported; export a single raw image.

If a drive clicks, repeatedly disconnects, or produces read errors, stop ordinary
scanning. This program has no bad-sector retry map or failing-drive imaging
capability. Use a specialist imaging workflow or recovery service for valuable data.

## Command line

```powershell
py -3 recovery.py E:\Images\old-drive.img
py -3 recovery.py E:\Images\old-drive.img --recover F:\RecoveredFiles
py -3 recovery.py E:\Images\old-drive.img --types jpg png --max-file-mib 256
py -3 recovery.py E:\Images\old-drive.img --start 1048576 --length 1073741824
```

Output is JSON Lines: each candidate includes its byte offset, format, estimated
length, and status. The final summary reports whether the candidate limit was hit.
The defaults cap each candidate at 64 MiB and a scan at 10,000 candidates; increase
`--max-file-mib` or `--max-candidates` if appropriate. Scans can take hours.
Redirect scan output to a report on a healthy drive if desired:

```powershell
py -3 recovery.py E:\Images\old-drive.img > F:\scan-report.jsonl
```

Advanced users can enter a Windows device path such as `\\.\PhysicalDrive2`
for scan-only access, generally from an elevated terminal. Verify the disk number
with Windows Disk Management first. Direct-device scanning is experimental and
has not been validated on Windows hardware; image scanning is the tested workflow.
Direct-device recovery is intentionally blocked: create an image first.
Linux block-device paths also support scan-only access when permissions allow.

## What results mean

- Detects JPEG, PNG, PDF, and ZIP signatures. Modern Office documents are ZIP
  containers and will initially be saved with `.zip` extensions. Inspect the
  container to identify the actual format; archives are never automatically extracted.
- Finds signatures throughout the image, including allocated/live files, deleted
  files, embedded thumbnails, and random false positives. It cannot say a file
  was deleted or distinguish live from lost data.
- Looks for bounded end markers. `end-marker-found` is a heuristic, not proof of
  a complete, valid file. JPEG embedded thumbnails and PDF incremental saves can
  produce shortened candidates. ZIP central-directory readability is reported
  for recovered archives, without decompressing or verifying every member.
- Does not reconstruct NTFS/FAT/exFAT directory trees, filenames, timestamps, or
  fragmented files. Encrypted volumes must be unlocked and imaged appropriately.
  Overwritten data and SSD data discarded by TRIM generally cannot be recovered.
- A no-results scan does not prove the drive contains nothing recoverable.
  Use a filesystem-aware tool such as Recuva or TestDisk as a further check.
- Output filenames use source offsets. Existing output directories are rejected.
  Copies use `.partial` while being written; a forced stop can leave partial
  files, which must not be treated as completed recovery.

## Validation

```powershell
py -3 -m unittest -v test_recovery.py
```

Tests exercise scan-only behavior, copying candidates byte-for-byte, unchanged
source images, signatures crossing read boundaries, bounds, existing-output
protection, and aligned reads. Windows device access and the native desktop UI
require validation on a Windows machine.
