# Terprint Quality-of-Solution Review Template

> Copy this file to each project as `docs/QUALITY_REVIEW.md`.
>
> **To have Copilot generate this report for you in a project:**
> 1. Open the project in VS Code.
> 2. Open `docs/QUALITY_REVIEW.md`.
> 3. In Copilot Chat, run this instruction:
>    **"Using this repository as context, fully populate docs/QUALITY_REVIEW.md following its template. Analyze architecture, code quality, security, reliability/observability, testing, performance, docs, and risks, and write your answer as updated markdown for that file."**
> 4. Review and tweak the AI-generated content, then save.

---

## 1. Review Summary

- **Project name:**
- **Repository path:**
- **Review date:**
- **Reviewer(s):**
- **Scope of review:** (e.g., API surface, data pipeline, marketplace flow)
- **Overall rating (1–5):**
- **Executive summary (3–5 bullets):**
  - 
  - 
  - 

## 2. Architecture & Design

- **High-level overview:**
  - What does this component do in the Terprint ecosystem?
  - Key responsibilities and boundaries.
- **Key dependencies:** (other Terprint services, Azure resources, external APIs)
- **Topology & data flow:**
  - Request/response paths (through APIM where applicable).
  - Batch flows (e.g., menu download → batch processor → data API).
- **Design quality:**
  - Clear separation of concerns? (UI, API, domain, infrastructure)
  - Use of patterns (e.g., adapters for dispensary APIs, ETL for data processing).
- **Risks & smells:**
  - Tight coupling or circular dependencies.
  - Hidden or undocumented side effects.

**Architecture verdict:** (Strong / Adequate / Needs Refactor)  
**Key architecture actions:**
- 
- 

## 3. Code Quality & Maintainability

- **Structure & organization:**
  - Clear folder layout and module boundaries?
  - Alignment with language/framework standards (Python, .NET, TypeScript, etc.)
- **Readability:**
  - Descriptive naming, small functions, clear responsibilities.
  - Complexity hotspots (large methods, deeply nested logic).
- **Reusability & duplication:**
  - Common patterns extracted into shared utilities?
  - Obvious duplication that should move to terprint-config / shared libs.
- **Error handling:**
  - Consistent, contextual logging.
  - Graceful handling of dispensary/API failures and timeouts.

**Code-quality verdict:** (Strong / Adequate / Needs Refactor)  
**Key code-quality actions:**
- 
- 

## 4. Security & Compliance

- **Authentication & authorization:**
  - Correct use of Entra ID / managed identities.
  - No function keys used for app-to-app calls (except documented health check exceptions).
- **Secrets & configuration:**
  - All secrets in Key Vault; no secrets in code or config files.
- **Input validation & output encoding:**
  - Validation on external inputs (dispensary APIs, webhooks, user inputs).
  - Protection against injection and XSS in any user-facing paths.
- **OWASP-related concerns:**
  - Any findings related to common OWASP Top 10 categories.

**Security verdict:** (Strong / Adequate / Needs Attention)  
**Key security actions:**
- 
- 

## 5. Reliability, Observability & Operations

- **Logging:**
  - Structured, contextual logs (correlation IDs, request IDs).
  - No noisy or sensitive logs.
- **Metrics & traces:**
  - Application Insights/Log Analytics configured and used.
  - Key business and technical metrics captured (success/failure rates, latency, queue depths).
- **Resilience:**
  - Retries, circuit breakers, and timeouts where appropriate.
  - Graceful degradation strategies.
- **Operations:**
  - Runbooks or operational docs available.
  - Health endpoints implemented and monitored.
  - Containerization and hosting model documented (Function App, App Service, Static Web App, etc.).
- **APIM, caching & container standards:**
  - All service-to-service calls go through APIM (no direct function URLs), or documented exceptions.
  - Caching behavior clear (Redis vs in-memory, TTLs, cache-aside pattern) and aligned with shared cache config.
  - Dockerfile and .dockerignore present and maintained; `/api/health` (or equivalent) exposed for health checks.

**Ops/observability verdict:** (Strong / Adequate / Needs Attention)  
**Key ops/observability actions:**
- 
- 

## 6. Testing & Quality Assurance

- **Test coverage:**
  - Unit tests present and meaningful.
  - Integration/E2E tests for critical flows.
- **Test quality:**
  - Clear, deterministic, and fast tests.
  - Good coverage of error and edge cases (e.g., dispensary API changes, malformed COA files).
- **Pyramid balance:**
  - Reasonable ratio of unit vs integration vs E2E tests.

- **Pipeline & DORA signals:**
  - CI pipeline configured and green (build + tests) for this component.
  - Rough deployment frequency and lead time for typical changes.
  - Any known change-failure patterns or rollback history.
  - How quickly issues are usually detected and recovered (MTTR indicators, dashboards, alerts).

**Testing verdict:** (Strong / Adequate / Gaps)  
**Key testing actions:**
- 
- 

## 7. Performance & Scalability

- **Hot paths & bottlenecks:**
  - Known or observed slow operations (large JSON parsing, COA extraction, heavy queries).
- **Resource usage:**
  - Efficient handling of memory and I/O for large payloads.
- **Scalability:**
  - Suitability for load patterns (batch vs real-time; Azure Functions scaling behavior).

**Performance verdict:** (Strong / Adequate / Needs Optimization)  
**Key performance actions:**
- 
- 

## 8. Documentation & Developer Experience

- **Required docs present:**
  - README, ARCHITECTURE, INTEGRATION, USAGE, openapi.json (where applicable).
- **Accuracy & freshness:**
  - Docs match the current implementation and deployment model.
- **Developer experience:**
  - Clear local setup, `func host start` / `dotnet` / `npm` instructions.
  - CI/CD behavior documented (which pipeline, promotion flow).

**Docs/dev-experience verdict:** (Strong / Adequate / Needs Work)  
**Key docs/dev-experience actions:**
- 
- 

## 9. Risk Register

List the top risks discovered in this review.

| # | Risk description | Impact | Likelihood | Mitigation / Notes |
|---|------------------|--------|-----------|---------------------|
| 1 |                  | High/Med/Low | High/Med/Low |                     |
| 2 |                  |            |             |                     |
| 3 |                  |            |             |                     |

## 10. Action Items & Owners

Summarize concrete follow-ups.

| # | Area | Action item | Priority | Owner | Target date | Status |
|---|------|-------------|----------|-------|-------------|--------|
| 1 |      |             | P0/P1/P2 |       |             |        |
| 2 |      |             |          |       |             |        |
| 3 |      |             |          |       |             |        |

## 11. Review Notes

Free-form notes, context, and links (work items, dashboards, diagrams):

- 
- 
- 
