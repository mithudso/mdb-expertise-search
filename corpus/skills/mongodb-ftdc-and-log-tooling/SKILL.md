---
name: mongodb-ftdc-and-log-tooling
description: >-
  Expert diagnosis, architecture, and operation of FTDC and Log Tooling in MongoDB clusters.
  TRIGGER: 'FTDC and Log Tooling', 'ftdc-and-log-tooling', 'troubleshoot ftdc and log tooling', 'diagnose ftdc and log tooling'.
  SKIP: unrelated non-MongoDB operational topics.
version: 1.0.0
updated: 2026-10-05
category: database
tags: [mongodb, database, performance, diagnostics, ftdc-and-log-tooling]
keywords:
  - ftdc and log tooling
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
  - "Diagnosing or inspecting FTDC and Log Tooling issues"
  - "Evaluating cluster performance related to FTDC and Log Tooling"
  - "Tuning MongoDB configurations for FTDC and Log Tooling"
whenNotToUse:
  - "Working on relational SQL database optimization"
  - "Writing general frontend UI components"
---

# FTDC and Log Tooling

## Overview
Full-Time Diagnostic Data Capture (FTDC) architecture and log parsing utilities (bsondump, mtools, ftdc-tools) for microsecond metric inspection in MongoDB.

## Core Concepts & Mechanics
- **Claim**: FTDC captures periodic serverStatus, collStats, and system resource samples into zlib/snappy compressed BSON chunk files inside the diagnostic.data directory. (Confidence: `high`)
- **Claim**: FTDC samples are recorded at 1-second intervals by default; metric deltas are run-length encoded across chunk arrays to maintain a compact footprint under 200MB. (Confidence: `high`)

## Methodology & Operational Patterns
- **Pattern**: Extracting serverStatus.wiredTiger.concurrentTransactions reveals read and write ticket exhaustion where available tickets drop to zero under burst workloads.

## Anti-Patterns & Pitfalls
- **Caution**: Attempting to parse multi-gigabyte raw FTDC folders with text-based tools without decompressing chunk headers causes corrupt metric sequence extraction.

## Troubleshooting & Remediation
- **Diagnostic**: Symptom: FTDC files consuming all root partition space. Cause: diagnosticDataCollectionDirectorySizeMB set too high on constrained storage. Fix: Set lower storage cap via setParameter.

## Authoritative References
- [MongoDB Parameters Reference](https://www.mongodb.com/docs/manual/reference/parameters/) (`docs`)
- [MongoDB FTDC Utils Library](https://github.com/mongodb/ftdc-utils) (`repo`)
- [WiredTiger Internals Documentation](https://www.mongodb.com/docs/manual/core/wiredtiger-storage-engine/) (`docs`)
- [bsondump Utility Reference](https://www.mongodb.com/docs/manual/reference/program/bsondump/) (`docs`)
