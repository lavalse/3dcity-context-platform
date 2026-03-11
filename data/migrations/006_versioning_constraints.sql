-- Migration 006: Versioning invariants
--
-- Enforce the key invariant used by the API: at most one current version
-- may exist for a feature at any time.

CREATE UNIQUE INDEX IF NOT EXISTS feature_versions_one_current_idx
ON citydb.feature_versions (gmlid)
WHERE status = 'current';
