# P3 evaluation results

Synthetic results are diagnostics, not human-labelled validation.
PASS/FAIL applies only to the named configuration and measured scope.

- public_data: NOT_MEASURED. no licensed public test set with completed HCAT human labels supplied
- human_synthetic: NOT_MEASURED. 400-row blank annotation workflow exported; no human labels supplied
- suggestions: NOT_MEASURED. no provider credentials or two completed 40-item rating sheets
- usability: NOT_MEASURED. five-person SUS study belongs to NFR4; see docs/frontend-usability.md
- deidentification / recall: PASS. 0.984127 >= 0.95
- deidentification / mandatory_types / PHONE: PASS. 1.0 == 1
- deidentification / mandatory_types / EMAIL: PASS. 1.0 == 1
- deidentification / mandatory_types / HEALTH_CARD: PASS. 1.0 == 1
- deidentification / mandatory_types / RECORD_NUMBER: PASS. 1.0 == 1
- deidentification / over_removal: PASS. 0.0 < 0.05
- deidentification / unit_names_removed: PASS. 0 == 0
- synthetic_intent / targets / sentiment_macro_f1: FAIL. 0.724113 >= 0.75
- synthetic_intent / targets / category_micro_f1: PASS. 0.822018 >= 0.7
- synthetic_intent / targets / stage_accuracy: PASS. 0.741144 >= 0.65
- synthetic_intent / targets / urgency_high_recall: FAIL. 0.0 >= 0.8
- issues / recovery / target: PASS. 8 >= 6
- issues / patterns / discharge_medication: PASS.
- issues / patterns / night_noise: PASS.
- issues / patterns / transport: PASS.
- issues / human_quality: NOT_MEASURED. two members must rate ten comments from each top issue
- dashboard / endpoints / /issues / maximum: PASS. 0.008668 <= 2
- dashboard / endpoints / /issues / http_200: PASS. True == True
- dashboard / endpoints / /comments?limit=50 / maximum: PASS. 0.008581 <= 2
- dashboard / endpoints / /comments?limit=50 / http_200: PASS. True == True
- dashboard / endpoints / /compare?by=category / maximum: PASS. 0.018057 <= 2
- dashboard / endpoints / /compare?by=category / http_200: PASS. True == True
- dashboard / endpoints / /compare?by=stage / maximum: PASS. 0.017562 <= 2
- dashboard / endpoints / /compare?by=stage / http_200: PASS. True == True
- dashboard / endpoints / /compare?by=unit / maximum: PASS. 0.01492 <= 2
- dashboard / endpoints / /compare?by=unit / http_200: PASS. True == True
- dashboard / endpoints / /suggestions / maximum: PASS. 0.008939 <= 2
- dashboard / endpoints / /suggestions / http_200: PASS. True == True
- dashboard / endpoints / /issues/1/comments / maximum: PASS. 0.012227 <= 2
- dashboard / endpoints / /issues/1/comments / http_200: PASS. True == True
- dashboard / endpoints / /issues/1/comments?format=csv / maximum: PASS. 0.00743 <= 2
- dashboard / endpoints / /issues/1/comments?format=csv / http_200: PASS. True == True
- dashboard / comparison_integrity / category: PASS. True == True
- dashboard / comparison_integrity / stage: PASS. True == True
- dashboard / comparison_integrity / unit: PASS. True == True
- performance: NOT_MEASURED. benchmark skipped or embedding unavailable; import/API timing is partial
