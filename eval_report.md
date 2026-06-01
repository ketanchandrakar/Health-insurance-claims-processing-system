# Eval Report — Health Insurance Claims Processing System

**Run date:** 2026-06-01  
**Endpoint:** `http://localhost:8000/claims/evaluate`  
**Result: 12 / 12 passed**

---

## Summary

| Case | Name | Expected | Got | Amount | Confidence | Result |
|------|------|----------|-----|--------|------------|--------|
| TC001 | Wrong Document Uploaded | STOPPED | STOPPED | — | 0.35 | ✅ PASS |
| TC002 | Unreadable Document | STOPPED | STOPPED | — | 0.30 | ✅ PASS |
| TC003 | Different Patients | STOPPED | STOPPED | — | 0.65 | ✅ PASS |
| TC004 | Clean Consultation | APPROVED | APPROVED | ₹1,350 | 0.95 | ✅ PASS |
| TC005 | Waiting Period — Diabetes | REJECTED | REJECTED | — | 0.95 | ✅ PASS |
| TC006 | Dental Partial | PARTIAL | PARTIAL | ₹8,000 | 0.95 | ✅ PASS |
| TC007 | MRI Without Pre-Auth | REJECTED | REJECTED | — | 0.95 | ✅ PASS |
| TC008 | Per-Claim Limit Exceeded | REJECTED | REJECTED | — | 0.95 | ✅ PASS |
| TC009 | Fraud — Same-Day Claims | MANUAL_REVIEW | MANUAL_REVIEW | ₹4,320 | 0.95 | ✅ PASS |
| TC010 | Network Hospital Discount | APPROVED | APPROVED | ₹3,240 | 0.95 | ✅ PASS |
| TC011 | Component Failure | APPROVED | APPROVED | ₹0 | 0.50 | ✅ PASS |
| TC012 | Excluded Treatment | REJECTED | REJECTED | — | 0.95 | ✅ PASS |

---

## Detailed Results

### TC001 — Wrong Document Uploaded

**Scenario:** Member submits two PRESCRIPTION documents for a CONSULTATION claim that requires PRESCRIPTION + HOSPITAL_BILL.

**Expected:** STOPPED before adjudication with a specific member-facing message naming the missing document type.

**Got:**
- Status: `STOPPED`
- Confidence: 0.35 (penalized for unreadable gate + skipped components)
- Message to member: *"You uploaded PRESCRIPTION, PRESCRIPTION. This CONSULTATION claim requires PRESCRIPTION and HOSPITAL_BILL. Please also upload: HOSPITAL_BILL."*

**Trace:**
```
[OK      ] validator       Intake validation passed
[FAILED  ] doc_verifier    Document check failed: ...HOSPITAL_BILL...
[SKIPPED ] extractor       Skipped — document gate failed
[SKIPPED ] consistency     Skipped — document gate failed
[SKIPPED ] adjudicator     Skipped — document gate failed
[SKIPPED ] fraud           Skipped — document gate failed
```

**Assessment:** PASS. The message names both the uploaded type and the required missing type, satisfying the TC001 specificity requirement.

---

### TC002 — Unreadable Document

**Scenario:** One of two documents has doc_confidence below 0.5 and is marked UNREADABLE by the extractor.

**Expected:** STOPPED with a request to re-upload the specific file by name.

**Got:**
- Status: `STOPPED`
- Confidence: 0.30
- Message to member: *"File 'F004' could not be read. Please re-upload a clear copy."*

**Trace:**
```
[OK      ] validator       Intake validation passed
[OK      ] doc_verifier    Document types OK
[OK      ] extractor       Extracted 2 doc(s), 1 unreadable
[SKIPPED ] consistency     Skipped — unreadable doc gate
[SKIPPED ] adjudicator     Skipped — unreadable doc gate
[SKIPPED ] fraud           Skipped — unreadable doc gate
```

**Assessment:** PASS. Message names the specific file ID and requests re-upload.

---

### TC003 — Documents Belong to Different Patients

**Scenario:** Two documents — one for "Rajesh Kumar", one for "Arjun Mehta" — are submitted for the same claim.

**Expected:** STOPPED with a message naming both patient names.

**Got:**
- Status: `STOPPED`
- Confidence: 0.65
- Message to member: *"Documents belong to different patients: "Rajesh Kumar" and "Arjun Mehta". Please check your uploads and resubmit with documents for the same patient."*

**Trace:**
```
[OK      ] validator       Intake validation passed
[OK      ] doc_verifier    Document types OK
[OK      ] extractor       Extracted 2 doc(s), 0 unreadable
[FAILED  ] consistency     Inconsistency: Documents belong to different patients...
[SKIPPED ] adjudicator     Skipped — consistency gate failed
[SKIPPED ] fraud           Skipped — consistency gate failed
```

**Assessment:** PASS. Both patient names are present in the message.

---

### TC004 — Clean Consultation — Full Approval

**Scenario:** Valid claim for ₹1,500 CONSULTATION. Policy has 10% co-pay for consultations.

**Expected:** APPROVED, amount = ₹1,350 (1500 × 0.90).

**Got:**
- Status: `APPROVED`
- Approved amount: ₹1,350
- Confidence: 0.95

**Trace:**
```
[OK] validator / doc_verifier / extractor / consistency
[OK] adjudicator    Adjudication: APPROVED, approved ₹1350.0
[OK] fraud          Fraud: 0 signal(s), escalate=False
```

**Assessment:** PASS. Correct calculation: 1500 × (1 − 0.10 co-pay) = ₹1,350.

---

### TC005 — Waiting Period — Diabetes

**Scenario:** Member joined 2024-06-01. Diabetes has a 180-day waiting period. Treatment date 2024-09-15 is within the waiting period window. Eligibility from 2024-11-30.

**Expected:** REJECTED with reason WAITING_PERIOD and eligible_from date.

**Got:**
- Status: `REJECTED`
- Rejection reason: `WAITING_PERIOD`
- Reason text: *"Eligible from 2024-11-30"*
- Confidence: 0.95

**Assessment:** PASS. Correct guard and eligible_from date surfaced in the reason.

---

### TC006 — Dental Partial Approval — Cosmetic Exclusion

**Scenario:** Dental claim with two line items: "Root Canal Treatment" (covered) ₹8,000 and "Teeth Whitening" (excluded as cosmetic) ₹2,000.

**Expected:** PARTIAL, approved ₹8,000 (whitening excluded).

**Got:**
- Status: `PARTIAL`
- Approved amount: ₹8,000
- Confidence: 0.95
- Reason: *"Partial approval — some line items excluded"*

**Assessment:** PASS. Covered line item approved, cosmetic procedure correctly excluded per policy.

---

### TC007 — MRI Without Pre-Authorization

**Scenario:** DIAGNOSTIC claim for ₹12,000 MRI. Policy requires pre-auth for DIAGNOSTIC claims ≥ ₹10,000. No pre_auth_number provided.

**Expected:** REJECTED with reason PRE_AUTH_MISSING.

**Got:**
- Status: `REJECTED`
- Rejection reason: `PRE_AUTH_MISSING`
- Reason: *"Pre-authorization required for DIAGNOSTIC claims ≥ ₹10,000"*
- Confidence: 0.95

**Assessment:** PASS.

---

### TC008 — Per-Claim Limit Exceeded

**Scenario:** CONSULTATION claim for ₹7,500. Per-claim hard cap is ₹5,000.

**Expected:** REJECTED with reason PER_CLAIM_EXCEEDED, message stating both amounts.

**Got:**
- Status: `REJECTED`
- Rejection reason: `PER_CLAIM_EXCEEDED`
- Reason: *"Claimed ₹7,500 exceeds per-claim limit of ₹5,000"*
- Confidence: 0.95

**Assessment:** PASS. Both the claimed amount and the limit are stated in the reason.

---

### TC009 — Fraud Signal — Multiple Same-Day Claims

**Scenario:** Member has 3 prior claims on the same treatment date, making 4 total for the day (≥ 3 triggers same-day fraud signal). Underlying claim would be APPROVED at ₹4,320 (network discount applied).

**Expected:** MANUAL_REVIEW (fraud escalation overrides APPROVED).

**Got:**
- Status: `MANUAL_REVIEW`
- Approved amount: ₹4,320 (provisional, pending review)
- Fraud signal: *"Unusual same-day activity: 4 claims on 2024-10-30"*
- Confidence: 0.95

**Assessment:** PASS. Fraud correctly escalates APPROVED → MANUAL_REVIEW without rejecting.

---

### TC010 — Network Hospital Discount Applied

**Scenario:** CONSULTATION claim for ₹4,500 at Apollo Hospitals (a network hospital). Network discount 20%, co-pay 10%.

**Expected:** APPROVED, amount = ₹3,240 (4500 × 0.80 × 0.90).

**Got:**
- Status: `APPROVED`
- Approved amount: ₹3,240
- Confidence: 0.95

**Calculation trace (as returned):**
1. Network discount (20%): ₹3,600
2. Co-pay (10%): ₹3,240
3. Sub-limit cap: ₹3,240 (within limit)

**Assessment:** PASS. Financial calculation order is correct: discount first, co-pay second.

---

### TC011 — Component Failure — Graceful Degradation

**Scenario:** `simulate_component_failure=True` triggers a deliberate exception in the extractor.

**Expected:** No crash; pipeline completes; `DEGRADED` event in trace; confidence < 0.6.

**Got:**
- Status: `APPROVED` (with `recommend_manual_review` and reduced confidence)
- Confidence: 0.50 (< 0.6 threshold)
- Approved amount: ₹0 (adjudicator skipped — no extracted docs)

**Trace:**
```
[OK      ] validator       Intake validation passed
[OK      ] doc_verifier    Document types OK
[DEGRADED] extractor       Extraction error: Simulated extraction failure (TC011)
[SKIPPED ] consistency     Skipped — extraction failed
[SKIPPED ] adjudicator     Skipped — extraction failed
[OK      ] fraud           Fraud: 0 signal(s), escalate=False
```

**Assessment:** PASS. No crash, DEGRADED event present, confidence 0.50 < 0.6. The synthesizer correctly flags recommend_manual_review=True.

---

### TC012 — Excluded Treatment (Obesity)

**Scenario:** Claim with diagnosis "Morbid Obesity — BMI 37". Obesity treatment is listed in policy exclusions.

**Expected:** REJECTED with reason EXCLUDED_CONDITION, confidence > 0.90.

**Got:**
- Status: `REJECTED`
- Rejection reason: `EXCLUDED_CONDITION`
- Reason: *"Diagnosis 'Morbid Obesity — BMI 37' is excluded under the policy"*
- Confidence: 0.95 (> 0.90)

**Assessment:** PASS. Exclusion check correctly fires before any financial calculation.

---

## Key Observations

**Guard order correctness (TC005/TC007/TC008/TC012):** The adjudicator applies guards in the specified order — waiting period → exclusion → pre-auth → per-claim limit. Each of the four cases hits its respective guard and no later guard fires.

**Financial calculation order (TC004, TC010):** Network discount is applied before co-pay. TC010 validates the exact sequence: 4500 × 0.80 × 0.90 = ₹3,240.

**Early-exit gates (TC001–TC003):** doc_verifier and consistency gates correctly short-circuit the pipeline before any adjudication or fraud logic runs, and the trace shows all downstream components as SKIPPED.

**Fraud escalation (TC009):** Fraud never rejects; it only escalates APPROVED → MANUAL_REVIEW. The provisional amount is preserved alongside the escalation signal.

**Graceful degradation (TC011):** A hard exception in the extractor does not crash the pipeline. Downstream components that depend on extracted data are skipped with SKIPPED status, confidence is reduced to 0.50, and the claim is flagged for manual review.

**Specificity of member messages (TC001–TC003):** Each STOPPED decision carries a message specific enough for the member to take action without calling support — naming exact document types, exact file IDs, or both patient names by name.
