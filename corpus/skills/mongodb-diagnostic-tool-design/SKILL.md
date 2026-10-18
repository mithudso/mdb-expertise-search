---
name: mongodb-diagnostic-tool-design
description: >-
  Expert diagnosis, architecture, and operation of Diagnostic Tool Design in MongoDB clusters.
  TRIGGER: 'Diagnostic Tool Design', 'diagnostic-tool-design', 'troubleshoot diagnostic tool design', 'diagnose diagnostic tool design'.
  SKIP: unrelated non-MongoDB operational topics.
version: 1.0.0
updated: 2026-10-05
category: database
tags: [mongodb, database, performance, diagnostics, diagnostic-tool-design]
keywords:
  - diagnostic tool design
  - mongodb
  - performance
  - troubleshooting
  - diagnostic-workflows
  - database-tuning
  - telemetry
  - query-optimization
related_skills:
  - mongodb-expert
  - atlas-diagnostics-expert
  - mongodb-performance-troubleshooting-expert
whenToUse:
  - "Diagnosing or inspecting Diagnostic Tool Design issues"
  - "Evaluating cluster performance related to Diagnostic Tool Design"
  - "Tuning MongoDB configurations for Diagnostic Tool Design"
whenNotToUse:
  - "Working on relational SQL database optimization"
  - "Writing general frontend UI components"
---

# Diagnostic Tool Design

## Overview
Architecture and design principles for non-intrusive MongoDB diagnostic, telemetry capture, and log analysis tooling in high-throughput environments.

## Core Concepts & Mechanics
- **Claim**: Diagnostic tooling must avoid acquiring exclusive database locks or triggering unindexed catalogue lookups during production incidents. (Confidence: `high`)

## Methodology & Operational Patterns
- **Pattern**: Streaming BSON parsers must enforce strict chunk buffer caps to prevent diagnostic tools from inducing OOM kills on memory-constrained replica nodes.
- **Pattern**: Use query-shape normalization (stripping constants while retaining predicates) to allow deterministic error grouping without leaking sensitive field values.

## Anti-Patterns & Pitfalls
- **Caution**: Capturing full query documents without regex-based PII redaction creates severe data governance and compliance violations in diagnostic bundles.

## Troubleshooting & Remediation
- **Diagnostic**: Symptom: Diagnostic scraper causes replica set election. Cause: Scraper command timeout holding db lock. Fix: Use non-blocking serverStatus with small timeout.

## Authoritative References
- [MongoDB Support Tools Repository](https://github.com/mongodb/support-tools) (`repo`)
- [MongoDB Monitoring Guide](https://www.mongodb.com/docs/manual/administration/monitoring/) (`docs`)
- [FTDC Streaming Tools](https://github.com/mongodb/ftdc-utils) (`repo`)
- [MongoDB Compliance Architecture](https://www.mongodb.com/docs/manual/core/security-compliance/) (`docs`)
