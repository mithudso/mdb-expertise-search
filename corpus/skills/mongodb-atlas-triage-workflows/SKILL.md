---
name: mongodb-atlas-triage-workflows
description: >-
  Expert diagnosis, architecture, and operation of Atlas Triage Workflows in MongoDB clusters.
  TRIGGER: 'Atlas Triage Workflows', 'atlas-triage-workflows', 'troubleshoot atlas triage workflows', 'diagnose atlas triage workflows'.
  SKIP: unrelated non-MongoDB operational topics.
version: 1.0.0
updated: 2026-10-05
category: database
tags: [mongodb, database, performance, diagnostics, atlas-triage-workflows]
keywords:
  - atlas triage workflows
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
  - "Diagnosing or inspecting Atlas Triage Workflows issues"
  - "Evaluating cluster performance related to Atlas Triage Workflows"
  - "Tuning MongoDB configurations for Atlas Triage Workflows"
whenNotToUse:
  - "Working on relational SQL database optimization"
  - "Writing general frontend UI components"
---

# Atlas Triage Workflows

## Overview
Systematic triage playbooks for MongoDB Atlas incidents including CPU spikes, memory pressure, disk IOPS throttles, and automatic election recovery.

## Core Concepts & Mechanics
- **Claim**: Atlas Real-Time Performance Panel correlates normalized CPU, system memory, disk IOPS utilization, and query shapes within 1-second metric resolution. (Confidence: `high`)

## Methodology & Operational Patterns
- **Pattern**: Disk IOPS throttling in AWS/Azure/GCP cloud environments manifests as sudden high execution latency accompanied by queuing WiredTiger disk checkpoints.
- **Pattern**: In primary failover scenarios, verify Atlas election log lines to determine if the election was initiated by stepdown, heartbeat timeout, or out-of-memory kill.

## Anti-Patterns & Pitfalls
- **Caution**: Scaling cluster instance size (e.g. M30 to M50) as a first response to unindexed query spikes without verifying ESR indexing wastes cloud budget and leaves bottleneck queries unoptimized.

## Troubleshooting & Remediation
- **Diagnostic**: Symptom: High memory usage alert (>90%). Cause: WiredTiger cache (50% RAM) plus connection overhead (1MB per thread) plus sorting buffers. Fix: Scale RAM or tune maxConns and allowDiskUse.

## Authoritative References
- [Atlas Cluster Metrics Documentation](https://www.mongodb.com/docs/atlas/monitor-cluster-metrics/) (`docs`)
- [Atlas Performance Advisor](https://www.mongodb.com/docs/atlas/performance-advisor/) (`docs`)
- [Atlas Cluster Architecture and Sizing](https://www.mongodb.com/docs/atlas/cluster-sizing/) (`docs`)
- [Atlas Replica Set State Reference](https://www.mongodb.com/docs/atlas/reference/replica-states/) (`docs`)
