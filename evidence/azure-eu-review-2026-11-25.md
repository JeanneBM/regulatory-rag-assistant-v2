# Azure EU rerun findings — 25 November 2026

The ten-case full Azure EU run completed at 18:23 UTC (19:23 in Poland).
Automatic citation and abstention expectations are met. Semantic answer quality
still has limitations. The raw report and full statement-by-statement assessment
remain private; this public summary excludes deployment metadata and raw payloads.
The assessment was performed by the assistant, not an independent domain expert.

| Automatic metric | Result |
| --- | --- |
| Expected article retrieved | 8/8 |
| Expected article ranked first | 8/8 |
| Expected article cited after verification | 8/8 |
| Correct control abstentions | 2/2 |
| Generated / shown / rejected claims | 26 / 22 / 4 |
| Technical errors | 0 |

The earlier reported EU citation score was 6/8. This run improves locator coverage
to 8/8, including A01/A02. A citation hit is not a complete-answer accuracy score.

All 26 statements were compared with their own quotations:

| Disposition | Supported | Partial |
| --- | --- | --- |
| Shown (22) | 18 | 4 |
| Rejected (4) | 1 false rejection | 3 justified rejections |

The four partial shown claims are in A01 (two), A02 and A04. They omit affected
persons or rights/obligations context, omit a time condition and blur alternative
conditions, or omit confidentiality/intellectual-property safeguards. The core
statements are recognisable, but the model's supported labels are too permissive.

A03 retains a supported format/timing statement while its principal notice-duty
statement was correctly rejected for a missing exception. Its article citation
therefore masks incomplete answer coverage. Point-level support also does not
establish that an answer contains every relevant exception in another paragraph.

N01 abstains before generation because no evidence is retrieved. N02 retrieves
eight unrelated fragments and the model correctly abstains. Only one control is
retrieval-gated; both final abstentions are correct.

One A04 rejection is a rule error: the source's applicability qualifier belongs to
one article reference, while the statement concerns a different, unconditional
reference. The correction keeps that qualifier local and still sends the statement
to model verification. Six synthetic scope regressions and all prior tests pass
(158 total); numeric/reference checks and strict acceptance remain active.

The original run was not recalculated with the correction. Live confirmation of
the narrow rule change remains pending. The report does not record its application
commit or resolved model version. The new guidance rerun report is still needed;
its earlier baseline is not combined with this EU run as one corrected-version score.
