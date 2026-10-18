---
name: mongodb-ts-diag-and-diagnostic-workflows
description: >-
  Expert diagnosis, architecture, and operation of ts-diag and Diagnostic Workflows in MongoDB clusters.
  TRIGGER: 'ts-diag and Diagnostic Workflows', 'ts-diag-and-diagnostic-workflows', 'troubleshoot ts-diag and diagnostic workflows', 'diagnose ts-diag and diagnostic workflows'.
  SKIP: unrelated non-MongoDB operational topics.
version: 1.0.0
updated: 2026-10-05
category: database
tags: [mongodb, database, performance, diagnostics, ts-diag-and-diagnostic-workflows]
keywords:
  - ts-diag and diagnostic workflows
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
  - "Diagnosing or inspecting ts-diag and Diagnostic Workflows issues"
  - "Evaluating cluster performance related to ts-diag and Diagnostic Workflows"
  - "Tuning MongoDB configurations for ts-diag and Diagnostic Workflows"
whenNotToUse:
  - "Working on relational SQL database optimization"
  - "Writing general frontend UI components"
---

# ts-diag and Diagnostic Workflows

## Overview
Standardized MongoDB diagnostic triage workflow utilizing ts-diag scripts to collect cluster topology, hardware utilization, system logs, and FTDC archives into structured diagnostic bundles.

## Core Concepts & Mechanics
- **Claim**: ts-diag aggregates host-level metrics, rs.status(), rs.conf(), sh.status(), and FTDC chunks into a non-destructive compressed archive for offline analysis. (Confidence: `high`)

## Methodology & Operational Patterns
- **Pattern**: Diagnostic workflows must isolate whether latency regressions stem from WiredTiger cache exhaustion, ticket queuing, or unindexed collection scans before topology interventions.
- **Pattern**: In replica sets, ts-diag validates replication lag against the primary's oplog window size to prevent secondary sync failure during network partitions.

## Anti-Patterns & Pitfalls
- **Caution**: Running collection-heavy commands like db.collection.stats() during high lock contention can exacerbate read/write ticket stalls.

## Troubleshooting & Remediation
- **Diagnostic**: Symptom: High network wait times with low CPU utilization. Cause: Socket queue backlog or connection pool exhaustion. Fix: Tune maxPoolSize and TCP keepalive.

## Authoritative References
- [MongoDB Support Tools Repository](https://github.com/mongodb/support-tools) (`repo`)
- [MongoDB Monitoring Reference](https://www.mongodb.com/docs/manual/administration/monitoring/) (`docs`)
- [WiredTiger Storage Engine Internals](https://www.mongodb.com/docs/manual/core/wiredtiger-storage-engine/) (`docs`)
- [MongoDB collStats Command Reference](https://www.mongodb.com/docs/manual/reference/command/collStats/) (`docs`)
