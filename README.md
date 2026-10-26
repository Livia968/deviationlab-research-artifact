# DeviationLab

DeviationLab checks restaurant images and short videos for six predefined conditions. It runs YOLO region detection and MobileNetV3 classification on your computer, then lets you review the findings and export the evidence. The interface is in English. You do not need an API key or a model-selection step.

This private research artifact is for editors and reviewers. It contains restricted monitoring footage. Do not make the repository public, enable GitHub Pages, or redistribute the sample media. See [access and media restrictions](REVIEW-NOTES.md#access-and-media-restrictions).

## Install and start

Download and extract the complete repository or release ZIP. Open a terminal in the folder containing this README and `run.py`. Keep the model and sample folders in place.

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

The first dependency installation needs internet access. The application uses the bundled weights for inference and does not send images to an LLM provider. The tested platform is macOS with Python 3.13; the Windows and Linux instructions are provided for portability but have not been independently tested. FFmpeg and the Python environment are not included in the ZIP. The first analysis also loads the model libraries and weights, so allow extra time before expecting progress.

## Run a first analysis

1. Select **Kitchen** and upload `samples/kitchen-mask.mp4`.
2. Open **Sampling & cashier region** and choose **3** frames for a quick test. Click **Run analysis**. Uploading or playing the video alone does not run inference.
3. Wait for **Analysis complete**. Review the issue and uncertain categories. Click a timestamp to inspect its frame and any available region box.
4. Edit findings or add a missed finding if needed. Save the review before exporting if you want it recorded as a saved review.
5. Click **Export JSON** or **Export CSV**. The files download to your browser's download folder.

For **Front of house**, use the matching files in [samples/](samples/README.md). Draw the employee work area before testing cashier occupancy. Select the space behind the counter where the employee stands, not the whole store or customer area. Keep that region fixed for a stationary camera. Without a region, the cashier check reports that configuration is required.

The bundled clips are walkthrough examples, not labeled accuracy tests. Their filenames name the check to inspect; they do not establish that a deviation occurs in every frame.

## What the page supports

| Scene | Checks |
|---|---|
| Kitchen | Head covering, mask coverage, workwear or apron |
| Front of house | Table clearance, bread-display gaps, cashier occupancy |

Use JPG or PNG images, or browser-playable MP4/MOV videos, up to 30 MiB and 60 seconds. Decoded dimensions must not exceed 4096 pixels on either axis. Images produce one frame assessment; videos use 3, 6 or 12 sampled frames. CPU processing may take several minutes. This application does not track people or calculate continuous incident durations.

The result count refers to categories, not people. A category can appear in both the issue count and the uncertain count when different sampled frames have different outcomes. Read [how results are produced](REVIEW-NOTES.md#how-a-result-is-produced) before interpreting the output.

## Read the documentation

| File | Purpose |
|---|---|
| [REVIEW-NOTES.md](REVIEW-NOTES.md) | Recognition steps, output meanings, privacy and submission scope |
| [MODEL-STATUS.md](MODEL-STATUS.md) | Frozen model versions, development metrics and training limits |
| [DELIVERY-AUDIT.md](DELIVERY-AUDIT.md) | Completed tests, repeatable verification commands and untested conditions |
| [EVALUATION-CHECKLIST.md](EVALUATION-CHECKLIST.md) | Protocol for the independent evaluation that remains to be done |
| [proposal-pipeline/README.md](proposal-pipeline/README.md) | Code structure and the difference between contract tests and web inference |
| [reproduction/README.md](reproduction/README.md) | Training-source requirements and missing private inputs |
| [third-party/README.md](third-party/README.md) | Included third-party notices |

`SHA256SUMS.txt` lists the release files and their hashes. `python tools/verify.py` checks those hashes, sample counts, registries and documented development metrics without running recognition. [MANIFEST.md](MANIFEST.md) describes the directory layout.

## Troubleshooting

| Symptom | What to check |
|---|---|
| The page has no styling or stays on Loading | Use the HTTP address above with `python run.py` running, not a `file://` address. |
| The browser cannot connect | Check the terminal for an error. Port 7891 may already be occupied. On macOS/Linux, `PORT=7892 python run.py` uses another port. |
| A Python package cannot be found | Activate the same environment used to install `requirements.txt`. Check `python -m pip show torch torchvision ultralytics`. |
| Video analysis fails | Check `ffmpeg` and `ffprobe`, file size, duration and decoding. Try a bundled JPG to separate video decoding from model inference. |
| The engine is unavailable or a model hash fails | Run `python tools/verify.py`. Restore the complete release rather than downloading unrelated weights. |
| The cashier check did not run | Draw the employee area and run the analysis again. |
| Findings are uncertain or disagree with the image | Inspect the frame and region. Record a human correction; do not interpret uncertainty as compliance. |
| Queue full | Wait for the active analysis. This local server processes one job at a time. |

Job records and review history are stored in `~/.deviationlab-review/jobs/`, outside the repository. Uploaded media and decoded frames are processed in temporary files; job records retain their source hash and findings. Do not commit runtime records. A repository upload makes the code available to authorized collaborators; it does not host the website. This release does not change the existing cloud deployment.
