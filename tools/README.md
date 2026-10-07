# Android upload simulator

Run from the parent repository with Python 3 (standard library only):

```bash
python3 tools/simulate_android_upload.py
```

The default API is the new clone; other API bases are rejected for safety.
The default input is the real `test_files/000` recording in backend Git history
(`b19efb0`), loaded without writing fixture bytes into the checkout. That Git
history must be available locally. It decoded successfully with the unchanged
`read_shimmer_dat()` implementation: 30,240 timestamp samples. No fake sensor
data is generated. A unique Android-style filename is generated for each run.

Optional arguments: `--file /path/to/real/recording`, `--filename <upload-basename>`,
and `--api-base https://wwr1eh4vg9.execute-api.us-east-2.amazonaws.com`.
The protocol matches Android: JSON filename array → presigned upload URL → raw
`text/plain` S3 PUT → JSON `full_file_name` decode request → missing-files recheck.
Additional read-only checks confirm dashboard metadata, decoded JSON, and a
byte-for-byte raw download. All stages must pass; failures exit nonzero with
status/body detail. Redirects and signed URLs outside the new bucket are rejected.
Presigned credentials are not printed. An existing filename aborts before upload.
No AWS credentials, extra Python dependencies, login, or device connection are
needed. HTTP timeout is 45 seconds to allow cloud decode; this does not change
Android's timeouts or retry behavior.

## Verified run: 2026-10-06

```bash
python3 tools/simulate_android_upload.py --filename SIM_ANDROID_20261006_RUN1__20261006_180000__SIMULATOR__Shimmer_SIM-001__000.txt
```

All eight stages passed with HTTP 200. Fixture: 998,176 bytes,
SHA-256 `bdbe73b87729e55dea7b3f05aaf6c0d91e385dbc56a9de307cd8ea54910d1695`.
Independent read-only AWS CLI checks, after verifying account `837873138796`
with profile `shimmer-admin` in `us-east-2`, confirmed:

- Bucket `shimmer-server-clone-databucket-wn9atsyogh42`: raw object 998,176 bytes,
  `text/plain`; decoded object 10,549,123 bytes, `application/json`.
- Decoded key: `decode/SIM_ANDROID_20261006_RUN1__20261006_180000__SIMULATOR__Shimmer_SIM-001__000_decoded.json`.
- Table `shimmer-server-clone-FileMetadataTable-1FARD0NWRCNXP`: consistent-read
  metadata row keyed by the uploaded filename, with matching decode pointer and
  recording start/end timestamps.
- `/files/combined-meta/`, the dashboard's decoded metadata endpoint, contains
  this recording. Decoded JSON contains 30,240 `timestampCal` samples.
- Reusing this filename exits 1 before PUT. Local checks also passed for unsafe
  URL rejection, metadata lookup, HTTP failure detail, and signature redaction.

In https://clone.djm6m1z6lh719.amplifyapp.com search for device
`SIM_ANDROID_20261006_RUN1`, filename/date `2026-10-06`, shimmer `Shimmer_SIM`,
patient `none` (no mapping was created). The real fixture's recording range is
`2010-10-02T22:43:51.951752+00:00` to `2010-10-02T22:53:50.596345+00:00`;
its embedded timestamps differ from the synthetic test filename's date.
Authenticated UI verification remains manual; no browser/login test was run.

Test objects and metadata are intentionally retained in the new backend for
inspection and incur normal storage/request charges. Repeated runs add records;
the simulator neither cleans up data nor invokes aggregation. No application
behavior or infrastructure was changed. Fixture bytes/uploads/caches are not
committed.
