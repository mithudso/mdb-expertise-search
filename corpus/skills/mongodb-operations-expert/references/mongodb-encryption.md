<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-operations-expert` hub.** Formerly the standalone `mongodb-encryption` skill.
> Sibling MongoDB sub-topics are now reference files under the four hubs (`mongodb-expert`,
> `mongodb-atlas-expert`, `atlas-diagnostics-expert`, `mongodb-operations-expert`) — **not**
> standalone skills. Ignore any "use the X skill" / `related_skills` / SKIP pointers below that
> name a bare `mongodb-*`/`atlas-*` skill; instead load that topic's `references/<name>.md`
> from the owning hub (see the hub's "Cross-hub map").

---

---
name: mongodb-encryption
version: "1.2.1"
updated: "2026-05-29"
origin: local
description: >
  MongoDB in-use encryption expert — CSFLE and Queryable Encryption (QE).
  TRIGGER: user needs to encrypt specific MongoDB fields, choose between CSFLE
  and QE, set up KMS providers (AWS KMS, Azure Key Vault, GCP KMS, KMIP, HashiCorp
  Vault), configure automatic vs explicit encryption, set up driver encryption
  (Node.js, Python, Java, C#), tune contention factor / sparsity / trimFactor,
  run range/equality/prefix/suffix/substring queries on encrypted fields, compact
  metadata collections, migrate an unencrypted collection to QE/CSFLE (critical:
  no updateMany/bulkWrite on QE encrypted collections), rotate DEKs, combine Atlas
  EAR with in-use encryption, configure audit logging for encrypted collections,
  or meet HIPAA / PCI-DSS / GDPR / SOC 2 compliance. Activate proactively whenever
  the user mentions PII encryption, field-level security, in-use encryption, KMS
  key management, crypt_shared, mongocryptd, KMIP, or HashiCorp Vault with MongoDB.
  SKIP: network TLS/SSL configuration (connection-level, not field-level); full-disk
  or filesystem-level encryption; application-layer encryption done entirely outside
  MongoDB drivers; Atlas Search on encrypted fields (not supported); general MongoDB
  queries or schema design without an encryption requirement (use mongodb-schema-design
  or mongodb-expert).
triggers:
  - encrypt MongoDB fields
  - CSFLE setup
  - Queryable Encryption
  - MongoDB KMS
  - field-level encryption
  - encrypted queries
  - mongocryptd
  - crypt_shared
  - DEK key rotation
  - contention factor
  - encryptedFieldsMap
  - PII encryption MongoDB
  - KMIP MongoDB
  - HashiCorp Vault MongoDB encryption
  - sparsity trimFactor QE
  - migrate unencrypted to encrypted
  - audit logging encrypted collections
  - Atlas EAR in-use encryption
  - MongoDB encryption compliance
keywords:
  - mongodb
  - encryption
  - csfle
  - queryable-encryption
  - kms
  - field-level
  - in-use-encryption
  - pii
  - hipaa
  - pci-dss
  - gdpr
  - kmip
  - hashicorp-vault
  - audit-logging
  - atlas-ear
  - byok
  - sparsity
  - trimFactor
  - encrypted-migration
when_to_use:
  - Encrypt specific fields in MongoDB documents with CSFLE or Queryable Encryption
  - Choose between CSFLE and Queryable Encryption for a new project
  - Set up AWS KMS, Azure Key Vault, GCP KMS, KMIP, or HashiCorp Vault for MongoDB
  - Configure automatic vs explicit encryption in driver code
  - Query on encrypted fields (equality, range, prefix, suffix, substring)
  - Tune contention factor, sparsity, or trimFactor for Queryable Encryption
  - Migrate an unencrypted collection to QE or CSFLE
  - Rotate DEK encryption keys after CMK rotation
  - Combine Atlas EAR with in-use encryption for defense-in-depth
  - Configure audit logging for encrypted collections
  - Meet HIPAA, PCI-DSS, GDPR, or SOC 2 with field-level encryption
when_not_to_use:
  - Network TLS/SSL configuration — connection-level, not field-level
  - Full-disk or filesystem-level encryption
  - Application-layer encryption done entirely outside MongoDB drivers
  - Atlas Search on encrypted fields — not supported
  - General MongoDB queries or schema design without an encryption requirement (use mongodb-schema-design or mongodb-expert)
  - Atlas network security, VPC peering, or private endpoints (use mongodb-atlas-expert)
related_skills:
  - mongodb-expert
  - mongodb-atlas-expert
  - security-compliance-auditor
  - mongodb-developer
  - mongodb-compliance
  - mongodb-schema-design
---

# MongoDB In-Use Encryption: CSFLE and Queryable Encryption

Expert reference for MongoDB's two in-use encryption approaches: Client-Side Field Level Encryption (CSFLE) and Queryable Encryption (QE).

## When to use this skill

Activate when the user:

- asks about encrypting specific fields in MongoDB documents
- needs to choose between CSFLE and Queryable Encryption
- wants to set up KMS providers (AWS KMS, Azure Key Vault, GCP KMS, KMIP, or HashiCorp Vault)
- asks about automatic vs explicit encryption
- needs to configure encryption schemas or encryptedFieldsMap
- asks about mongocryptd vs crypt_shared (Automatic Encryption Shared Library)
- wants to perform queries on encrypted data (equality, range, prefix, suffix, substring)
- needs to tune contention factor, sparsity, or trimFactor for Queryable Encryption
- asks about encrypted collection compaction or metadata management
- wants to migrate from CSFLE to QE, or migrate unencrypted collections to QE/CSFLE
- needs driver setup for encryption (Node.js, Python, Java, C#, Go, Mongoid)
- asks about encryption key rotation or key vault management
- needs to understand storage overhead of encrypted collections
- asks about BSON type support for encrypted fields
- wants to encrypt PII, PHI, or other regulated data in MongoDB
- asks about Atlas Encryption at Rest (EAR) vs field-level encryption or how to combine them
- needs audit logging configuration for encrypted collections
- asks about KMIP or HashiCorp Vault integration for MongoDB key management

## When NOT to use this skill

- General MongoDB queries or schema design without encryption — use mongodb-expert instead
- Network TLS/SSL configuration — connection-level, not field-level
- Application-layer encryption done entirely outside MongoDB drivers (e.g., encrypting before inserting raw bytes)
- Full-disk or filesystem-level encryption
- MongoDB Atlas Search on encrypted fields (not supported — QE/CSFLE fields cannot be indexed in Atlas Search)

## Related skills

- **mongodb-expert** -- general MongoDB query, schema, and index guidance
- **mongodb-atlas-expert** -- Atlas-specific configuration including network encryption and Atlas Search
- **security-compliance-auditor** -- broader compliance and security review beyond encryption
- **mongodb-developer** -- application development patterns with MongoDB drivers

---

## Quick Rules

1. **New project without per-tenant key isolation?** Use Queryable Encryption ([Choosing CSFLE vs QE](https://www.mongodb.com/docs/manual/core/queryable-encryption/about-qe-csfle/)).
2. **Need different DEKs per user/tenant for the same field?** Use CSFLE.
3. **Never mix CSFLE and QE in the same collection** -- they are mutually exclusive.
4. **Always use a cloud KMS in production** (AWS KMS, Azure Key Vault, GCP KMS, or KMIP). Local keys are development-only.
5. **Use crypt_shared, not mongocryptd** -- set `cryptSharedLibRequired: true`.
6. **Only set `queryType` on fields you actually query** -- each queryable field adds 2-3x metadata overhead.
7. **Compact metadata regularly** -- run `compactStructuredEncryptionData()` when ESC/ECOC exceed 1 GB.
8. **Rewrap DEKs immediately after CMK rotation** -- do not disable the old CMK version until rewrapping completes.
9. **Range queries require MongoDB 8.0+** -- equality queries are available from 6.0+.
10. **Do not use prefix/suffix/substring queries in production** -- they are public preview in 8.2 and the GA release will be incompatible.
11. **Migrating unencrypted → QE? No `updateMany` or `bulkWrite`** -- QE encrypted collections do not support multi-document write ops. Migrate one document at a time into a new collection, then rename.
12. **Use both EAR and in-use encryption** -- Atlas Encryption at Rest (EAR) protects storage files; CSFLE/QE protects field values from DBAs and operators. They are complementary, not alternatives.

## Edition Requirements

| Feature | Community Edition | Enterprise / Atlas |
|---------|------------------|--------------------|
| CSFLE explicit encryption | Yes | Yes |
| CSFLE automatic encryption | No | Yes |
| QE explicit encryption | No | Yes |
| QE automatic encryption | No | Yes |
| crypt_shared library | N/A | Required for automatic |
| mongocryptd | N/A | Legacy alternative to crypt_shared |

Community Edition users can use CSFLE with explicit `encrypt()` / `decrypt()` calls in application code. Automatic encryption (where the driver transparently encrypts/decrypts based on schemas) requires Enterprise or Atlas ([CSFLE docs](https://www.mongodb.com/docs/manual/core/csfle/), [CSFLE explicit encryption](https://www.mongodb.com/docs/manual/core/csfle/fundamentals/manual-encryption/)).

---

## Overview

MongoDB provides two complementary in-use encryption mechanisms that encrypt data on the client side before it reaches the server. Both guarantee that the server never sees plaintext values, protecting data from unauthorized access including by database administrators and cloud infrastructure operators ([MongoDB CSFLE docs](https://www.mongodb.com/docs/manual/core/csfle/), [MongoDB QE docs](https://www.mongodb.com/docs/manual/core/queryable-encryption/)).

### CSFLE (Client-Side Field Level Encryption)

Introduced in MongoDB 4.2 (automatic encryption in Enterprise/Atlas, explicit in Community). CSFLE encrypts individual fields before they leave the driver. It supports two encryption algorithms -- **deterministic** (same input always produces same ciphertext, enabling equality queries) and **randomized** (different ciphertext each time, stronger security but no querying). CSFLE is the foundational technology and remains the right choice when per-tenant or per-user key isolation is required ([CSFLE features](https://www.mongodb.com/docs/manual/core/csfle/features/), [CSFLE encryption algorithms](https://www.mongodb.com/docs/manual/core/csfle/fundamentals/encryption-algorithms/)).

### Queryable Encryption (QE)

Introduced in MongoDB 6.0 as public preview (equality queries), reaching **GA for equality queries in MongoDB 7.0** (the GA release is incompatible with the 6.0 preview — do not mix them). Range queries reached GA in MongoDB 8.0, and prefix/suffix/substring queries are in public preview in MongoDB 8.2. QE uses structured encryption based on recent academic cryptographic research, providing randomized encryption for all fields while still supporting queries. Unlike CSFLE's deterministic mode, QE never leaks whether two ciphertexts correspond to the same plaintext. QE is the recommended approach for new projects unless multi-key-per-field isolation is needed ([QE features](https://www.mongodb.com/docs/manual/core/queryable-encryption/features/), [Choosing CSFLE vs QE](https://www.mongodb.com/docs/manual/core/queryable-encryption/about-qe-csfle/)).

Both approaches use the **AES-256-CBC** encryption algorithm with **HMAC-SHA-512** authentication (AEAD) under the hood and share the same envelope encryption key management architecture ([MongoDB encryption announcement](https://www.mongodb.com/company/blog/product-release-announcements/mongodb-announces-queryable-encryption)).

---

## Core Concepts

### Envelope Encryption and Key Hierarchy

Both CSFLE and QE use a two-tier key hierarchy ([KMS providers docs](https://www.mongodb.com/docs/manual/core/queryable-encryption/fundamentals/kms-providers/)):

1. **Customer Master Key (CMK)** -- stored in a KMS provider (AWS KMS, Azure Key Vault, GCP KMS, KMIP, or a local key for development). Never leaves the KMS.
2. **Data Encryption Key (DEK)** -- generated by the driver, encrypted by the CMK, and stored as a BSON document in a dedicated **Key Vault collection** (typically `__keyVault` in the `encryption` database). The DEK is what actually encrypts field values.

The driver fetches the encrypted DEK from the Key Vault, sends it to the KMS for decryption, and uses the plaintext DEK to encrypt/decrypt field values locally. The MongoDB server never sees the plaintext DEK or the plaintext field values.

```
Application --> Driver --> KMS (decrypt DEK) --> Driver encrypts/decrypts fields
                  |                                        |
                  +--- Key Vault (encrypted DEKs) ---------+
                  |                                        |
                  +--- MongoDB Server (encrypted data) ----+
```

### KMS Provider Configuration

Each KMS provider requires specific credentials ([CSFLE KMS providers](https://www.mongodb.com/docs/v7.0/core/csfle/reference/kms-providers/), [QE KMS providers](https://www.mongodb.com/docs/manual/core/queryable-encryption/fundamentals/kms-providers/)):

**AWS KMS:**
- `accessKeyId` and `secretAccessKey` (IAM user with `kms:Encrypt` and `kms:Decrypt` permissions)
- Region and key ARN specified when creating the DEK
- Supports temporary credentials via `sessionToken` for STS/assumed roles

**Azure Key Vault:**
- `tenantId`, `clientId`, `clientSecret` (or managed identity)
- Key vault URL and key name specified when creating the DEK
- If `keyVersion` is omitted, Azure uses the latest version; after CMK rotation, you must rewrap DEKs or decryption of old DEKs fails

**GCP KMS:**
- `email` (service account) and `privateKey`
- Project, location, key ring, and key name specified when creating the DEK

**KMIP:**
- `endpoint` URL for the KMIP-compliant key server
- TLS certificate and key for authentication

**Local key (development only):**
- 96-byte base64-encoded key stored in application config
- Never use in production -- the key is visible to anyone with access to the application

### Encryption Algorithms (CSFLE)

CSFLE offers two algorithms ([CSFLE encryption algorithms](https://www.mongodb.com/docs/manual/core/csfle/fundamentals/encryption-algorithms/)):

| Algorithm | Security | Queryability | Use case |
|-----------|----------|-------------|----------|
| **Deterministic** | Good -- same plaintext always produces same ciphertext | Equality queries supported | SSN, email, account number -- fields you must query exactly |
| **Randomized** | Stronger -- same plaintext produces different ciphertext each time | No queries supported | Medical records, free-text notes -- fields that are read-only |

**Key constraint:** Deterministic encryption leaks frequency information (an attacker can tell when two documents have the same value). Queryable Encryption eliminates this leakage.

### Encryption in Queryable Encryption

QE always uses **randomized encryption** but adds cryptographic metadata structures that enable the server to evaluate queries without decrypting the data. This is achieved through three internal metadata collections created automatically alongside the encrypted collection ([QE encrypt and query](https://www.mongodb.com/docs/manual/core/queryable-encryption/fundamentals/encrypt-and-query/)):

- **ESC (Encrypted State Collection)** -- tracks unique field/value pair occurrences
- **ECOC (Encrypted Compaction Collection)** -- supports metadata compaction
- **ECC (Encrypted Counter Collection)** -- manages delete tracking (removed in MongoDB 7.0+; merged into ESC)

### Supported Query Types

| Query Type | CSFLE | QE | MongoDB Version | Status |
|------------|-------|----|-----------------|--------|
| Equality (`$eq`, `$ne`, `$in`) | Deterministic fields only | Yes | 6.0 preview / 7.0+ GA | GA |
| Range (`$gt`, `$gte`, `$lt`, `$lte`) | No | Yes | 8.0+ | GA |
| Prefix (`$startsWith`) | No | Yes | 8.2+ | Public Preview |
| Suffix (`$endsWith`) | No | Yes | 8.2+ | Public Preview |
| Substring (`$contains`) | No | Yes | 8.2+ | Public Preview |
| Unencrypted (no query type) | Randomized fields | `queryType: "none"` | All | GA |

**Warning:** The prefix, suffix, and substring query types in MongoDB 8.2 are public preview only. Do not use them in production. The GA implementation will be incompatible with the preview, requiring re-encryption ([QE limitations](https://www.mongodb.com/docs/manual/core/queryable-encryption/reference/limitations/)).

### Supported BSON Types

**CSFLE deterministic encryption** supports: `string`, `binary`, `objectId`, `boolean`, `date`, `regex`, `dbPointer`, `javascript`, `symbol`, `int`, `timestamp`, `long`, `decimal`, `minKey`, `maxKey` ([CSFLE encryption schemas](https://www.mongodb.com/docs/manual/core/csfle/reference/encryption-schemas/)).

**CSFLE randomized encryption** supports all BSON types including `object` and `array` (encrypts the entire value as a unit).

> **Encryption + AI/vector-search constraint:** an embedding vector must be stored as
> raw floats to be searchable, so you **cannot** QE/CSFLE-encrypt the vector field and
> still run `$vectorSearch` over it. Encrypt the sensitive **source/metadata** fields
> (SSN, account, name) with QE/CSFLE and leave the embedding + coarse filter keys
> queryable. Full pattern in `atlas-vector-search-pii-isolation`; embedding-leakage
> rationale in `embedding-inversion-threat-model`.

**QE equality queries** support all BSON types except: `array`, `decimal`, `double`, `object` ([QE encrypt and query](https://www.mongodb.com/docs/manual/core/queryable-encryption/fundamentals/encrypt-and-query/)).

**QE range queries** support: `int`, `long`, `double`, `decimal` (Decimal128), `date` (UTC DateTime). For `double` and `decimal`, `min` and `max` bounds are required. For `int`, `long`, and `date`, bounds are optional but strongly recommended for performance ([QE supported operations](https://www.mongodb.com/docs/manual/core/queryable-encryption/reference/supported-operations/)).

---

## Tools and Frameworks

### mongocryptd vs crypt_shared

MongoDB provides two libraries that handle the automatic encryption/decryption logic at the driver level ([mongocryptd docs](https://www.mongodb.com/docs/v7.0/core/queryable-encryption/reference/mongocryptd/)):

| Feature | mongocryptd | crypt_shared (Automatic Encryption Shared Library) |
|---------|------------|---------------------------------------------------|
| Type | Separate daemon process | Shared library loaded in-process |
| Spawning | Driver auto-spawns if not running | No separate process |
| Availability | Enterprise only | Enterprise only (bundled with MongoDB Enterprise or downloadable) |
| Performance | IPC overhead for each operation | In-process, lower latency |
| Recommendation | Legacy; still supported | **Preferred for all new deployments** |

To enforce crypt_shared and prevent fallback to mongocryptd:

```javascript
// Node.js
const client = new MongoClient(uri, {
  autoEncryption: {
    kmsProviders,
    keyVaultNamespace: 'encryption.__keyVault',
    encryptedFieldsMap,  // or schemaMap for CSFLE
    extraOptions: {
      cryptSharedLibPath: '/path/to/mongo_crypt_v1.so',
      cryptSharedLibRequired: true  // fail if crypt_shared unavailable
    }
  }
});
```

### Driver Support Matrix

All official MongoDB drivers support both CSFLE and QE. The `mongodb-client-encryption` (or equivalent) companion library is required alongside the main driver ([mongodb-client-encryption npm](https://www.npmjs.com/package/mongodb-client-encryption)):

| Driver | CSFLE Auto | CSFLE Explicit | QE Auto | QE Explicit | Companion Library |
|--------|-----------|---------------|---------|------------|-------------------|
| Node.js | Yes | Yes | Yes | Yes | `mongodb-client-encryption` |
| Python (PyMongo) | Yes | Yes | Yes | Yes | `pymongocrypt` |
| Java | Yes | Yes | Yes | Yes | Built into `mongodb-driver-sync` 4.7+ |
| C# (.NET) | Yes | Yes | Yes | Yes | `MongoDB.Libmongocrypt` |
| Go | Yes | Yes | Yes | Yes | Built into `mongo-go-driver` |
| Ruby (Mongoid) | Yes | Yes | Yes | Yes | `libmongocrypt` bindings |
| PHP | Yes | Yes | Yes | Yes | `ext-mongodb` + `mongodb/mongodb` |

### ODM/Framework Support

- **Mongoose** natively supports both QE and CSFLE with schema-level configuration ([Mongoose CSFLE docs](https://mongoosejs.com/docs/field-level-encryption.html), [Mongoose QE announcement](https://www.mongodb.com/company/blog/product-release-announcements/mongoose-now-natively-supports-qe-csfle))
- **Mongoid** (Ruby) supports automatic encryption via model-level declarations ([Mongoid encryption](https://www.mongodb.com/docs/mongoid/current/security/encryption/))
- **Spring Data MongoDB** supports CSFLE and QE through `@ExplicitEncrypted` and `@Queryable` annotations ([Spring Data MongoDB encryption](https://docs.spring.io/spring-data/mongodb/reference/mongodb/mongo-encryption.html))
- **Doctrine MongoDB ODM** supports QE through property-level annotations ([Doctrine QE](https://www.doctrine-project.org/projects/doctrine-mongodb-odm/en/2.15/cookbook/queryable-encryption.html))
- **EF Core Provider** supports QE through property configuration ([EF Core QE](https://damieng.com/blog/2025/09/22/mongodb-queryable-encryption/))

---

## Methodology

### Choosing Between CSFLE and Queryable Encryption

Use this decision tree ([Choosing CSFLE vs QE](https://www.mongodb.com/docs/manual/core/queryable-encryption/about-qe-csfle/)):

```
Start
  |
  v
Need per-user or per-tenant key isolation for the same field?
  |-- Yes --> Use CSFLE (supports different DEKs per document for same field)
  |-- No
      |
      v
      Existing application already using CSFLE?
        |-- Yes --> Stay with CSFLE unless you need range/prefix/suffix queries
        |-- No
            |
            v
            Use Queryable Encryption (recommended for new projects)
```

**You cannot use both CSFLE and QE in the same collection.** Choose one approach per collection.

### Setting Up CSFLE (Automatic Encryption)

1. **Install companion library** for your driver (e.g., `npm install mongodb-client-encryption`)
2. **Download crypt_shared** from the MongoDB Enterprise download center
3. **Configure KMS provider** with credentials
4. **Create a Data Encryption Key** using `ClientEncryption.createDataKey()`
5. **Define the JSON Schema** with encryption metadata for each field
6. **Create the MongoClient** with `autoEncryption` options including `schemaMap`

```javascript
// Node.js CSFLE setup
const { MongoClient, ClientEncryption } = require('mongodb');

// 1. KMS provider config
const kmsProviders = {
  aws: {
    accessKeyId: process.env.AWS_ACCESS_KEY_ID,
    secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY
  }
};

// 2. Create DEK
const encryption = new ClientEncryption(keyVaultClient, {
  keyVaultNamespace: 'encryption.__keyVault',
  kmsProviders
});

const dataKeyId = await encryption.createDataKey('aws', {
  masterKey: {
    key: 'arn:aws:kms:us-east-1:123456789:key/abcd-1234',
    region: 'us-east-1'
  }
});

// 3. Define schema
const schemaMap = {
  'mydb.users': {
    bsonType: 'object',
    encryptMetadata: { keyId: [dataKeyId] },
    properties: {
      ssn: {
        encrypt: {
          bsonType: 'string',
          algorithm: 'AEAD_AES_256_CBC_HMAC_SHA_512-Deterministic'
        }
      },
      medicalNotes: {
        encrypt: {
          bsonType: 'string',
          algorithm: 'AEAD_AES_256_CBC_HMAC_SHA_512-Random'
        }
      }
    }
  }
};

// 4. Create encrypted client
const client = new MongoClient(uri, {
  autoEncryption: {
    kmsProviders,
    keyVaultNamespace: 'encryption.__keyVault',
    schemaMap,
    extraOptions: {
      cryptSharedLibPath: '/path/to/mongo_crypt_v1.so',
      cryptSharedLibRequired: true
    }
  }
});
```

### Setting Up Queryable Encryption

1. **Install companion library** and crypt_shared (same as CSFLE)
2. **Configure KMS provider** with credentials
3. **Define encryptedFieldsMap** specifying fields, query types, and contention
4. **Create the encrypted collection** using `createEncryptedCollection()` (generates DEKs and metadata collections automatically)
5. **Create the MongoClient** with `autoEncryption` options including `encryptedFieldsMap`

```javascript
// Node.js Queryable Encryption setup
const { MongoClient, ClientEncryption } = require('mongodb');

const kmsProviders = {
  aws: {
    accessKeyId: process.env.AWS_ACCESS_KEY_ID,
    secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY
  }
};

const encryptedFieldsMap = {
  'mydb.patients': {
    fields: [
      {
        path: 'patientId',
        bsonType: 'string',
        queryType: 'equality',   // can query with $eq, $in
        contention: 8            // default; tune based on write concurrency
      },
      {
        path: 'age',
        bsonType: 'int',
        queryType: 'range',      // MongoDB 8.0+ -- can query with $gt, $lt, etc.
        trimFactor: 6,           // controls index precision vs storage
        contention: 0,           // low-contention for rarely concurrent writes
        rangeOptions: {
          min: 0,
          max: 150
        }
      },
      {
        path: 'diagnosis',
        bsonType: 'string'
        // No queryType = encrypted but not queryable
      }
    ]
  }
};

// Create encrypted collection (auto-generates DEKs + metadata collections)
const encryption = new ClientEncryption(client, {
  keyVaultNamespace: 'encryption.__keyVault',
  kmsProviders
});

await encryption.createEncryptedCollection(db, 'patients', {
  provider: 'aws',
  createCollectionOptions: { encryptedFields: encryptedFieldsMap['mydb.patients'] },
  masterKey: {
    key: 'arn:aws:kms:us-east-1:123456789:key/abcd-1234',
    region: 'us-east-1'
  }
});
```

```python
# Python (PyMongo) Queryable Encryption setup
from pymongo import MongoClient
from pymongo.encryption import ClientEncryption, AutoEncryptionOpts

kms_providers = {
    "aws": {
        "accessKeyId": os.environ["AWS_ACCESS_KEY_ID"],
        "secretAccessKey": os.environ["AWS_SECRET_ACCESS_KEY"],
    }
}

encrypted_fields_map = {
    "mydb.patients": {
        "fields": [
            {
                "path": "patientId",
                "bsonType": "string",
                "queryType": "equality",
                "contention": 8,
            },
            {
                "path": "age",
                "bsonType": "int",
                "queryType": "range",
                "trimFactor": 6,
                "contention": 0,
                "rangeOptions": {"min": 0, "max": 150},
            },
        ]
    }
}

auto_encryption_opts = AutoEncryptionOpts(
    kms_providers=kms_providers,
    key_vault_namespace="encryption.__keyVault",
    encrypted_fields_map=encrypted_fields_map,
    crypt_shared_lib_path="/path/to/mongo_crypt_v1.so",
    crypt_shared_lib_required=True,
)

client = MongoClient(uri, auto_encryption_opts=auto_encryption_opts)
```

### Contention Factor Tuning

The contention factor controls how many concurrent writers can update the same encrypted field/value pair without lock contention on the internal counter ([QE contention](https://www.mongodb.com/docs/manual/core/queryable-encryption/fundamentals/encrypt-and-query/)):

| Contention Value | Write Performance | Read Performance | Best For |
|-----------------|-------------------|-----------------|----------|
| 0 | Lowest (serialized) | Best (single counter) | Low-write fields, high-read fields |
| 4 | Good | Good | Moderate concurrency |
| 8 (default) | High | Good | Most workloads |
| 16+ | Highest | Lower (more partitions to scan) | High-write, low-cardinality fields |

**Formula:** Set contention to at least the number of concurrent writers (omega) expected within a 30ms window. If unknown, use the number of virtual CPU cores on the server.

**Important:** Once a field's contention factor is set during collection creation, it is immutable. To change it, you must recreate the collection.

### Metadata Compaction

Queryable Encryption's metadata collections (ESC, ECOC) grow with every insert and update. Without compaction, each field/value pair across all documents creates a metadata entry ([Encrypted collections management](https://www.mongodb.com/docs/manual/core/queryable-encryption/fundamentals/manage-collections/)):

- **When to compact:** When metadata collections exceed 1 GB, or when query performance degrades
- **How:** Run `db.collection.compactStructuredEncryptionData()` in mongosh
- **Impact:** Reduces ESC and ECOC size; merges counter partitions; must be run during a maintenance window with reduced write load
- **Example:** A collection with 1 million documents and one encrypted field has up to 1 million ESC + 1 million ECOC entries before compaction

---

## Practical Patterns

### Pattern 1: PII Protection with CSFLE

Encrypt SSN deterministically (to allow exact lookups) and other PII randomly:

```javascript
const schemaMap = {
  'app.customers': {
    bsonType: 'object',
    encryptMetadata: { keyId: [dataKeyId] },
    properties: {
      ssn: {
        encrypt: {
          bsonType: 'string',
          algorithm: 'AEAD_AES_256_CBC_HMAC_SHA_512-Deterministic'
        }
      },
      dateOfBirth: {
        encrypt: {
          bsonType: 'date',
          algorithm: 'AEAD_AES_256_CBC_HMAC_SHA_512-Random'
        }
      },
      address: {
        encrypt: {
          bsonType: 'object',
          algorithm: 'AEAD_AES_256_CBC_HMAC_SHA_512-Random'
        }
      }
    }
  }
};
```

### Pattern 2: Healthcare Data with QE Range Queries

Use QE for HIPAA-regulated data where you need range queries on encrypted numeric/date fields:

```javascript
const encryptedFieldsMap = {
  'hospital.records': {
    fields: [
      { path: 'patientId', bsonType: 'string', queryType: 'equality', contention: 8 },
      { path: 'labResult', bsonType: 'int', queryType: 'range', contention: 4,
        rangeOptions: { min: 0, max: 10000 } },
      { path: 'visitDate', bsonType: 'date', queryType: 'range', contention: 4 },
      { path: 'diagnosis', bsonType: 'string' }  // encrypted, not queryable
    ]
  }
};

// Query: find patients with lab results above threshold in a date range
const results = await collection.find({
  labResult: { $gte: 200 },
  visitDate: { $gte: new Date('2025-01-01'), $lte: new Date('2025-12-31') }
});
```

### Pattern 3: Multi-Tenant Isolation with CSFLE

When each tenant needs a separate DEK (CSFLE's key advantage over QE):

```javascript
// Create per-tenant DEKs
const tenantAKeyId = await encryption.createDataKey('aws', {
  masterKey: { key: cmkArn, region: 'us-east-1' },
  keyAltNames: ['tenant-A']
});
const tenantBKeyId = await encryption.createDataKey('aws', {
  masterKey: { key: cmkArn, region: 'us-east-1' },
  keyAltNames: ['tenant-B']
});

// Explicit encryption with tenant-specific key
const encryptedValue = await encryption.encrypt(sensitiveData, {
  keyId: tenantAKeyId,
  algorithm: 'AEAD_AES_256_CBC_HMAC_SHA_512-Random'
});
```

### Pattern 4: Key Rotation

Rotate the CMK in your KMS provider, then rewrap all DEKs to use the new CMK version:

```javascript
// Rewrap all DEKs encrypted by the old CMK
const result = await encryption.rewrapManyDataKey(
  { masterKey: { key: oldCmkArn } },  // filter: DEKs using old CMK
  {
    provider: 'aws',
    masterKey: {
      key: newCmkArn,
      region: 'us-east-1'
    }
  }
);
console.log(`Rewrapped ${result.bulkWriteResult.modifiedCount} DEKs`);
```

### Pattern 5: Server-Side Schema Enforcement

Store the encryption schema on the server to prevent unencrypted writes from misconfigured clients:

```javascript
// Create collection with server-side validator (CSFLE)
db.createCollection('secure_data', {
  validator: {
    $jsonSchema: {
      bsonType: 'object',
      properties: {
        ssn: {
          encrypt: {
            bsonType: 'string',
            algorithm: 'AEAD_AES_256_CBC_HMAC_SHA_512-Deterministic',
            keyId: [dataKeyId]
          }
        }
      }
    }
  }
});
```

---

## Anti-Patterns

### 1. Using a local master key in production
A local 96-byte key provides no security -- anyone with application access can decrypt all data. Always use a cloud KMS in production ([KMS providers](https://www.mongodb.com/docs/manual/core/queryable-encryption/fundamentals/kms-providers/)).

### 2. Encrypting everything with queryType
Every queryable encrypted field adds metadata overhead (2-3x storage for fully encrypted collections). Only set `queryType` on fields you actually need to query. Use `queryType: "none"` (or omit it) for write-only encrypted fields ([QE limitations](https://www.mongodb.com/docs/manual/core/queryable-encryption/reference/limitations/)).

### 3. Mixing CSFLE and QE in the same collection
This is not supported and will fail. If you need both approaches, use separate collections.

### 4. Deterministic encryption on low-cardinality fields
Using deterministic encryption on fields like `boolean`, `gender`, or `status` leaks the frequency distribution, enabling inference attacks. Use randomized encryption for low-cardinality fields.

### 5. Ignoring metadata compaction
Without regular compaction, ESC and ECOC metadata collections grow unboundedly, degrading query performance and consuming disk space. Schedule compaction as part of regular maintenance.

### 6. Setting contention too high for read-heavy workloads
High contention (16+) partitions the counter into many segments, which improves write throughput but forces reads to scan more partitions. For read-heavy workloads, use contention 0-4.

### 7. Forgetting to rewrap DEKs after CMK rotation
Rotating the CMK in your KMS without rewrapping DEKs leaves old DEKs encrypted under the old CMK. If the old CMK is deleted or disabled, those DEKs become permanently inaccessible. Always rewrap after rotation, especially with Azure Key Vault which defaults to the latest key version.

### 8. Using mongocryptd when crypt_shared is available
mongocryptd requires spawning a separate process (daemon management, port conflicts, startup latency). The crypt_shared library loads in-process with better performance and simpler operations. Set `cryptSharedLibRequired: true` to enforce it.

### 9. Encrypting array elements individually
Neither CSFLE nor QE supports encrypting individual elements of an array. You can only encrypt the entire array as a single unit (with randomized encryption in CSFLE, or as an unqueried field in QE).

### 10. Using prefix/suffix/substring queries in production (MongoDB 8.2)
These are public preview features. The GA implementation will be incompatible with the preview, requiring collection recreation. Do not build production features on preview query types.

---

## Troubleshooting

### "MongoServerError: not authorized" on encrypted operations
- The KMS credentials lack required permissions. For AWS KMS, the IAM user/role needs `kms:Encrypt` and `kms:Decrypt` on the CMK ARN.
- The Key Vault collection requires a unique index on `keyAltNames`. Create it: `db.getCollection('__keyVault').createIndex({ keyAltNames: 1 }, { unique: true, partialFilterExpression: { keyAltNames: { $exists: true } } })`.

### "Error: crypt_shared library not found"
- Verify `cryptSharedLibPath` points to the correct `.so`/`.dylib`/`.dll` file.
- Ensure the library version matches the driver version.
- On macOS, the library may need to be unsigned or have security exceptions.

### mongocryptd spawns unexpectedly
- Set `extraOptions.cryptSharedLibRequired: true` and `extraOptions.mongocryptdBypassSpawn: true` to prevent fallback.
- Verify crypt_shared loaded by checking driver debug logs for "Using crypt_shared library".

### Encrypted queries return no results
- **CSFLE:** Ensure the field was encrypted with deterministic (not randomized) algorithm.
- **QE:** Ensure `queryType` is set on the field in `encryptedFieldsMap`.
- Verify the query client uses the same DEK that encrypted the data.
- Check that the client's `encryptedFieldsMap` or `schemaMap` matches the collection's configuration exactly.

### Performance degradation over time
- Run `db.collection.compactStructuredEncryptionData()` to compact QE metadata.
- Check metadata collection sizes: `db.getCollection('enxcol_.collectionName.esc').stats()`.
- For QE range queries, ensure `min`/`max` bounds are set -- unbounded ranges cause larger indexes.
- Review `trimFactor` -- lower values create more precise indexes but consume more storage.

### "Cannot use CSFLE and Queryable Encryption on the same collection"
- These are mutually exclusive. Migrate the collection data to a new collection using the other approach.
- Use `mongodump` / `mongorestore` with a non-encrypting client to export plaintext, then import into the new encrypted collection.

### Storage unexpectedly large
- Each queryable encrypted field adds metadata. A collection with 5 queryable fields and 1M documents can have 5M+ metadata entries.
- Run compaction regularly.
- Consider reducing the number of queryable fields (use `queryType: "none"` for fields that do not need to be queried).

### Key rotation fails with Azure Key Vault
- Azure defaults to the latest CMK version. If the old version is disabled before rewrapping, DEKs encrypted under it become inaccessible.
- Always rewrap all DEKs immediately after rotating the CMK, before disabling the old version.

---

## Performance Characteristics

### CSFLE Performance Impact

Performance varies by workload, document size, and number of encrypted fields. The following are approximate ranges observed in practice -- always benchmark with your own workload:

- **Write overhead:** ~10-20% for automatic encryption (schema validation + encryption per field)
- **Read overhead:** Minimal for non-encrypted fields; ~10-15% for decrypting returned fields
- **Index usage:** Deterministic fields can use standard indexes; randomized fields cannot be indexed
- **crypt_shared vs mongocryptd:** crypt_shared eliminates IPC overhead, providing measurably lower latency per operation

### Queryable Encryption Performance Impact

- **Storage:** 2-3x the unencrypted collection size due to metadata collections
- **Write overhead:** Higher than CSFLE due to metadata collection updates (ESC, ECOC)
- **Read overhead:** Depends on contention factor; higher contention = more partitions to scan
- **Range queries:** Slower than unencrypted range queries; performance depends on `trimFactor` and bounds
- **Compaction benefit:** Can reduce metadata collection size by 50-90% and improve query performance proportionally

### Sizing Guidelines

| Metric | Recommendation |
|--------|---------------|
| Storage budget | 2-3x unencrypted size for fully encrypted collections |
| Metadata compaction frequency | When ESC/ECOC exceed 1 GB or weekly for high-write workloads |
| Maximum queryable encrypted fields | Practical limit ~10-15 per collection before overhead dominates |
| Key Vault size | One document per DEK (~1 KB each); negligible for most deployments |

---

## Migration: CSFLE to Queryable Encryption

1. **Assess compatibility:** Verify you do not need per-user/per-tenant key isolation on the same field (QE uses one key per field)
2. **Verify server version:** QE requires MongoDB 6.0+ (equality), 8.0+ (range)
3. **Create a new collection** with `encryptedFieldsMap` configuration
4. **Export data** from the CSFLE collection using a client configured with CSFLE (reads decrypt automatically)
5. **Import data** into the new QE collection using a client configured with QE (writes encrypt automatically)
6. **Update application code:** Replace `schemaMap` with `encryptedFieldsMap` in driver configuration
7. **Verify queries** work against the new collection
8. **Keep the old CSFLE collection** until validation is complete and production traffic has been stable for a defined period
9. **Drop the old CSFLE collection** only after rollback window expires
10. **Schedule compaction** for the new QE collection

### Rollback Plan

- **Do not drop the CSFLE collection immediately.** Keep it as a rollback target for at least one release cycle.
- If QE migration fails mid-stream, revert the application to the CSFLE-configured driver and point it back at the original collection.
- Maintain a tested `mongodump` backup of the CSFLE collection taken before migration begins.
- Document the rollback procedure in your runbook: revert driver config, validate CSFLE reads/writes, and confirm KMS access before declaring rollback complete.

---

## Advanced QE Parameters: sparsity and trimFactor

Two advanced parameters control performance trade-offs of Queryable Encryption metadata storage:

### sparsity (Range Queries)

Controls the density of the range index tree stored in metadata collections. Values: integer 1–8 (default: 2; MongoDB 8.2+ raised maximum to 8).

| sparsity | Effect |
|----------|--------|
| Low (1–2) | Smaller range partitions → better range query performance → more metadata storage |
| High (6–8) | Larger partitions → less metadata storage → slower range scans |

Recommendation: Keep default (2) unless storage overhead is a primary concern. For large numeric ranges with infrequent range queries, increase to 4–6. **Immutable after collection creation.**

```js
encryptedFields: {
  fields: [{
    path: "salary", bsonType: "int",
    queries: [{ queryType: "range", sparsity: 2, min: 0, max: 1000000 }]
  }]
}
```

### trimFactor (Write Concurrency)

Controls ESC (Encrypted State Collection) entry size to reduce contention on high-write workloads. Default: 6. Range: 0–10. **Immutable after collection creation.**

| trimFactor | Effect |
|------------|--------|
| Low (0–3) | Larger ESC entries → slower concurrent writes → faster range reads |
| High (7–10) | Smaller entries → better concurrent write throughput → slower range reads |

Increase to 8–10 when you have >100 concurrent writes to the same encrypted collection.

---

## Migrating Unencrypted Collections to QE/CSFLE

**Critical constraint:** QE does **not** support `updateMany` or `bulkWrite` multi-document operations on encrypted collections. Migration must be done document-by-document.

```js
// 1. Create new encrypted collection
await db.createCollection("users_encrypted", { encryptedFields: { ... } });

// 2. Migrate one at a time — no bulk ops
const cursor = db.users.find({});
for await (const doc of cursor) {
  await encryptedCollection.insertOne(transformForEncryption(doc));
}

// 3. Verify counts, then rename
await db.users.rename("users_old");
await db.users_encrypted.rename("users");
```

**Why no updateMany:** Encryption is client-side — the driver encrypts each field individually. The server cannot perform batch operations on plaintext it cannot see. Atlas Live Migration is also not supported for encrypted collection moves.

CSFLE explicit mode does allow `updateMany` (unlike automatic mode) — switch to explicit for bulk operations if needed.

---

## Atlas Encryption at Rest + In-Use Encryption: Defense-in-Depth

| Layer | What it protects | Protects against |
|-------|-----------------|-----------------|
| **EAR (Encryption at Rest)** | WiredTiger data files, journal, oplog on disk | Storage theft, cloud provider storage access |
| **CSFLE/QE (In-Use)** | Field values before they reach the server | DBAs, cloud operators, compromised server |

Use both together — EAR alone lets DBAs read plaintext; CSFLE/QE alone leaves WiredTiger files readable if someone has storage access.

### Atlas BYOK (Customer Managed Keys) for EAR

Atlas CMK via AWS KMS, Azure Key Vault, or GCP KMS. Key rotation re-encrypts only the master key wrapper — does not re-encrypt data files (metadata operation only).

---

## KMIP and HashiCorp Vault Integration

### HashiCorp Vault KMIP Requirements

- **Vault Enterprise** with ADP (Advanced Data Protection) license, or **HCP Vault Dedicated Plus**
- Vault KMIP secrets engine: `vault secrets enable kmip`

```bash
vault write kmip/config listen_addrs=0.0.0.0:5696
vault write -f kmip/scope/mongodb
vault write kmip/scope/mongodb/role/app operation_all=true
vault write -f kmip/scope/mongodb/role/app/credential/generate format=pem
```

```js
const client = new MongoClient(uri, {
  autoEncryption: {
    keyVaultNamespace: "encryption.__keyVault",
    kmsProviders: { kmip: { endpoint: "vault-host:5696" } },
    tlsOptions: {
      kmip: {
        tlsCAFile: "/path/to/vault-ca.pem",
        tlsCertificateKeyFile: "/path/to/client-cert.pem"
      }
    }
  }
});
```

Vault KMIP supports automated key rotation and fine-grained ACL policies. Validated with Thales Luna HSMs for hardware-backed key storage.

---

## Audit Logging for Encrypted Collections

### What Atlas audit logs capture
- `authCheck` events: every authenticated operation on encrypted collections
- Enable `auditAuthorizationSuccess: true` for full CRUD audit (not just failures)
- M10+ required for always-on database authentication auditing

### What audit logs do NOT capture
- **Which encrypted field values were decrypted** — decryption is client-side; the server never sees plaintext
- **Key vault access patterns** — use KMS provider audit logs (CloudTrail, Azure Monitor, GCP audit logs)

```js
// Query Atlas audit logs for encrypted collection access
db.mongodb_logs.aggregate([
  { $match: { "atype": "authCheck", "param.ns": /users_encrypted/, "result": 0 }},
  { $group: { _id: "$user", queryCount: { $sum: 1 }, lastAccess: { $max: "$ts" }}}
])
```

---

## Java Driver Setup for QE

```xml
<dependency>
  <groupId>org.mongodb</groupId><artifactId>mongodb-driver-sync</artifactId><version>5.1.0</version>
</dependency>
<dependency>
  <groupId>org.mongodb</groupId><artifactId>mongodb-crypt</artifactId><version>1.10.0</version>
</dependency>
```

```java
Map<String, Map<String, Object>> kmsProviders = new HashMap<>();
Map<String, Object> awsKms = new HashMap<>();
awsKms.put("accessKeyId", System.getenv("AWS_ACCESS_KEY_ID"));
awsKms.put("secretAccessKey", System.getenv("AWS_SECRET_ACCESS_KEY"));
kmsProviders.put("aws", awsKms);

Map<String, BsonDocument> encryptedFieldsMap = new HashMap<>();
encryptedFieldsMap.put("mydb.users", BsonDocument.parse(
  "{ \"fields\": [{ \"path\": \"ssn\", \"bsonType\": \"string\", \"queries\": [{\"queryType\": \"equality\"}] }] }"
));

AutoEncryptionSettings autoSettings = AutoEncryptionSettings.builder()
    .keyVaultNamespace("encryption.__keyVault")
    .kmsProviders(kmsProviders)
    .encryptedFieldsMap(encryptedFieldsMap)
    .build();

MongoClient client = MongoClients.create(
    MongoClientSettings.builder()
        .applyConnectionString(new ConnectionString(uri))
        .autoEncryptionSettings(autoSettings)
        .build()
);
```

Minimum: Java driver 5.x (or 4.10+), `mongodb-crypt` 1.7.3+ for key rotation API.

---

## C# Driver Setup for QE

```xml
<PackageReference Include="MongoDB.Driver" Version="2.28.0" />
```

```csharp
var kmsProviders = new Dictionary<string, IReadOnlyDictionary<string, object>> {
    { "aws", new Dictionary<string, object> {
        { "accessKeyId", Environment.GetEnvironmentVariable("AWS_ACCESS_KEY_ID") },
        { "secretAccessKey", Environment.GetEnvironmentVariable("AWS_SECRET_ACCESS_KEY") }
    }}
};

var encryptedFieldsMap = new Dictionary<string, BsonDocument> {
    { "mydb.users", BsonDocument.Parse(
        "{ \"fields\": [{ \"path\": \"ssn\", \"bsonType\": \"string\", \"queries\": [{\"queryType\": \"equality\"}] }] }"
    )}
};

var settings = MongoClientSettings.FromConnectionString(uri);
settings.AutoEncryptionOptions = new AutoEncryptionOptions(
    keyVaultNamespace: new CollectionNamespace("encryption", "__keyVault"),
    kmsProviders: kmsProviders,
    encryptedFieldsMap: encryptedFieldsMap
);
var client = new MongoClient(settings);
```

C# driver 2.28+ supports KMIP delegated mode and range queries. Use `EncryptedFieldsMap` for QE; use `SchemaMap` for CSFLE.

---

## Compliance Mapping

MongoDB in-use encryption (CSFLE and QE) supports compliance requirements across multiple regulatory frameworks. The mapping below shows how encryption features align with specific controls ([Atlas encryption guidance](https://www.mongodb.com/docs/atlas/architecture/current/data-encryption/)):

| Regulation | Relevant Control | How CSFLE/QE Helps |
|-----------|-----------------|-------------------|
| **HIPAA** | Technical Safeguards (164.312) | Encrypts PHI fields (SSN, diagnosis, lab results) so even DBAs and cloud operators cannot read them |
| **PCI-DSS** | Requirement 3 (Protect Stored Data) | Encrypts cardholder data (PAN, CVV) at the field level; KMS-managed keys satisfy key management requirements |
| **GDPR** | Article 32 (Security of Processing) | Field-level encryption as a technical measure; supports right-to-erasure via DEK deletion (crypto-shredding) |
| **SOC 2** | CC6.1 (Logical and Physical Access) | Server and DBAs never see plaintext; access requires both KMS credentials and application-level authorization |
| **CCPA** | 1798.150 (Data Security) | Encrypts personal information at rest in the database; breach of encrypted data may reduce notification obligations |

### Crypto-Shredding for GDPR Right-to-Erasure

When using per-user or per-tenant DEKs (CSFLE pattern), you can satisfy deletion requests by deleting the DEK from the Key Vault rather than locating and deleting every document containing that user's data. Without the DEK, the encrypted fields become permanently unreadable. This technique is known as crypto-shredding.

---

## References

1. [MongoDB CSFLE documentation](https://www.mongodb.com/docs/manual/core/csfle/) -- Official CSFLE reference covering architecture, setup, and limitations
2. [MongoDB Queryable Encryption documentation](https://www.mongodb.com/docs/manual/core/queryable-encryption/) -- Official QE reference covering setup, query types, and metadata management
3. [Choosing an In-Use Encryption Approach (CSFLE vs QE)](https://www.mongodb.com/docs/manual/core/queryable-encryption/about-qe-csfle/) -- Decision guidance for selecting between CSFLE and QE
4. [KMS Providers reference](https://www.mongodb.com/docs/manual/core/queryable-encryption/fundamentals/kms-providers/) -- Configuration details for AWS KMS, Azure Key Vault, GCP KMS, KMIP, and local keys
5. [Encrypted Fields and Enabled Queries](https://www.mongodb.com/docs/manual/core/queryable-encryption/fundamentals/encrypt-and-query/) -- Contention factor, query types, BSON type support, and range options
6. [CSFLE Encryption Schemas](https://www.mongodb.com/docs/manual/core/csfle/reference/encryption-schemas/) -- JSON Schema syntax for CSFLE automatic encryption
7. [QE Supported Operations](https://www.mongodb.com/docs/manual/core/queryable-encryption/reference/supported-operations/) -- Complete list of supported query operators for encrypted fields
8. [QE Limitations](https://www.mongodb.com/docs/manual/core/queryable-encryption/reference/limitations/) -- Current constraints including preview feature warnings
9. [Encrypted Collections Management](https://www.mongodb.com/docs/manual/core/queryable-encryption/fundamentals/manage-collections/) -- Compaction, metadata collections, and storage management
10. [CSFLE Encryption Algorithms](https://www.mongodb.com/docs/manual/core/csfle/fundamentals/encryption-algorithms/) -- Deterministic vs randomized algorithm details
11. [MongoDB Announces Queryable Encryption](https://www.mongodb.com/company/blog/product-release-announcements/mongodb-announces-queryable-encryption) -- Product announcement with architectural overview
12. [Strengthen Data Security with Queryable Encryption](https://www.mongodb.com/company/blog/product-release-announcements/strengthen-data-security-mongodb-queryable-encryption) -- Deep dive on QE security properties and range query support
13. [MongoDB Queryable Encryption range queries (MongoDB 8.0)](https://www.helpnetsecurity.com/2024/10/17/mongodb-queryable-encryption-mongodb-8/) -- Coverage of range query GA in MongoDB 8.0
14. [Mongoose CSFLE Integration](https://mongoosejs.com/docs/field-level-encryption.html) -- Mongoose ODM setup for CSFLE and QE
15. [Mongoose QE and CSFLE Native Support](https://www.mongodb.com/company/blog/product-release-announcements/mongoose-now-natively-supports-qe-csfle) -- Announcement of native Mongoose support
16. [PyMongo In-Use Encryption](https://pymongo.readthedocs.io/en/stable/examples/encryption.html) -- Python driver encryption examples
17. [Spring Data MongoDB Encryption](https://docs.spring.io/spring-data/mongodb/reference/mongodb/mongo-encryption.html) -- Java/Spring framework encryption integration
18. [MongoDB Client-Side Encryption Specification](https://github.com/mongodb/specifications/blob/master/source/client-side-encryption/client-side-encryption.md) -- Driver specification for implementers
19. [Atlas Architecture: Data Encryption Guidance](https://www.mongodb.com/docs/atlas/architecture/current/data-encryption/) -- Atlas-specific encryption architecture recommendations
20. [Queryable Encryption Complete Guide (Mydbops)](https://medium.com/@mydbopsdatabasemanagement/queryable-encryption-in-mongodbqueryable-encryption-in-mongodb-a-complete-guide-b021d2cfb2b3) -- Community deep dive on QE architecture and internals
