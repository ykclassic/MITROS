# Provenance requirements

Every authoritative observation, feature, signal, risk decision, proposal, approval, order, execution and outcome must be traceable.

Minimum: source/provider, source version, venue/instrument/timeframe, provider observation timestamp, receipt timestamp, request/correlation/causation IDs, schema version, strategy/model/risk version, reproducibility reference or checksum, human actor/time for approval, venue order/execution IDs, immutable audit linkage.

Verified market state is append-only. Derived records reference inputs. AI text is evidence-linked and cannot mutate authoritative market state. Execution requires approval plus idempotency. Unknown execution state must reconcile before resubmission.
