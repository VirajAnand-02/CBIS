-- Manual SQL Migration for Face Recognition Tables
-- Run this directly on your PostgreSQL database using psql or Supabase SQL editor
-- This will add the Person and FaceInstance tables to your existing CBIS database

-- Step 1: Create persons table
CREATE TABLE IF NOT EXISTS "persons" (
  "id" TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updatedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "name" TEXT,
  "notes" TEXT,
  "thumbnail" TEXT,
  "faceCount" INTEGER NOT NULL DEFAULT 0,
  "tags" TEXT[] DEFAULT ARRAY[]::TEXT[]
);

-- Step 2: Create face_instances table
CREATE TABLE IF NOT EXISTS "face_instances" (
  "id" TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updatedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "blobId" TEXT NOT NULL,
  "boundingBox" JSONB NOT NULL,
  "embedding" vector(512) NOT NULL,
  "confidence" DOUBLE PRECISION,
  "quality" DOUBLE PRECISION,
  "sharpness" DOUBLE PRECISION,
  "brightness" DOUBLE PRECISION,
  "facingAngle" DOUBLE PRECISION,
  "personId" TEXT,
  "detectorModel" TEXT NOT NULL DEFAULT 'retinaface',
  "embeddingModel" TEXT NOT NULL DEFAULT 'arcface'
);

-- Step 3: Add foreign key constraints
ALTER TABLE "face_instances" 
  DROP CONSTRAINT IF EXISTS "face_instances_blobId_fkey",
  ADD CONSTRAINT "face_instances_blobId_fkey" 
    FOREIGN KEY ("blobId") REFERENCES "blobs"("id") 
    ON DELETE CASCADE ON UPDATE CASCADE;

ALTER TABLE "face_instances" 
  DROP CONSTRAINT IF EXISTS "face_instances_personId_fkey",
  ADD CONSTRAINT "face_instances_personId_fkey" 
    FOREIGN KEY ("personId") REFERENCES "persons"("id") 
    ON DELETE SET NULL ON UPDATE CASCADE;

-- Step 4: Create indexes for persons
CREATE INDEX IF NOT EXISTS "persons_name_idx" ON "persons"("name");

-- Step 5: Create indexes for face_instances
CREATE INDEX IF NOT EXISTS "face_instances_blobId_idx" ON "face_instances"("blobId");
CREATE INDEX IF NOT EXISTS "face_instances_personId_idx" ON "face_instances"("personId");

-- Step 6: Create vector index for similarity search (for better performance)
-- Note: This may take some time if you have many face instances
CREATE INDEX IF NOT EXISTS "face_instances_embedding_idx" 
  ON "face_instances" USING ivfflat ("embedding" vector_cosine_ops)
  WITH (lists = 100);

-- Step 7: Verify tables were created
SELECT 
  table_name,
  (SELECT COUNT(*) FROM information_schema.columns WHERE table_name = t.table_name) as column_count
FROM information_schema.tables t
WHERE table_schema = 'public' 
AND table_name IN ('persons', 'face_instances')
ORDER BY table_name;

-- Step 8: Display table structures
\d persons
\d face_instances
