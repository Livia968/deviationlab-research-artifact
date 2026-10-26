# Workflow and reviewer guidance

## How a result is produced

The browser previews the selected media locally. Clicking **Run analysis** sends it to the local server. FFmpeg decodes one image or the requested video samples. For a video of duration D and N samples, the timestamps are i × D / N for i = 0 through N - 1, rounded to milliseconds. The last sample is before the end of the clip.

The server applies the three checks for the selected scene to each decoded frame:

| Check | Region supplied to MobileNetV3 | Deviation condition |
|---|---|---|
| Head covering | YOLO head box | A required cap or hairnet is absent |
| Mask coverage | YOLO head box | The mask does not cover the nose and mouth |
| Workwear | Upper 85% of a YOLO person box | Neither workwear nor an apron is visible |
| Table clearance | Generic YOLO dining-table box | Garbage or uncleared material remains on the table |
| Bread display | Trained bakery-region detector box | The display has substantial empty gaps |
| Cashier occupancy | User-selected employee work area | No employee is visible in that area |

YOLO class labels do not determine the final compliance judgment. MobileNetV3 classifies each crop. Mask and head-covering checks share the detected head boxes; the mask input is not a separately detected face box. The generic person detector does not identify employees, so people in irrelevant areas can be included. Reviewers must check the evidence.

Cashier occupancy is a documented exception to automatic region localization. YOLO person boxes are retained as supporting evidence, but the occupancy classifier uses the whole user-selected work area. Those person boxes do not override its judgment. The system does not automatically discover the cashier station.

YOLO runs on CPU with image size 960 and detection confidence 0.25. The runtime classifies at most 50 candidate regions per check. MobileNetV3 applies the transforms and ordered labels in [the model registry](proposal-pipeline/models/registry.json). A top-class score below 0.60 becomes uncertain. This score is not a calibrated probability.

## Read the findings

| Output | Meaning |
|---|---|
| Issue observed / `present` | At least one classified region in that sampled frame indicates a deviation |
| No issue / `absent` | The available classified regions indicate no deviation; this does not prove that every person or area was detected |
| Uncertain / `uncertain` | A classifier abstained or no relevant region was detected |
| Configuration required | The cashier region was not supplied, so that check did not run |
| Failed job | Media decoding or inference failed; the system does not replace the model or fabricate results |

Within a check and frame, any deviation takes priority over uncertainty, and uncertainty takes priority over no deviation. JSON retains the individual region judgments even when the displayed result aggregates them.

Across a video, the interface groups findings by category and status. A category can be an issue in one frame and uncertain in another, so the two category counts can overlap. **Checks not completed** counts check/frame executions, not unique categories. Sample times identify observations; they are not incident start and end times. Frames between samples may contain missed events.

## Review and export

The original model observations remain in the job record. Editing a finding changes the review draft. **Save review** appends a revision to the review history rather than overwriting the model output.

- JSON includes frame assessments, sampled times, region observations, model identifiers, weight hashes, saved review history and the current unsaved draft.
- CSV contains `model_check` rows, the latest `saved_human_review` rows and `unsaved_review_draft` rows. Separate these row types before counting or comparing results. CSV is a convenient summary; JSON is the more complete evidence record.
- Clicking a timestamp seeks the source video and displays the associated available box. The interface requires the current source media to remain loaded for playback.

The outputs support human inspection. They do not establish employee identity, unique person counts, continuous absence duration, or grounds for an employment decision.

## Evidence and submission scope

The bundled models are development checkpoints. [MODEL-STATUS.md](MODEL-STATUS.md) reports the saved crop-level development results and their limitations. The walkthrough tests confirm execution, review and export; they do not estimate recognition accuracy. Independent evaluation of the full detection/classification sequence remains pending.

This repository supplies the prototype component of the [Organization Science special issue](https://orgsci.org/). The proposal and technical appendix are separate submission documents and are not included or edited here. Before submitting them, check that their descriptions acknowledge the manual cashier region, sampled-frame analysis and pending independent evaluation.

## Access and media restrictions

The project owner authorized the six monitoring clips and derived still images for private testing by editors and reviewers on 26 October 2026. Keep the repository private and grant access only to authorized reviewers or project collaborators. Public distribution of the videos, still images or a package containing them requires separate permission. Do not upload screenshots containing this footage to public issues or documentation.

Inference runs locally without an external LLM request. Job and review records remain on the machine running the server. Restrict access to that machine and its data directory. The local launcher listens only on 127.0.0.1; it is not a secured public hosting setup.

Third-party code and pretrained weights retain their original terms; see [third-party/README.md](third-party/README.md). A private repository does not replace license review or authorize redistribution beyond the original permissions. Original training media are not included.
