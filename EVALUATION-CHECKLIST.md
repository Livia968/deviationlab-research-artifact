# Independent evaluation plan

Independent evaluation is pending. Before reporting accuracy on new footage, complete the steps below. The walkthrough tests verify execution only.

## Freeze the system

Record the release commit, weight hashes, class mappings, region definitions, transforms, thresholds and frame-sampling rule before opening the evaluation set. Include the cashier-region annotation procedure. Do not tune a threshold using the same data later reported as an independent test.

## Build the reference set

Use authorized footage from stores and cameras excluded from training and model selection. Include ordinary operating periods as well as candidate deviations. Keep clips from the same source in the same data split so near-duplicate frames cannot appear in both development and evaluation sets.

Have two coders label each target in each frame independently, without seeing the model predictions. Use four labels: deviation, no deviation, unclear and inapplicable. Retain both initial judgments, document disagreement resolution and record the relevant region. For cashier occupancy, specify who draws the region and what counts as the employee work area.

## Measure the separate stages and full sequence

1. Evaluate localization for the five automatically localized checks. Report missed regions and irrelevant detections. Evaluate manual cashier-region repeatability separately.
2. Evaluate classification on correctly localized or reference crops to isolate classifier errors.
3. Evaluate the full deployed sequence on all eligible target/frame pairs, including localization failures, uncertain outcomes and checks that did not run.
4. Report precision, recall, specificity where applicable, definite-answer coverage and execution failures. Report class counts and uncertainty intervals with clustering appropriate to repeated footage from the same store or camera.
5. Compare original model observations and separately saved human-reviewed results against the independent labels. Report review time and coder agreement.
6. Measure processing time and computing cost on declared hardware. Document failure cases such as occlusion, camera movement and people outside the employee area.

Do not count sampled observations as unique people or continuous incidents. If test results inform a model change, report that work as development tuning and use a new independent set to evaluate the revised model.
