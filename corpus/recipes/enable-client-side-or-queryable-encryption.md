---
name: enable-client-side-or-queryable-encryption
title: Enable client-side field encryption (CSFLE or Queryable Encryption)
summary: Choose between CSFLE and Queryable Encryption, set up a KMS-backed key hierarchy and encrypted collection, verify that the server only sees ciphertext, and plan key rotation and limits.
applies_to: [atlas, self-managed]
sources:
  - skills/mongodb-operations-expert/references/mongodb-encryption.md
  - skills/mongodb-expert/references/mongodb-multi-tenancy.md
---
# Enable client-side field encryption (CSFLE or Queryable Encryption)

## When to use
- Sensitive field values (identifiers, medical notes, account numbers) must be unreadable to database administrators and cloud operators. The driver encrypts before data leaves the client, so the server never sees plaintext.
- You must pick between Client-Side Field Level Encryption (CSFLE) and Queryable Encryption (QE) for a collection.
- You need per-tenant or per-user keys, or you need to query encrypted fields.

This is separate from encryption at rest (EAR). EAR protects storage files; in-use encryption protects field values from operators. Use both.

## Prerequisites (checklist)
- [ ] Edition: Atlas or Enterprise for automatic encryption. Community Edition supports only CSFLE explicit encryption (`encrypt()` / `decrypt()` calls in app code). QE is not available on Community.
- [ ] A cloud KMS key (AWS KMS, Azure Key Vault, GCP KMS, or a KMIP server) for production. A local key is for development only.
- [ ] KMS credentials with encrypt and decrypt permission on the key (AWS example: `kms:Encrypt`, `kms:Decrypt`).
- [ ] Driver and its encryption companion library installed (Node.js example: `mongodb-client-encryption`).
- [ ] The `crypt_shared` library downloaded from the MongoDB Enterprise download center (preferred over `mongocryptd`).
- [ ] Server version for the query types you need: QE equality GA in 7.0, QE range GA in 8.0. Do not use the 6.0 preview (incompatible with GA).
- [ ] You listed the exact fields to encrypt and which of them you must query.
- [ ] A storage budget of 2 to 3 times the unencrypted size for QE collections.

## Steps

### 1. Choose the approach
Decision tree from the corpus:
- Need different keys per user or per tenant for the same field: CSFLE.
- Existing app already on CSFLE and no need for range queries: stay on CSFLE.
- Otherwise (new project): Queryable Encryption.

Key differences:

| Topic | CSFLE | Queryable Encryption |
|---|---|---|
| Equality query | Deterministic fields only | Yes (`queryType: "equality"`) |
| Range query | No | Yes, 8.0+ (`queryType: "range"`) |
| Frequency leakage | Deterministic mode leaks repeats | Randomized for all fields, no repeat leakage |
| Keys | Many DEKs per field possible | One key per field |
| Mixed in one collection | Never | Never |

Expect: one written decision per collection. Never mix CSFLE and QE in the same collection; use separate collections if you need both.

### 2. Create the customer master key in the KMS
Create the key in your KMS and record its identifier (AWS example: key ARN and region).
```text
Cloud console or KMS CLI: create a symmetric key, grant the application role Encrypt and Decrypt
```
Expect: you have a key ARN (or the equivalent URL or resource path) `<kms-key-id>`.

### 3. Create the key vault collection and index
```javascript
db.getSiblingDB("encryption").getCollection("__keyVault").createIndex(
  { keyAltNames: 1 },
  { unique: true, partialFilterExpression: { keyAltNames: { $exists: true } } }
)
```
Expect: an index name is returned. The key vault holds one small document per data encryption key (DEK). Restrict who can read and write it.

### 4A. CSFLE: create a DEK and a schema map
```javascript
const { ClientEncryption } = require("mongodb");
const kmsProviders = { aws: { accessKeyId: process.env.AWS_ACCESS_KEY_ID,
                              secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY } };
const enc = new ClientEncryption(keyVaultClient, {
  keyVaultNamespace: "encryption.__keyVault", kmsProviders });
const dataKeyId = await enc.createDataKey("aws", {
  masterKey: { key: "<kms-key-id>", region: "<region>" } });
```
Expect: `dataKeyId` is a Binary UUID, and a new document exists in `encryption.__keyVault`.

Schema map for `mydb.users`:
```javascript
const schemaMap = { "mydb.users": {
  bsonType: "object",
  encryptMetadata: { keyId: [dataKeyId] },
  properties: {
    ssn:          { encrypt: { bsonType: "string",
                    algorithm: "AEAD_AES_256_CBC_HMAC_SHA_512-Deterministic" } },
    medicalNotes: { encrypt: { bsonType: "string",
                    algorithm: "AEAD_AES_256_CBC_HMAC_SHA_512-Random" } } } } };
```
Use Deterministic only for fields you must match exactly and that have high cardinality. Use Random for everything else.

### 4B. QE: define encrypted fields and create the collection
```javascript
const encryptedFields = { fields: [
  { path: "patientId", bsonType: "string",
    queries: { queryType: "equality", contention: 8 } },
  { path: "age", bsonType: "int",
    queries: { queryType: "range", contention: 0, trimFactor: 6, min: 0, max: 150 } },
  { path: "diagnosis", bsonType: "string" }   // encrypted, not queryable
] };
await enc.createEncryptedCollection(db, "patients", {
  provider: "aws",
  createCollectionOptions: { encryptedFields },
  masterKey: { key: "<kms-key-id>", region: "<region>" }
});
```
Expect: the `patients` collection plus internal metadata collections named like `enxcol_.patients.esc` and `enxcol_.patients.ecoc`. DEKs are generated for you.

Rules: `queryType`, `contention` and the range options (`min`, `max`, `sparsity`, `trimFactor`) go inside a `queries: { ... }` object on each field entry; there is no separate `rangeOptions`. Set `queries` only on fields you query (each adds 2 to 3 times metadata overhead). `contention` is fixed at collection creation and cannot change afterwards (recreate the collection to change it). For `double` and `decimal` range fields `min` and `max` are required; for `int`, `long`, `date` they are optional but recommended. Range needs MongoDB 8.0 or later. QE equality does not support `array`, `decimal`, `double` or `object`.

### 5. Create the encrypting client
```javascript
const client = new MongoClient(uri, { autoEncryption: {
  kmsProviders,
  keyVaultNamespace: "encryption.__keyVault",
  encryptedFieldsMap: { "mydb.patients": encryptedFields },   // QE
  // schemaMap,                                               // CSFLE instead
  extraOptions: { cryptSharedLibPath: "<path-to>/mongo_crypt_v1.so",
                  cryptSharedLibRequired: true }
} });
```
Expect: the client connects and `Using crypt_shared library` appears in driver debug logs. With `cryptSharedLibRequired: true` startup fails instead of silently falling back to `mongocryptd`.

### 6. Write and query through the encrypting client
```javascript
const coll = client.db("mydb").collection("patients");
await coll.insertOne({ patientId: "P-1001", age: 47, diagnosis: "<text>" });
await coll.findOne({ patientId: "P-1001" });
await coll.find({ age: { $gte: 40, $lte: 50 } }).toArray();   // range needs 8.0+
```
Expect: the reads return plaintext values to the encrypting client.

### 7. Schedule maintenance (QE)
```javascript
db.getSiblingDB("mydb").patients.compactStructuredEncryptionData()
```
Expect: success. Run it when the metadata collections pass about 1 GB or query performance drops (weekly for high-write workloads), in a maintenance window with reduced writes.

### 8. Rotate the master key
Rotate the key in the KMS, then rewrap every DEK before disabling the old key version:
```javascript
const r = await enc.rewrapManyDataKey(
  { masterKey: { key: "<old-kms-key-id>" } },
  { provider: "aws", masterKey: { key: "<new-kms-key-id>", region: "<region>" } });
console.log(r.bulkWriteResult.modifiedCount);
```
Expect: the count equals the number of DEKs under the old key. Do not disable the old key until it is non-zero for all and reads still work.

## Verify
1. Connect with a plain client (no `autoEncryption`) and read a document:
```javascript
db.getSiblingDB("mydb").patients.findOne()
```
Expect: encrypted fields show as `Binary` ciphertext, not plaintext.
2. Read the same document through the encrypting client. Expect: plaintext.
3. Run a query on a queryable field through the encrypting client. Expect: the expected document is returned.
4. Confirm the metadata collections exist: `db.getCollectionNames()` lists the `enxcol_.*` collections.
5. Confirm the key vault contains the DEKs: `db.getSiblingDB("encryption").__keyVault.countDocuments()`.
6. Check storage: for QE, total size 2 to 3 times the plaintext estimate is expected.

## Rollback / abort
- You cannot decrypt in place. To go back, read through an encrypting client and write plaintext to a new collection (or use a non-encrypting client to dump ciphertext only if you also keep keys).
- CSFLE to QE migration: create a new collection with `encryptedFieldsMap`, read from the CSFLE collection with a CSFLE client, write into the QE collection with a QE client, verify, keep the old collection and a tested `mongodump` backup for at least one release cycle, then drop it.
- If a migration fails, point the application back at the original collection with the previous driver configuration and confirm KMS access.
- Never delete or disable a KMS key (or DEKs) you might still need; data encrypted under it becomes permanently unreadable.
- To migrate an unencrypted collection into QE, `updateMany` and `bulkWrite` are not supported. Insert one document at a time into a new encrypted collection, verify counts, then rename.

## Pitfalls
- Local master key in production. Anyone with application access can decrypt everything.
- Mixing CSFLE and QE in one collection.
- Deterministic encryption on low-cardinality fields (boolean, status, gender) leaks frequency and enables inference.
- Setting `queryType` on every field; storage and write cost grow quickly. Practical limit in the corpus is about 10 to 15 queryable fields per collection.
- Forgetting to rewrap DEKs after master key rotation, especially with Azure Key Vault, which defaults to the latest key version.
- Skipping compaction; ESC and ECOC grow without bound.
- High contention (16 or more) on read-heavy fields slows reads; use 0 to 4 for read-heavy workloads. The corpus suggests contention at least the expected concurrent writers within a 30 ms window.
- `mongocryptd` spawning unexpectedly: set `cryptSharedLibRequired: true` and `mongocryptdBypassSpawn: true`.
- Encrypted query returns nothing: the field was randomized in CSFLE, no `queryType` was set in QE, or the client uses a different schema or DEK than the collection.
- Encrypting array elements individually is unsupported; encrypt the whole array as a unit.
- Prefix, suffix and substring query types are public preview in 8.2 and the GA version will be incompatible; do not use them in production.
- You cannot `$vectorSearch` over an encrypted embedding field. Encrypt source fields and leave the vector and coarse filter keys queryable.
- "not authorized" on encrypted operations: KMS permissions or the missing key vault index.
- Collection-level RBAC alone does not give cryptographic per-tenant isolation; use per-tenant DEKs with CSFLE.
- Atlas Live Migration is not supported for moving encrypted collections.

## Sources
- `skills/mongodb-operations-expert/references/mongodb-encryption.md:146-175` (quick rules, edition table)
- `skills/mongodb-operations-expert/references/mongodb-encryption.md:176-286` (overview, key hierarchy, KMS providers, algorithms, query type table, BSON types)
- `skills/mongodb-operations-expert/references/mongodb-encryption.md:290-318` (crypt_shared vs mongocryptd)
- `skills/mongodb-operations-expert/references/mongodb-encryption.md:343-570` (decision tree, CSFLE and QE setup, contention, compaction)
- `skills/mongodb-operations-expert/references/mongodb-encryption.md:653-672` (key rotation with `rewrapManyDataKey`)
- `skills/mongodb-operations-expert/references/mongodb-encryption.md:698-830` (anti-patterns, troubleshooting, performance, CSFLE to QE migration and rollback)
- `skills/mongodb-operations-expert/references/mongodb-encryption.md:863-903` (unencrypted to QE migration, EAR plus in-use)
- `skills/mongodb-operations-expert/references/mongodb-encryption.md:1043-1047` (crypto-shredding)
- `skills/mongodb-expert/references/mongodb-multi-tenancy.md:292-345` (per-tenant DEKs and the collection-RBAC caveat)
