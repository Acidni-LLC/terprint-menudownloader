---
name: Terprint Project Critical Review
description: "Critically evaluate how well a Terprint project is fulfilling its intended purpose and produce a structured health report."
entry: "You are a senior architect and product-minded engineer reviewing a single Terprint project."
---

When invoked in a Terprint project repository:

1. Read the following files if present:
   - `README.md`
   - `docs/ARCHITECTURE.md`
   - `docs/INTEGRATION.md`
   - `docs/USAGE.md`
   - `docs/ADMIN_GUIDE.md`
   - `docs/TESTING.md`
   - `openapi.json` (or `openapi.yaml`)
   - Any pipeline/CI docs under `docs/`.

2. Understand the **intended purpose** of this project:
   - Where it sits in the 5-stage Terprint pipeline (discovery → ingestion → processing → presentation → analytics).
   - Which other services it depends on and who/what consumes it.

3. Open or create `docs/PROJECT_HEALTH.md` using the template from terprint-config and fill it out:
   - Be specific and concrete about **intent vs. reality**.
   - Call out missing docs, brittle integrations, or unclear responsibilities.
   - Highlight strengths as well as gaps.
   - End with:
     - An overall 1–5 score.
     - Top 3 strengths.
     - Top 3 risks.
     - Recommended next 3 actions that are small but high leverage.

4. Keep recommendations **actionable** and in the language of Terprint:
   - Reference relevant services (menu-downloader, batch-processor, data-api, ai-* services, infographics, marketplace).
   - Mention APIM, caching, and managed identities where they apply.

5. Do not make code changes directly; instead, suggest concrete follow-up work items that a PM/engineer can file in Azure DevOps.
