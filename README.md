# DeviationLab

DeviationLab extracts behavioral evidence from images and short videos of everyday work. The current application identifies six compliance-related conditions in bakery-store footage. It first locates the person or area relevant to a check, then classifies that image region. Each observation retains its source location so researchers can examine the finding, record a correction and export the results.

The workflow uses trained YOLO detectors and MobileNetV3 classifiers. The English application runs in a browser with the included models and requires no API key. Researchers can use its observations to study where deviations occur and, with suitable sampling and linked records, how work changes over time.

The public repository does not include sample images or videos. Upload your own authorized media to use the application. The historical test settings and results contain no media and are retained for audit; repeating those exact tests requires the privately held files. See [media restrictions](REVIEW-NOTES.md#access-and-media-restrictions).

## Install and start

Download and extract the current repository. Open a terminal in the folder containing this README and `run.py`. Keep the model folders in place. Older downloads may contain media no longer included in the current version.

Use Python 3.13 for the tested configuration. Install FFmpeg separately and check that both commands work:

```sh
python3 --version
ffmpeg -version
ffprobe -version
```

On macOS or Linux:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python tools/verify.py
python run.py
```

On Windows PowerShell:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe tools\verify.py
.\.venv\Scripts\python.exe run.py
```

Open **http://127.0.0.1:7891/**. Keep the terminal open while using the page. Press Ctrl+C in that terminal to stop it. Do not double-click `index.html`: that opens an HTML file without the analysis server.

Installation requires internet access, Python and FFmpeg. Once installed, the application analyzes media with the included weights without sending images to an LLM provider. The local installation was tested on macOS with Python 3.13. The Windows and Linux commands have not been independently tested. Allow extra time for the first analysis while the model libraries and weights load.

## Run a first analysis

1. Select the scene matching your own authorized image or video, then upload the file.
2. Click **Run analysis**. Uploading a file alone only creates a preview; an image is assessed once. To test your own permitted video, choose **3** frames under **Sampling & cashier region** for a quick run.
3. Wait for **Analysis complete**. Inspect the findings, including those marked uncertain. Click a timestamp to inspect its frame and any available region box.
4. Edit findings or add a missed finding if needed. Save the review before exporting if you want it recorded as a saved review.
5. Click **Export JSON** or **Export CSV**. The files download to your browser's download folder.

Choose **Kitchen** for head covering, mask coverage and workwear. Choose **Front of house** for table clearance, bread display and cashier occupancy. Draw the employee work area before testing cashier occupancy. Select the space behind the counter where the employee stands, not the whole store or customer area. Keep that region fixed for a stationary camera. Without a region, the cashier check reports that configuration is required.

A successful smoke test means processing completed, not that every judgment was correct. Published Git history was rewritten on 29 October 2026 to remove the sample folder. Old cached commit URLs and previously downloaded copies may still contain media. Collaborators should clone the cleaned repository again rather than merge an old clone back into it.

## What the page supports

| Scene | Checks |
|---|---|
| Kitchen | Head covering, mask coverage, workwear or apron |
| Front of house | Table clearance, bread-display gaps, cashier occupancy |

Use JPG or PNG images, or browser-playable MP4/MOV videos, up to 30 MiB and 60 seconds. Decoded dimensions must not exceed 4096 pixels on either axis. Images produce one frame assessment; videos use 3, 6 or 12 sampled frames. CPU processing may take several minutes. This application does not track people or calculate continuous incident durations.

Results are counted by category. If different sampled frames produce different outcomes, the same category can appear in both the issue and uncertain counts. Read [how results are produced](REVIEW-NOTES.md#how-a-result-is-produced) before interpreting the output.

## Use observations in research

Exports retain the model findings and saved corrections separately. Researchers can add store, camera and recording-date identifiers, apply a consistent sampling rule and summarize observations for comparison. For example, the share of assessable sampled moments when a cashier area is unoccupied describes coverage during the sampled period. Linking these summaries to feedback or performance records requires the corresponding identifiers and dates. The application exports observations for this work rather than constructing a store-level dataset automatically.

## Read the documentation

| File | Purpose |
|---|---|
| [REVIEW-NOTES.md](REVIEW-NOTES.md) | Recognition steps, output meanings, privacy and submission scope |
| [MODEL-STATUS.md](MODEL-STATUS.md) | Model versions, training choices and development results |
| [DELIVERY-AUDIT.md](DELIVERY-AUDIT.md) | Completed tests, repeatable verification commands and untested conditions |
| [EVALUATION-CHECKLIST.md](EVALUATION-CHECKLIST.md) | Protocol for the independent evaluation that remains to be done |
| [proposal-pipeline/README.md](proposal-pipeline/README.md) | Code structure and the difference between contract tests and web inference |
| [reproduction/README.md](reproduction/README.md) | Training scripts and the source data needed to rerun them |
| [third-party/README.md](third-party/README.md) | Included third-party notices |

`SHA256SUMS.txt` lists the public release files and their hashes. `python tools/verify.py` checks those hashes, historical test-record consistency, registries and documented development metrics without running recognition or requiring private media. [MANIFEST.md](MANIFEST.md) describes the directory layout.

## Troubleshooting

| Symptom | What to check |
|---|---|
| The page has no styling or stays on Loading | Use the HTTP address above with `python run.py` running, not a `file://` address. |
| The browser cannot connect | Check the terminal for an error. Port 7891 may already be occupied. On macOS/Linux, `PORT=7892 python run.py` uses another port. |
| A Python package cannot be found | Activate the same environment used to install `requirements.txt`. Check `python -m pip show torch torchvision ultralytics`. |
| Video analysis fails | Check `ffmpeg` and `ffprobe`, file size, duration and decoding. Try an authorized local PNG to separate video decoding from model inference. |
| The engine is unavailable or a model hash fails | Run `python tools/verify.py`. Restore the complete release rather than downloading unrelated weights. |
| The cashier check did not run | Draw the employee area and run the analysis again. |
| Findings are uncertain or disagree with the image | Inspect the frame and region. Record a human correction; do not interpret uncertainty as compliance. |
| Queue full | Wait for the active analysis. This local server processes one job at a time. |

Job records and review history are stored in `~/.deviationlab-review/jobs/`, outside the repository. Uploaded media and decoded frames are processed in temporary files; job records retain their source hash and findings. Do not commit runtime records. The repository provides code for authorized collaborators to run. Updating it does not update the existing cloud deployment.
