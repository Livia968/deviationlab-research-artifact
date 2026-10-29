# Workflow and reviewer guidance

## How a result is produced

The workflow turns each selected image or video sample into observations of the conditions listed below. The browser first previews the media. Clicking **Run analysis** sends it to the application server, where FFmpeg decodes the image or samples the video. For a video of duration D and N samples, the timestamps are i × D / N for i = 0 through N - 1, rounded to milliseconds. The last sample is before the end of the clip.

The server applies the three checks for the selected scene to each decoded frame:

| Check | Region supplied to MobileNetV3 | Deviation condition |
|---|---|---|
| Head covering | YOLO head box | A required cap or hairnet is absent |
| Mask coverage | YOLO head box | The mask does not cover the nose and mouth |
| Workwear | Upper 85% of a YOLO person box | Neither workwear nor an apron is visible |
| Table clearance | Generic YOLO dining-table box | Garbage or uncleared material remains on the table |
| Bread display | Trained bakery-region detector box | The display has substantial empty gaps |
| Cashier occupancy | User-selected employee work area | No employee is visible in that area |

For the five automatically located targets, YOLO identifies relevant regions and MobileNetV3 classifies the resulting crops. Mask and head-covering checks share the same head boxes. The workwear check uses person boxes, so interpreting its findings requires checking that the people shown are employees.

For cashier occupancy, the user draws the employee work area before analysis. MobileNetV3 classifies that entire area. YOLO person boxes provide additional evidence without changing the occupancy judgment.

YOLO runs on CPU with image size 960 and detection confidence 0.25. The runtime classifies at most 50 candidate regions per check. MobileNetV3 applies the transforms and ordered labels in [the model registry](proposal-pipeline/models/registry.json). A highest class score below 0.60 produces an uncertain result. This score is the model’s classification score, not a calibrated probability that a deviation occurred.

## Read the findings

| Output | Meaning |
|---|---|
| Issue observed / `present` | At least one classified region in that sampled frame indicates a deviation |
| No issue detected / `absent` | The available classified regions indicate no deviation; this does not prove that every person or area was detected |
| Uncertain / `uncertain` | A classifier abstained or no relevant region was detected |
| Configuration required | The cashier region was not supplied, so that check did not run |
| Failed job | Media decoding or inference failed; the system does not replace the model or fabricate results |

Each check combines its region judgments into one result for the frame: a deviation takes priority, followed by uncertainty and then no deviation. JSON also retains the separate region judgments.

Across a video, the interface groups findings by category and status. A category can be an issue in one frame and uncertain in another, so the two category counts can overlap. **Checks not completed** counts check/frame executions, not unique categories. Sample times identify observations; they are not incident start and end times. Frames between samples may contain missed events.

## Review and export

The original model observations remain in the job record. Editing a finding changes the review draft. **Save review** appends a revision to the review history rather than overwriting the model output.

- JSON includes frame assessments, sampled times, region observations, model identifiers, weight hashes, saved review history and the current unsaved draft.
- CSV contains `model_check` rows, the latest `saved_human_review` rows and `unsaved_review_draft` rows. Separate these row types before counting or comparing results. Use CSV for tabular summaries and JSON for the complete evidence record.
- Clicking a timestamp seeks the source video and displays the associated available box. The interface requires the current source media to remain loaded for playback.

The unit of observation is a target in a sampled frame. A series of observations can describe how often a condition appears in the samples, but does not identify employees or establish the number or duration of incidents. These outputs are intended for research, not individual employment decisions.

## Evidence and submission scope

The bundled models are development checkpoints. [MODEL-STATUS.md](MODEL-STATUS.md) reports the saved crop-level development results and their limitations. The walkthrough tests confirm execution, review and export; they do not estimate recognition accuracy. Independent evaluation of the full detection/classification sequence remains pending.

This repository supplies the prototype component of the [Organization Science special issue](https://orgsci.org/). The proposal and technical appendix are separate submission documents and are not included or edited here. Before submitting them, check that their descriptions acknowledge the manual cashier region, sampled-frame analysis and pending independent evaluation.

## Access and media restrictions

The author has withdrawn the sample images and videos from the current public repository. No sample media are distributed with this version. Local author-held submission copies remain private and were not deleted. Use only media you are authorized to process. Image editing, face blurring and repository access do not establish anonymity, consent, copyright permission or IRB clearance.

Historical test-case settings and execution records are retained as text, without embedded media. They document prior functional tests and are not an accuracy benchmark. The optional smoke test requires an explicitly supplied private folder; a normal installation and analysis of your own media do not require these test files.

Published Git history was rewritten on 29 October 2026 to remove `samples/` from all commits. The release tag also points to a media-free version. Old cached commit URLs and previous downloads may still contain removed media; history rewriting cannot revoke copies already downloaded. GitHub Support may need to purge cached views and unreachable objects. Earlier permission for some clips was limited to private editorial and reviewer testing, not public redistribution. Do not treat historical availability as permission to reuse or redistribute media. Collaborators should re-clone the cleaned repository and must not merge or push old history back into it.

Inference runs locally without an external LLM request. Job and review records remain on the machine running the server. Restrict access to that machine and its data directory. The local launcher listens only on 127.0.0.1; it is not a secured public hosting setup.

Third-party code and pretrained weights retain their original terms; see [third-party/README.md](third-party/README.md). Repository access does not alter those licenses or the permissions attached to the media. Original training media are not included.
