# Vercel application boundary
Allowed: dashboards, research/copilot, proposal review, approval/rejection, authenticated BFF/read APIs, realtime subscriptions.
Forbidden: direct exchange order submission, long-running polling, authoritative risk decisions, mutable strategy state, durable execution state held only in serverless memory, client-exposed secrets.
