-- Custom pgvector search with dynamic (elbow) cutoff
--
-- Usage:
--   npx prisma db execute --file prisma/vector_search_elbow.sql
--
-- Creates:
--   cbis_vector_search_elbow(query_vec, top_k, min_results, max_results, sharpness,
--                           mime_types, is_document, has_people, is_screenshot, is_animal,
--                           min_nima_score, max_nima_score)

CREATE OR REPLACE FUNCTION cbis_vector_search_elbow(
  query_vec vector(512),
  top_k integer DEFAULT 100,
  min_results integer DEFAULT 5,
  max_results integer DEFAULT 50,
  sharpness real DEFAULT 3.0,
  mime_types text[] DEFAULT NULL,
  is_document boolean DEFAULT NULL,
  has_people boolean DEFAULT NULL,
  is_screenshot boolean DEFAULT NULL,
  is_animal boolean DEFAULT NULL,
  min_nima_score real DEFAULT NULL,
  max_nima_score real DEFAULT NULL
)
RETURNS TABLE(
  id text,
  filename text,
  "originalName" text,
  "mimeType" text,
  size integer,
  width integer,
  height integer,
  "uploadedAt" timestamptz,
  caption text,
  "nimaScore" real,
  "isDocument" boolean,
  "hasPeople" boolean,
  "isScreenshot" boolean,
  "isAnimal" boolean,
  distance double precision,
  similarity_score double precision,
  rank integer
)
LANGUAGE sql
STABLE
AS $$
WITH candidates AS (
  SELECT
    b.id,
    b.filename,
    b."originalName",
    b."mimeType",
    b.size::int AS size,
    b.width,
    b.height,
    b."createdAt" AS "uploadedAt",
    e.caption,
    ba."nimaScore",
    ba."isDocument",
    ba."hasPeople",
    ba."isScreenshot",
    ba."isAnimal",
    (e.vector <=> query_vec)::float8 AS distance,
    ROW_NUMBER() OVER (ORDER BY (e.vector <=> query_vec)) AS rank
  FROM blobs b
  JOIN embeddings e ON e."blobId" = b.id
  LEFT JOIN blob_attributes ba ON ba."blobId" = b.id
  WHERE b."processingStatus" = 'completed'
    AND (mime_types IS NULL OR b."mimeType" = ANY(mime_types))
    AND (is_document IS NULL OR ba."isDocument" = is_document)
    AND (has_people IS NULL OR ba."hasPeople" = has_people)
    AND (is_screenshot IS NULL OR ba."isScreenshot" = is_screenshot)
    AND (is_animal IS NULL OR ba."isAnimal" = is_animal)
    AND (min_nima_score IS NULL OR ba."nimaScore" >= min_nima_score)
    AND (max_nima_score IS NULL OR ba."nimaScore" <= max_nima_score)
  ORDER BY (e.vector <=> query_vec)
  LIMIT GREATEST(top_k, max_results, min_results)
),

diffs AS (
  SELECT
    rank,
    distance,
    distance - LAG(distance) OVER (ORDER BY rank) AS diff
  FROM candidates
),

diff_stats AS (
  SELECT
    MAX(diff) AS max_diff,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY diff) FILTER (WHERE diff IS NOT NULL) AS median_diff
  FROM diffs
),

best_jump AS (
  SELECT d.rank AS jump_rank, d.diff
  FROM diffs d
  CROSS JOIN diff_stats s
  WHERE d.diff IS NOT NULL
    AND (
      (s.median_diff IS NOT NULL AND s.median_diff > 0 AND s.max_diff >= sharpness * s.median_diff)
      OR (s.median_diff IS NULL AND s.max_diff IS NOT NULL AND s.max_diff > 0)
      OR (s.median_diff = 0 AND s.max_diff > 0)
    )
  ORDER BY d.diff DESC, d.rank ASC
  LIMIT 1
),

limits AS (
  SELECT
    (SELECT COUNT(*) FROM candidates) AS n,
    GREATEST(1, min_results) AS min_n,
    GREATEST(1, max_results) AS max_n,
    CASE
      WHEN (SELECT jump_rank FROM best_jump) IS NULL THEN GREATEST(1, max_results)
      ELSE GREATEST(1, (SELECT jump_rank FROM best_jump) - 1)
    END AS elbow_n
),

keep AS (
  SELECT LEAST(n, GREATEST(min_n, LEAST(max_n, elbow_n))) AS keep_n
  FROM limits
)

SELECT
  c.id,
  c.filename,
  c."originalName",
  c."mimeType",
  c.size,
  c.width,
  c.height,
  c."uploadedAt",
  c.caption,
  c."nimaScore",
  c."isDocument",
  c."hasPeople",
  c."isScreenshot",
  c."isAnimal",
  c.distance,
  (1 - c.distance)::float8 AS similarity_score,
  c.rank
FROM candidates c
CROSS JOIN keep k
WHERE c.rank <= k.keep_n
ORDER BY c.rank;
$$;
