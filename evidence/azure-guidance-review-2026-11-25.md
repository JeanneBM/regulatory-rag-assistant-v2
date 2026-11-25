# Azure guidance evaluation findings — 25 November 2026

**The twelve-case full guidance run completed, but answer quality did not pass.**
This public summary omits raw operator reports and deployment metadata. The original
reports and the full statement-by-statement source assessment remain private.
The assessment was performed by the assistant, not an independent domain expert.

| Automatic check | Original result |
| --- | --- |
| Expected source retrieved | 10/10 |
| Expected source ranked first | 8/10 |
| Expected source cited after verification | 8/10 |
| Unrelated controls abstained | 2/2 |
| Generated / shown / rejected claims | 36 / 25 / 11 |
| Technical errors | 0 |

All 36 generated statements were compared with their own attached quotations.

| Disposition | Supported | Partial | Wrong / unsupported |
| --- | --- | --- | --- |
| Shown (25) | 19 | 5 | 1 wrong actor |
| Rejected (11) | 7 | 3 | 1 unsupported |

The model labelled all shown claims supported; the source assessment disagreed on
six. There were also seven false rejections. A locator hit and a model label are
therefore not counted as semantic answer validation.

The failures involved page-wide exception keywords applied to unrelated measures,
functional NIST prerequisites classified as legal duties, recipient/signatory and
model/output substitutions, omitted scope conditions and details absent from the
claim's own page. Some rejected claims really did omit applicable exemptions.
GPAI01 and GPAI02 returned text but did not retain their configured source locator.

The candidate correction keeps numeric and article checks, sends PDF scope and
modality to the model with the full page and registered source context, and retains
the EU paragraph/point rules. Generation and verification prompts emphasise exact
actors, objects, applicable conditions and concise answers. Synthetic offline tests
check routing and strict filtering; they do not establish live model accuracy.

Two source-locator corrections are recorded separately from model behaviour:
GPAI01 now expects PDF page 5, which contains Measure 1.1; page 4 contains recitals
and scope. GPAI02 accepts page 5 for contacts and page 6 for actual provision of
downstream information and safeguards. The original 8/10 score is unchanged.
Future comparisons must distinguish expectation changes from quality improvements.

The user-reported ten-case EU run had retrieval 8/8, citations 6/8 and abstentions
2/2. Its detailed report is still needed, particularly for A01/A02. The combined
terminal summaries cover 22 cases with retrieval 18/18, citations 14/18 and abstentions
4/4; only the twelve-case guidance details have been source-reviewed here.

Next: review the EU report, rerun the corrected full Azure evaluation and assess
shown/rejected claims. Keep the working Azure environment until that evidence is
captured. These rule, prompt and fixture changes require no new import or provisioning.
