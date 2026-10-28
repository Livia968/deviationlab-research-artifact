'use strict';
// Display copy only. Stored predictions and recognition protocols stay intact.
const COPY = Object.freeze({
  targets: {cap_absent: 'Missing cap or hairnet', mask_uncovered: 'Mask not covering nose and mouth', uniform_absent: 'Missing workwear or apron', table_uncleared: 'Uncleared table', bread_shelf_underfilled: 'Underfilled bread display', cashier_vacancy: 'Unattended cashier station'},
  checks: {cap_absent: 'Cap or hairnet', mask_uncovered: 'Mask coverage', uniform_absent: 'Workwear or apron', table_uncleared: 'Table clearing', bread_shelf_underfilled: 'Bread display', cashier_vacancy: 'Cashier presence'},
  model: 'YOLO + MobileNetV3'
});
function englishText(value, fallback = '') {
  const text = String(value ?? '').trim();
  if (!/[\u3400-\u9fff]/u.test(text)) return text || fallback;
  const first = text.split(/\s+\/\s+/u)[0];
  return first && !/[\u3400-\u9fff]/u.test(first) ? first.trim() : fallback;
}
function findingLabel(event) {
  if (String(event.behavior).includes(' / ') && COPY.targets[event.deviation_type]) return COPY.targets[event.deviation_type];
  return englishText(event.behavior, COPY.targets[event.deviation_type] || 'Finding');
}
const EVIDENCE_COPY = Object.freeze({
  'MobileNetV3 classified the localized regions; review the region observations in the export.': 'The model classified the detected regions. The export includes the judgment for each region.',
  'No relevant region was localized. Compliance cannot be determined.': 'The model could not locate a relevant region, so this check is uncertain.',
  'Draw the cashier employee area to run this check.': 'Select the employee work area behind the cashier counter to run this check.',
  'At least one visible head was classified as not wearing a head covering.': 'The model classified at least one visible head as missing a cap or hairnet.',
  'No reliable head was localized, or at least one localized head had insufficient evidence.': 'The model could not reliably locate a head, or had too little evidence for at least one head.',
  'All localized heads were classified as wearing a head covering; this does not guarantee that every person in the image was localized.': 'The model classified all detected heads as having a cap or hairnet. It may have missed other people.',
  'At least one localized target was classified as uncovered.': 'The model classified at least one detected face as not fully covered by a mask.',
  'At least one localized target was classified as ordinary_clothes.': 'The model classified at least one detected person as wearing ordinary clothes rather than workwear or an apron.',
  'The model did not produce a reliable binary decision covering all localized targets.': 'The model could not make a reliable decision for every detected target.',
  'All localized targets were classified as non-deviations; this does not guarantee that every person in the image was localized.': 'The model found no issue in the detected targets. It may have missed people in the image.',
  'A person was detected inside the cashier-side ROI.': 'The model detected a person in the selected cashier region.',
  'No person was detected inside the cashier-side ROI; a human reviewer should still verify this single-frame result.': 'The model detected no one in the selected cashier region. Review the image to confirm this finding.',
  'The model localized at least one deviation region above the decision threshold.': 'The model found at least one issue region above its decision threshold.',
  'The model produced only candidate regions below the decision threshold; the result is retained as insufficient evidence.': 'The candidate regions fell below the decision threshold. The finding is uncertain.',
  'No deviation region was localized.': 'The model did not find an issue region.',
  'No deviation region was localized, but the available negative examples are insufficient to confirm a normal state.': 'The model did not find an issue region. It has too few negative examples to confirm a normal result.',
  'A cashier-side ROI has not been configured for this camera.': 'Select the area where the cashier stands to run this check.',
  'A configured second detector localized a supported deviation after no decisive primary detection.': 'The secondary detector found an issue that the primary detector could not confirm.'
});
function evidenceText(value) {
  if (!String(value ?? '').trim()) return 'No evidence provided.';
  const text = englishText(value, 'The provider returned evidence in another language. See the original JSON export.');
  return EVIDENCE_COPY[text] || text;
}
