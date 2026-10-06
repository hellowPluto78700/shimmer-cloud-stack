# Shimmer cloud operation guide

## 1. Quick reference

Frontend: https://clone.djm6m1z6lh719.amplifyapp.com

Backend: https://wwr1eh4vg9.execute-api.us-east-2.amazonaws.com

Normally use the frontend to sign in, inspect recordings, manage mappings, chart data, and download files. The backend URL is for the Android app, simulator, and administrator/API troubleshooting. It is not the dashboard website.

This guide follows current source and validation evidence as of 2026-10-06. For how the system works, contracts, security, and evidence details, see [System Architecture](SYSTEM_ARCHITECTURE.md). All examples below use synthetic identifiers. Commands that upload, register, decode, or aggregate write to the deployed clone; they are instructions, not checks performed during this documentation task.

## 2. Create a frontend account

1. Open the frontend URL and go to `/login` if necessary.
2. Select **Create Account** (the Sign Up flow).
3. Enter a username, email, password, and password confirmation as prompted. Current password minimum is eight characters.
4. Receive the email verification code at the supplied address.
5. Enter the code to verify the account.
6. Select **Sign In** and enter your username/password.

This creates a Cognito frontend user. **A frontend Cognito user is NOT the same thing as registering a phone/device.** Create the device/patient mapping separately below. Source supports this workflow; available validation confirms the forms and authentication configuration, but actual email delivery and successful signup/login still require user acceptance testing.

## 3. Register a phone/device

Register the identifier actually carried by recording filenames. Android normally uses `Settings.Secure.ANDROID_ID`; the app displays **Device ID** in its startup toast. It is the first component before `__` in the saved/uploaded filename, not your Cognito username, patient label, or sensor Bluetooth MAC.

On the frontend, open **User Operations** (`/user-ops`), choose **Add Mapping**, enter **Device** and **Patient**, add the left/right Shimmer identifiers, and click **Save**. If the phone has already uploaded, it may appear under **Unregistered Devices**; choose its **Add** button. Refresh the mapping grid to verify the row. Use **Update mapping** on an existing row to change assignments.

Android also has a person-icon Map button. With internet access, it reads the current mapping; if absent it offers **Patient**, **Shimmer 1**, **Shimmer 2**, and **Save**. Existing mappings are displayed read-only. Check the identifier shown in the dialog: this dialog first extracts a MAC from docking/status text and only falls back to `ANDROID_ID`. If it selected a sensor MAC, use the frontend/API to register the phone ID from the filename instead. The dialog's success message alone does not prove the upload identifier was registered.

API equivalent (run in a Bash shell with curl installed):

```bash
API_BASE='https://wwr1eh4vg9.execute-api.us-east-2.amazonaws.com'
DEVICE='LABPHONE001' # replace with the identifier before __ in the recording name
curl --fail-with-body -sS -X PUT "$API_BASE/ddb/device-patient-map/$DEVICE" \
  -H 'Content-Type: application/json' \
  --data '{"patient":"LAB_SUBJECT_001","shimmer1":["Shimmer_L001"],"shimmer2":["Shimmer_R001"]}'
curl --fail-with-body -sS "$API_BASE/ddb/device-patient-map/$DEVICE"
```

Use URL encoding for identifiers containing path-special characters. GET should return the same `device`, patient and Shimmer lists plus `updatedAt`; 404 means there is no mapping for that exact identifier. PUT replaces the item: include both side lists when preserving an existing assignment.

## 4. Assign a patient / Shimmer devices

Associate the phone/device with the lab's patient label. **Shimmer 1 / Left Hand Device** means left; **Shimmer 2 / Right Shimmers** means right in the current UI. Frontend lists support multiple permissible sensors per side: enter each identifier, click **Add**, then **Save** the mapping.

Use the identifier parsed from the recording name. For example, the filename component `Shimmer_L001-001` maps to `Shimmer_L001`; the final `-001` suffix is separated by the backend. Copy the exact parsed spelling/case from metadata when uncertain.

Without a mapping, a recording can still upload/decode, but patient normally shows `none`. Unmatched sensors can fall into the left (`shimmer1`) slot by default. Verify assignment before interpreting a left/right chart. Correct the mapping, then reload the data views.

## 5. Normal Android upload workflow

Record using the lab's Shimmer procedure, then use the Android docking/file-transfer flow to collect the recording. The app saves a local file and tracks it as unsynced. Automatic/background sync or **Sync to Cloud** checks missing files, uploads raw bytes, requests cloud decode, and then makes metadata available to the website. You do not manually open backend URLs for normal phone operation.

Keep internet available during synchronization. The foreground sync notification reports file progress and completion; manual sync also shows file status. Refresh **Shimmer Data** on the website after sync. Confirm the recording window and chart, not just the phone's completion message: current Android code can mark a successful raw upload synced even if decode subsequently fails. An existing raw object also stops it being considered missing.

Physical Bluetooth/phone behavior remains to be validated on real equipment; the cloud HTTP workflow has passed simulation.

## 6. Upload without Android

From the repository root, use Python 3; no extra packages or AWS credentials are needed:

```bash
python3 tools/simulate_android_upload.py
```

The default generates a unique filename and loads a real recording from backend history (`b19efb0:test_files/000`) if it is absent from the checkout. That history must be available. To set a synthetic name:

```bash
python3 tools/simulate_android_upload.py \
  --filename LABPHONE001__20261006_120000__TEST__Shimmer_L001-001__000.txt
```

To supply your own real raw recording and explicitly select the API:

```bash
python3 tools/simulate_android_upload.py \
  --api-base https://wwr1eh4vg9.execute-api.us-east-2.amazonaws.com \
  --file /path/to/real/shimmer-recording \
  --filename LABPHONE001__20261006_120001__TEST__Shimmer_L001-001__000.txt
```

Choose a fresh name each time. `--api-base` accepts only this clone; it is not a switch to arbitrary servers. `--help` lists the supported options.

The simulator runs missing-files → upload-URL request → raw S3 PUT → decode-and-store → missing-files recheck → dashboard metadata verification → decoded JSON download → byte-for-byte raw download comparison. All eight stages must pass; errors exit nonzero. It rejects existing names before upload and does not print signed credentials.

It validates the HTTP/storage/decode/read path with real bytes, without an Android identity or frontend login. It does not validate Bluetooth, phone storage, app scheduling/retries, UI login/chart rendering, mapping creation, or daily aggregation. It retains test objects/metadata and does not clean up after itself. Use a lab-approved test recording rather than participant data for these examples.

## 7. Manual URL/API upload procedure

For protocol diagnosis, use Bash, curl, Python 3, and a real raw Shimmer file. A plain text dummy can upload but cannot validate decoding. The example requires curl supporting `--fail-with-body`. Run the following blocks in the same shell; substitute the local file path and choose a fresh synthetic filename.

```bash
API_BASE='https://wwr1eh4vg9.execute-api.us-east-2.amazonaws.com'
FILENAME='LABPHONE001__20261006_120002__TEST__Shimmer_L001-001__000.txt'
RAW_FILE='/path/to/real/shimmer-recording'
```

Check whether the raw key is missing:

```bash
curl --fail-with-body -sS -X POST "$API_BASE/missing-files/" \
  -H 'Content-Type: application/json' --data "[\"$FILENAME\"]"
```

Expected: `{"missing_files":["<the filename>"]}`. If empty, choose a new filename before proceeding; PUT can overwrite an existing key.

Request the upload capability and capture it without printing it:

```bash
UPLOAD_RESPONSE=$(curl --fail-with-body -sS --get "$API_BASE/generate-upload-url/" \
  --data-urlencode "filename=$FILENAME")
UPLOAD_URL=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["upload_url"])' <<< "$UPLOAD_RESPONSE")
```

PUT the bytes to the exact returned URL; quote it so its query string stays intact. Do not rewrite the host or use redirect-following options.

```bash
curl --fail-with-body -sS -X PUT -H 'Content-Type: text/plain' \
  --data-binary "@$RAW_FILE" "$UPLOAD_URL"
unset UPLOAD_URL UPLOAD_RESPONSE
```

Successful PUT normally returns HTTP 200 with an empty body. Stop if a command fails. Trigger decoding:

```bash
curl --fail-with-body -sS -X POST "$API_BASE/decode-and-store/" \
  -H 'Content-Type: application/json' \
  --data "{\"full_file_name\":\"$FILENAME\"}"
```

Check for **Decode and store successful**, `decode_s3_key`, and recording timestamps, and ensure there is no `error` field. HTTP 200 alone is insufficient because decode errors can be returned in the JSON body. Repeat missing-files to check raw presence and refresh the website to check decoded visibility. Signed URLs are temporary access capabilities; keep them out of messages and saved logs.

## 8. Use the frontend website

Sign in, then use the header's labeled icons (hover to see names):

| View | What to do |
| --- | --- |
| **Shimmer Data** (`/home`) | Inspect hourly decoded recordings, patient, left/right groups, start/end times (GMT), acceleration and UWB chart buttons, and raw/decoded download controls. |
| **Data Operations / Download Data** (`/data-ops`) | Inspect file listings; filter **Patient**, **Device**, **Date**, **Experiment Name**, **Left Hand Device**, and **Right Hand Device**. Use row **Expand**, **Download**, or **Download All** controls. |
| **Dashboard** (`/dashboard`) | Inspect combined daily data by **Date (GMT)**, patient/device, **Left Hand** and **Right Hand**. Open available chart actions and select the side. Combined data requires aggregation first. |
| **User Operations** (`/user-ops`) | Add/update phone mappings and verify left/right sensor lists. |
| **Daily Aggregator** (`/daily-aggregator`) | Administrator processing controls and **Load Combined Data Files**; see section 10. |

Use column filter controls or **Quick search** where present, and clear filters if an expected row is absent. Views have different columns: Device is hidden in the hourly decoded grid, and Experiment Name is in the raw file view. Do not expect every filter in every view. Expand a raw file group for individual filenames; use decoded-side chart controls in Shimmer Data to inspect acceleration/UWB values. Available sides depend on uploaded data and mapping.

Date normally reflects decoded `recordedTimestamp`, not necessarily the timestamp embedded in the filename. Recording start/end and daily data are shown in GMT/UTC. Some fields, including nested metadata and the hourly grid's **Synced Date**, retain filename-derived dates. For the default simulator fixture, a 2026 filename can coexist with a **2010-10-02** recording window and daily date. Search by device/filename first; use the 2010 date for recording-time views and aggregation.

Optional review/comment/hide controls currently call a missing backend route; saving those changes is unsupported. Actual signed-in interactions still require acceptance testing; the deployed browser-origin data endpoints have been verified.

## 9. Verify an upload succeeded

For ordinary users:

1. Refresh **Shimmer Data** and clear filters.
2. Find the device/patient and expected recording window; check left/right assignment.
3. Open the decoded chart and confirm it contains data.
4. Download the raw or decoded data using the applicable controls.

For simulator/API users and administrators, check the complete chain:

| Check | Evidence |
| --- | --- |
| File no longer appears missing | Repeat `POST /missing-files/` returns an empty array for that key. |
| Raw object exists | Successful raw download or S3 object details show the expected key/size. |
| Decode succeeded | Decode response contains success fields, with no `error`. |
| Metadata appears | `GET /files/combined-meta/` contains the full filename and decoded pointer; administrator can inspect the DynamoDB item. |
| Frontend row appears | Correct device/date filters and mapping, refreshed view. |
| Decoded/chart data loads | Nonempty chart or decoded JSON arrays. |

Raw presence and a phone synced indicator are not sufficient to prove all six checks. Combined daily data is a separate aggregation check.

## 10. Run aggregation manually

An administrator can open **Daily Aggregator**, enter the recording date under **Date (Optional)**, and click **Trigger Aggregation**. Use **Load Combined Data Files → Load Files**, optionally filtered by that date, to inspect outputs. The result should show successful groups and their `s3_key`; check errors and file counts as well as the message.

API equivalent:

```bash
API_BASE='https://wwr1eh4vg9.execute-api.us-east-2.amazonaws.com'
curl --fail-with-body -sS -X POST "$API_BASE/daily-aggregator/" \
  -H 'Content-Type: application/json' --data '{"date":"2026-10-06"}'
```

Replace the synthetic date with a date having decoded recordings. For the default historical simulator fixture, use `2010-10-02`. Objects appear under `combinedbyDay/` as `{device}_{date}_{shimmer}_combined.json`, with nonempty acceleration averages, UWB count, and source-file timestamps. Refresh the combined Dashboard afterward.

Automatic processing is configured for **11:45 PM America/New_York**. A naturally timed run is not yet evidenced in the reports. The scheduler calls backfill with a five-date limit; to reproduce that request manually:

```bash
curl --fail-with-body -sS -X POST "$API_BASE/daily-aggregator/backfill/" \
  -H 'Content-Type: application/json' --data '{"limit":5}'
```

An empty-date manual request processes the next calendar date from state (or yesterday UTC), which may have no files. Prefer an explicit date. Backfill considers a date complete once any combined file exists: rerun the explicit date after late uploads or missing groups. If an HTTP timeout occurs, inspect output/logs before retrying; processing may continue.

## 11. Troubleshooting

| Symptom | Likely layer | What to check |
| --- | --- | --- |
| File always reported missing | Upload/S3 | PUT status, exact object key, expired signed URL. At large object counts, the current missing-files route reads only one S3 listing page. |
| Upload URL request fails | API/Lambda | HTTP status/body, required filename, administrator's main Lambda CloudWatch logs. |
| Raw upload succeeds but no recording row | Decode/metadata | `/decode-and-store/` response, especially `error` even with HTTP 200; verify decoded pointer/metadata. Ask an administrator to retry decode for the existing raw key. |
| Wrong Date shown | Shimmer timestamp | Recording window versus filename time; historical fixture records 2010. Clear date filters and search device first. |
| Patient is `none` | Device mapping | GET mapping for identifier before `__`; Android Map may have selected a sensor MAC. |
| Sensor appears on wrong side | Assignment | Exact parsed Shimmer identifier in left/right lists; unmatched identifiers default to left. |
| Chart unavailable | Decoded S3/backend | `decode_s3_key`, decoded-object existence, chart endpoint response and selected field. |
| Combined data missing | Aggregator | Correct recording date, manual result/group errors, `combinedbyDay/`, scheduler/main logs; rerun date for late uploads. |
| Frontend API errors | Browser/backend | Browser Network tab: requested endpoint, HTTP status/body, browser console; distinguish login problems from API failures. |
| Verification email/login fails | Frontend/Cognito | Entered email/username, spam folder and verification code; administrator checks user confirmation state. Actual email/login acceptance remains pending. |
| Comment/hide save fails | Unsupported contract | `PATCH /decoded-files/metadata/` is absent; this feature is not currently operational. |
| Phone says synced, charts absent | Android decode handling | Raw success can mark synced despite decode failure; inspect metadata instead of repeatedly uploading. |

Isolate the failing step and preserve its HTTP response or filename before requesting code changes. Do not share signed URLs or account tokens in troubleshooting messages.

## 12. Administrator checks

Use the existing authorized AWS profile and **us-east-2**. The backend stack is `shimmer-server-clone`; frontend stack is `shimmer-dashboard-clone`. Resolve resource names from stack outputs rather than guessing:

```bash
aws cloudformation describe-stacks --stack-name shimmer-server-clone \
  --profile shimmer-admin --region us-east-2 --query 'Stacks[0].Outputs'
```

| Inspect | Current location / check |
| --- | --- |
| Lambda / CloudWatch | Main `shimmer-server-clone-MainApiFunction-hNr96vzCphw3`; scheduler `shimmer-server-clone-BackfillSchedulerFunction-lsQhaxFSS55L`. Logs at `/aws/lambda/{function name}`; check decode errors and scheduler's API status/body. |
| S3 | `shimmer-server-clone-databucket-wn9atsyogh42`: raw key/bytes, `decode/`, `combinedbyDay/`. Date-only `daily-aggregated/` debug objects do not preserve separate groups. |
| DynamoDB | Stack outputs: `DevicePatientTableName`, `FileMetadataTableName`, `AggregatorStateTableName`, `AggregatedDataTableName`; inspect device/full-filename keys, decoded pointer, state date, and combined-key summaries. Active summary table ends `18R2RUULV8JDF`; retained old table is unused. |
| Amplify | App `djm6m1z6lh719`, branch `clone`, deployment job status (recorded job 1 SUCCEED). Hosting is manual, with auto-build disabled. |
| EventBridge Scheduler | Default-group schedule `shimmer-server-clone-daily-backfill`: enabled, 23:45 America/New_York, target scheduler Lambda. Check logs around trigger time for evidence of natural execution. |
| Cognito | User pool `us-east-2_dEitkPuXm`: account existence/confirmation for login diagnosis. This does not control backend API callers. |

## 13. Current operational limitations

Real Android/Bluetooth/Shimmer E2E still needs physical-device validation. Successful account signup/email verification/login and authenticated UI acceptance are pending in available evidence. Large-scale performance has not been characterized, and naturally scheduled execution has not yet been observed in the reports. Phone synced status does not guarantee decode; mapping-ID selection and late-data aggregation require the checks above.

Knowing the backend URL currently allows direct API requests: Cognito protects frontend access, but the backend has no caller authentication. The simulator succeeds without login or Android identity. See [the architecture security model](SYSTEM_ARCHITECTURE.md#5-authentication-and-security-model) for the exact boundary.

Evidence: [CORE validation](../shimmer-data-sync-api/CORE_VALIDATION.md), [aggregation validation](../shimmer-data-sync-api/AGGREGATOR_VALIDATION.md), [frontend deployment/validation](../shimmer-sensor-dashboard/DEPLOYMENT.md), [Android deployment/contracts](../shimmer-docking-android/DEPLOYMENT.md), [simulator usage/validated run](../tools/README.md). [System Architecture](SYSTEM_ARCHITECTURE.md) links the implementing source and explains mechanisms.
