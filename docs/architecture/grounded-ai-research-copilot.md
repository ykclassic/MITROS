# Phase 15 — Grounded AI Research Copilot

The copilot is an evidence interface over the deterministic research platform, not a second research engine.

## Grounding contract

Every factual research answer must be traceable to supplied, checksummed research artifacts. With no verified evidence, the copilot fails closed and does not fabricate a result.

## AI boundary

A future LLM adapter may summarize or explain grounded evidence, but it must not become an authoritative market-data source. The model cannot alter research artifacts, risk limits, approval state, execution state, or venue state.

The deterministic grounding layer is implemented first so an AI provider can be added behind a narrow interface without weakening the safety boundary.
