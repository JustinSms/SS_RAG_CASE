# Retrieval evaluation

> **Note on this run (2026-10-04):** it used `MAX_CANDIDATES` 50 because the eval image was older than the change to 20 that the app uses now, and the data was ingested before the parser stopped keeping HTML tags in headings. It was decided not to rerun for this. The tuning picked `SIMILARITY_CUTOFF` and `RERANK_MIN_SCORE` at the edge of the grid, so they are not applied as defaults. A plain-language summary is in the README, section "Retrieval evaluation". Regenerating this file removes this note.

120 questions on 5 PDFs, all standalone. An answerable question is a hit if at least one of the top N chunks after reranking is in a gold section or one of its subsections; an unanswerable question is correct if the system answers "not found". Thresholds are cross-validated leave-one-PDF-out. Details: `docs/design/evaluation-metrics.md`.

## Main table: the top N chunks after reranking

| PDF | Hit rate (answerable) | Refused (unanswerable) | Context tokens | Chunks per section |
|---|---|---|---|---|
| All | 100/100 (96-100%) | 6/20 (15-52%) | 3616 | - |
| A-EW_290_Windthesen_WEB.pdf | 20/20 (84-100%) | 0/4 (0-49%) | 3602 | 1.1 |
| GenAIInUnternehmen.pdf | 20/20 (84-100%) | 2/4 (15-85%) | 4136 | 1.1 |
| NIST.CSWP.29.pdf | 20/20 (84-100%) | 0/4 (0-49%) | 4539 | 1.2 |
| PolarBearHandbookforArcticGuides2026.pdf | 20/20 (84-100%) | 1/4 (5-70%) | 2987 | 1.0 |
| cfpb_your-home-loan-toolkit.pdf | 20/20 (84-100%) | 3/4 (30-95%) | 2723 | 1.0 |

Refusal precision 6/6 (61-100%): of all "not found" answers, how many were for an unanswerable question (the rest are answerable questions that were wrongly refused).

Retrieval latency per question (without the selection call): mean 77.9 s, p95 112.2 s.

## Tuning

Tuned on the rerank stage (top N, no section selection), all 120 questions. A setting scores the number of correct questions: hits on the answerable ones plus refusals of the unanswerable ones. Settings within 1% of the questions of the best count as equally good; the pick is the middle of them, not the single best value.

Pooled pick over all questions (the default to put in `env/config.py`): `SIMILARITY_CUTOFF` 0.3, `RERANK_MIN_SCORE` 0.5, `TOP_N` 5.

**Cutoff and minimum rerank score**, correct questions (`TOP_N` 5):

| RERANK_MIN_SCORE \ SIMILARITY_CUTOFF | 0.3 | 0.4 | 0.5 | 0.6 |
|---|---|---|---|---|
| 0.01 | 101/120 (77-90%) | 101/120 (77-90%) | 99/120 (75-88%) | 87/120 (64-80%) |
| 0.03 | 101/120 (77-90%) | 101/120 (77-90%) | 99/120 (75-88%) | 88/120 (65-80%) |
| 0.1 | 102/120 (78-90%) | 103/120 (78-91%) | 100/120 (76-89%) | 89/120 (66-81%) |
| 0.3 | 104/120 (79-92%) | 104/120 (79-92%) | 102/120 (78-90%) | 90/120 (67-82%) |
| 0.5 | 106/120 (81-93%) | 106/120 (81-93%) | 102/120 (78-90%) | 91/120 (67-83%) |

**TOP_N** (cutoff 0.3, minimum score 0.5):

| TOP_N | Hit rate (answerable) | Refused (unanswerable) |
|---|---|---|
| 3 | 99/100 (95-100%) | 6/20 (15-52%) |
| 5 | 100/100 (96-100%) | 6/20 (15-52%) |
| 8 | 100/100 (96-100%) | 6/20 (15-52%) |

**Leave-one-PDF-out picks** (tuned on the other PDFs; the main table uses these for the held-out PDF):

| Held-out PDF | SIMILARITY_CUTOFF | RERANK_MIN_SCORE | TOP_N |
|---|---|---|---|
| A-EW_290_Windthesen_WEB.pdf | 0.3 | 0.5 | 5 |
| GenAIInUnternehmen.pdf | 0.3 | 0.5 | 5 |
| NIST.CSWP.29.pdf | 0.3 | 0.5 | 5 |
| PolarBearHandbookforArcticGuides2026.pdf | 0.3 | 0.5 | 5 |
| cfpb_your-home-loan-toolkit.pdf | 0.3 | 0.5 | 5 |

## Failures

- **cfpb-22**: wanted refusal. Got: cfpb_your-home-loan-toolkit.pdf > Choosing the best mortgage for you > <sup>RESEARCH STARTER</sup> > 5 . Understand the trade-off between points and interest rate; cfpb_your-home-loan-toolkit.pdf > Your closing > <sup>RESEARCH STARTER</sup> > What is your Closing Disclosure?; cfpb_your-home-loan-toolkit.pdf > Your closing > <sup>RESEARCH STARTER</sup> > Additional Information About This Loan; cfpb_your-home-loan-toolkit.pdf > Your closing > <sup>RESEARCH STARTER</sup> > Escrow; cfpb_your-home-loan-toolkit.pdf > Choosing the best mortgage for you > <sup>RESEARCH STARTER</sup> > 6 . Shop with several lenders
- **genai-21**: wanted refusal. Got: GenAIInUnternehmen.pdf > Generative KI und KI-Agenten in Unternehmen Vom Assistenten zum Akteur > 2.  Nutzungsmöglichkeiten von generativer KI und KI-Agenten > TALK – ein LLM-Projekt zur Effizienzsteigerung in der Instandhaltung (Infineon); GenAIInUnternehmen.pdf > Generative KI und KI-Agenten in Unternehmen Vom Assistenten zum Akteur > Literatur; GenAIInUnternehmen.pdf > Generative KI und KI-Agenten in Unternehmen Vom Assistenten zum Akteur > Literatur; A-EW_290_Windthesen_WEB.pdf > Inhalt > Einleitung > Auktionen in Deutschland; GenAIInUnternehmen.pdf > Generative KI und KI-Agenten in Unternehmen Vom Assistenten zum Akteur > Literatur
- **genai-22**: wanted refusal. Got: GenAIInUnternehmen.pdf > Generative KI und KI-Agenten in Unternehmen Vom Assistenten zum Akteur > 3.  Welche Veränderungen bringen <u>generative KI und KI-Agenten mit sich?</u> > human+AI: working alongsAIde (Schaeffler AG); GenAIInUnternehmen.pdf > Generative KI und KI-Agenten in Unternehmen Vom Assistenten zum Akteur > 3.  Welche Veränderungen bringen <u>generative KI und KI-Agenten mit sich?</u> > 3.1 Veränderte Interaktionsformen > Kommunikation; GenAIInUnternehmen.pdf > Generative KI und KI-Agenten in Unternehmen Vom Assistenten zum Akteur > Literatur; GenAIInUnternehmen.pdf > Generative KI und KI-Agenten in Unternehmen Vom Assistenten zum Akteur > 1. Einleitung > Implikationen für die Arbeitswelt; GenAIInUnternehmen.pdf > Generative KI und KI-Agenten in Unternehmen Vom Assistenten zum Akteur > 3.  Welche Veränderungen bringen <u>generative KI und KI-Agenten mit sich?</u> > 3.1 Veränderte Interaktionsformen
- **nist-21**: wanted refusal. Got: NIST.CSWP.29.pdf > <mark>The NIST Cybersecurity Framework (CSF) 2.0</mark> > 2. Introduction to the CSF Core; NIST.CSWP.29.pdf > <mark>The NIST Cybersecurity Framework (CSF) 2.0</mark> > 5.2. Improving Integration with Other Risk Management Programs; NIST.CSWP.29.pdf > <mark>The NIST Cybersecurity Framework (CSF) 2.0</mark> > Appendix A. CSF Core; NIST.CSWP.29.pdf > <mark>The NIST Cybersecurity Framework (CSF) 2.0</mark> > Appendix A. CSF Core; NIST.CSWP.29.pdf > <mark>The NIST Cybersecurity Framework (CSF) 2.0</mark> > 5.2. Improving Integration with Other Risk Management Programs
- **nist-22**: wanted refusal. Got: NIST.CSWP.29.pdf > <mark>The NIST Cybersecurity Framework (CSF) 2.0</mark> > 1. Cybersecurity Framework (CSF) Overview; NIST.CSWP.29.pdf > <mark>The NIST Cybersecurity Framework (CSF) 2.0</mark> > Preface; NIST.CSWP.29.pdf > <mark>The NIST Cybersecurity Framework (CSF) 2.0</mark> > 5.2. Improving Integration with Other Risk Management Programs; NIST.CSWP.29.pdf > <mark>The NIST Cybersecurity Framework (CSF) 2.0</mark> > Appendix A. CSF Core; NIST.CSWP.29.pdf > <mark>The NIST Cybersecurity Framework (CSF) 2.0</mark> > 2. Introduction to the CSF Core
- **nist-23**: wanted refusal. Got: NIST.CSWP.29.pdf > <mark>The NIST Cybersecurity Framework (CSF) 2.0</mark> > 1. Cybersecurity Framework (CSF) Overview; NIST.CSWP.29.pdf > <mark>The NIST Cybersecurity Framework (CSF) 2.0</mark> > Preface; NIST.CSWP.29.pdf > <mark>The NIST Cybersecurity Framework (CSF) 2.0</mark> > Appendix A. CSF Core; NIST.CSWP.29.pdf > <mark>The NIST Cybersecurity Framework (CSF) 2.0</mark> > 2. Introduction to the CSF Core; NIST.CSWP.29.pdf > <mark>The NIST Cybersecurity Framework (CSF) 2.0</mark> > 4. Introduction to Online Resources That Supplement the CSF
- **nist-24**: wanted refusal. Got: NIST.CSWP.29.pdf > <mark>The NIST Cybersecurity Framework (CSF) 2.0</mark> > 1. Cybersecurity Framework (CSF) Overview; NIST.CSWP.29.pdf > <mark>The NIST Cybersecurity Framework (CSF) 2.0</mark> > Appendix A. CSF Core; NIST.CSWP.29.pdf > <mark>The NIST Cybersecurity Framework (CSF) 2.0</mark> > 5.2. Improving Integration with Other Risk Management Programs; NIST.CSWP.29.pdf > <mark>The NIST Cybersecurity Framework (CSF) 2.0</mark> > 4. Introduction to Online Resources That Supplement the CSF; NIST.CSWP.29.pdf > <mark>The NIST Cybersecurity Framework (CSF) 2.0</mark> > 2. Introduction to the CSF Core
- **polarbear-21**: wanted refusal. Got: PolarBearHandbookforArcticGuides2026.pdf > Polar Bear Handbook for Arctic Guides > Polar bear populations > Western Hudson Bay (including Churchill) > Challenges:; PolarBearHandbookforArcticGuides2026.pdf > Polar Bear Handbook for Arctic Guides > Polar Bear Facts and Figures > From Brown to White; PolarBearHandbookforArcticGuides2026.pdf > Polar Bear Handbook for Arctic Guides > Living with Polar Bears; PolarBearHandbookforArcticGuides2026.pdf > Polar Bear Handbook for Arctic Guides > Threats to Polar Bears > Climate Change > Trophic mismatch; PolarBearHandbookforArcticGuides2026.pdf > Polar Bear Handbook for Arctic Guides > Executive Summary
- **polarbear-23**: wanted refusal. Got: PolarBearHandbookforArcticGuides2026.pdf > Polar Bear Handbook for Arctic Guides > Living with Polar Bears; PolarBearHandbookforArcticGuides2026.pdf > Polar Bear Handbook for Arctic Guides > Polar bear populations > Western Hudson Bay (including Churchill) > What makes this population different:; PolarBearHandbookforArcticGuides2026.pdf > Polar Bear Handbook for Arctic Guides > Executive Summary; PolarBearHandbookforArcticGuides2026.pdf > Polar Bear Handbook for Arctic Guides > Sea ice > Seasonal Sea Ice Ecoregion; PolarBearHandbookforArcticGuides2026.pdf > Polar Bear Handbook for Arctic Guides > Threats to Polar Bears > Climate Change > Trophic mismatch
- **polarbear-24**: wanted refusal. Got: PolarBearHandbookforArcticGuides2026.pdf > Polar Bear Handbook for Arctic Guides > Polar bear populations; PolarBearHandbookforArcticGuides2026.pdf > Polar Bear Handbook for Arctic Guides > Threats to Polar Bears > Climate Change > Trophic mismatch; PolarBearHandbookforArcticGuides2026.pdf > Polar Bear Handbook for Arctic Guides > Living with Polar Bears; PolarBearHandbookforArcticGuides2026.pdf > Polar Bear Handbook for Arctic Guides > Executive Summary; PolarBearHandbookforArcticGuides2026.pdf > Polar Bear Handbook for Arctic Guides > Threats to Polar Bears > Overhunting
- **windthesen-21**: wanted refusal. Got: A-EW_290_Windthesen_WEB.pdf > Vorwort > Ergebnisse auf einen Blick:; A-EW_290_Windthesen_WEB.pdf > Inhalt > Einleitung > Die Herausforderung: Die Windausbaukrise beenden; A-EW_290_Windthesen_WEB.pdf > Inhalt > Einleitung > Rückstau auflösen, Zubau-Dynamik auslösen und auf hohem Niveau halten > Maßnahmenpaket nach Wirkungszeiträumen auf den Windenergie-an-Land-Zubau; A-EW_290_Windthesen_WEB.pdf > Inhalt > A. 2024: Den Rückstau auflösen; A-EW_290_Windthesen_WEB.pdf > Inhalt > Fazit
- **windthesen-22**: wanted refusal. Got: A-EW_290_Windthesen_WEB.pdf > Inhalt > A. 2024: Den Rückstau auflösen > 2. Befristete Aussetzung von Pönalen > Maßnahme; A-EW_290_Windthesen_WEB.pdf > Inhalt > Einleitung > Rückstau auflösen, Zubau-Dynamik auslösen und auf hohem Niveau halten; A-EW_290_Windthesen_WEB.pdf > Inhalt; A-EW_290_Windthesen_WEB.pdf > Inhalt > A. 2024: Den Rückstau auflösen > 3. Begrenzung der Pachthöhe von Windflächen; A-EW_290_Windthesen_WEB.pdf > Inhalt > C. Ab 2026: Zubauraten auf hohem Niveau stabilisieren > 13. Genehmigungen von Typ- Variantenclustern > Maßnahme
- **windthesen-23**: wanted refusal. Got: A-EW_290_Windthesen_WEB.pdf > Inhalt > B.  Bis 2026: Hochlauf des Zubaus > 8. Nutzung unkonventioneller Flächen für Windenergieanlagen > Maßnahme; A-EW_290_Windthesen_WEB.pdf > Inhalt > Einleitung > Rückstau auflösen, Zubau-Dynamik auslösen und auf hohem Niveau halten; A-EW_290_Windthesen_WEB.pdf > Inhalt > Einleitung > Auktionen in Deutschland; A-EW_290_Windthesen_WEB.pdf > Inhalt > B.  Bis 2026: Hochlauf des Zubaus > 8. Nutzung unkonventioneller Flächen für Windenergieanlagen > Maßnahme; A-EW_290_Windthesen_WEB.pdf > Inhalt > Einleitung > Auktionen in Deutschland
- **windthesen-24**: wanted refusal. Got: A-EW_290_Windthesen_WEB.pdf > Inhalt > B.  Bis 2026: Hochlauf des Zubaus > 6. Länderöffnungsklausel für Repowering-Projekte abschaffen; A-EW_290_Windthesen_WEB.pdf > Literaturverzeichnis > Fachagentur Windenergie an Land (2023):; A-EW_290_Windthesen_WEB.pdf > Inhalt > A. 2024: Den Rückstau auflösen; A-EW_290_Windthesen_WEB.pdf > Inhalt > C. Ab 2026: Zubauraten auf hohem Niveau stabilisieren > 13. Genehmigungen von Typ- Variantenclustern; A-EW_290_Windthesen_WEB.pdf > Inhalt > C. Ab 2026: Zubauraten auf hohem Niveau stabilisieren > 13. Genehmigungen von Typ- Variantenclustern > Maßnahme

## How much to trust the numbers

The questions are a sample, so every rate is an estimate: at 50% the interval is about ±10 points for the 100 answerable questions and ±20 points for the 20 unanswerable ones, and wider still for one PDF. Questions from the same PDF resemble each other, so read the per-PDF rows as indications of where retrieval fails. A hit means one right chunk was in the context, not that the context was complete. The context is scored after reranking, before section selection: selection only adds chunks from sections the top N already hit, so it cannot change a hit or a refusal, but the token counts above leave out the chunks it adds. Not measured: follow-up questions (the rewrite step) and questions that need two documents. **The generated answers are not evaluated yet** (correctness, completeness, faithfulness, citation validity); finding the right source is necessary for a good answer but not sufficient. Evaluating the answers is the next step.
