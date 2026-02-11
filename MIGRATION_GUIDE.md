# Database Migration Guide - Face Recognition Feature

## Current Status

✅ **Code Fixed**: All TypeScript errors in face detection API route are resolved  
⚠️ **Database**: Migration needs to be run when database is accessible

## What Was Fixed

### TypeScript Errors Fixed in `route.ts`
1. ✅ Removed `any` types from error handlers
2. ✅ Added proper type for face mapping function
3. ✅ Used proper error handling with `instanceof Error`
4. ✅ Added `FaceWithPerson` interface for type safety

### Changes Made
```typescript
// Added interface for type safety
interface FaceWithPerson {
  id: string;
  boundingBox: unknown;
  confidence: number | null;
  quality: number | null;
  person: {
    id: string;
    name: string | null;
    faceCount: number;
  } | null;
}

// Fixed error handling (removed `any`)
catch (error) {
  const errorMessage = error instanceof Error ? error.message : 'Failed...';
  // ...
}

// Fixed map function type
faces.map((face: FaceWithPerson) => ({
  // ...
}))
```

## Migration Steps (When Database is Accessible)

### Option 1: Fresh Migration (Recommended if no production data)

```powershell
cd next-js

# Create migration for face recognition tables
npx prisma migrate dev --name add_face_recognition

# Generate Prisma Client
npx prisma generate
```

This will create:
- `FaceInstance` table
- `Person` table
- Indexes for efficient queries
- Foreign key relationships

### Option 2: With Existing Data (If tables already exist)

If you have drift (existing tables without migrations):

```powershell
cd next-js

# 1. Create baseline migration for existing schema
npx prisma migrate dev --create-only --name baseline_existing

# 2. Mark the baseline as applied (don't run SQL)
npx prisma migrate resolve --applied baseline_existing

# 3. Create face recognition migration
npx prisma migrate dev --name add_face_recognition

# 4. Generate Prisma Client
npx prisma generate
```

### Option 3: Manual SQL (If migrations fail)

Run this SQL directly on your database:

```sql
-- Create persons table
CREATE TABLE IF NOT EXISTS "persons" (
  "id" TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  "createdAt" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updatedAt" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "name" TEXT,
  "notes" TEXT,
  "thumbnail" TEXT,
  "faceCount" INTEGER NOT NULL DEFAULT 0,
  "tags" TEXT[] DEFAULT ARRAY[]::TEXT[]
);

-- Create face_instances table
CREATE TABLE IF NOT EXISTS "face_instances" (
  "id" TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  "createdAt" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updatedAt" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
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
  "embeddingModel" TEXT NOT NULL DEFAULT 'arcface',
  CONSTRAINT "face_instances_blobId_fkey" FOREIGN KEY ("blobId") 
    REFERENCES "blobs"("id") ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT "face_instances_personId_fkey" FOREIGN KEY ("personId") 
    REFERENCES "persons"("id") ON DELETE SET NULL ON UPDATE CASCADE
);

-- Create indexes
CREATE INDEX IF NOT EXISTS "face_instances_blobId_idx" ON "face_instances"("blobId");
CREATE INDEX IF NOT EXISTS "face_instances_personId_idx" ON "face_instances"("personId");
CREATE INDEX IF NOT EXISTS "persons_name_idx" ON "persons"("name");

-- Create vector index for similarity search (optional but recommended)
CREATE INDEX IF NOT EXISTS "face_instances_embedding_idx" 
  ON "face_instances" USING ivfflat ("embedding" vector_cosine_ops);

-- Add faces relation to blobs (already exists in schema)
-- The foreign key constraint handles this
```

Then mark as migrated:

```powershell
npx prisma db pull
npx prisma generate
```

## Verification

After running the migration, verify it worked:

```powershell
# Check Prisma Client generated correctly
npx prisma generate

# Verify tables exist
npx prisma studio
# Should see FaceInstance and Person in the UI
```

## Troubleshooting

### Error: "Property 'faceInstance' does not exist"

**Cause**: Prisma Client hasn't been regenerated after schema changes

**Solution**:
```powershell
npx prisma generate
```

### Error: "Database drift detected"

**Cause**: Database has tables that don't match migration history

**Solution**: Use Option 2 above (baseline + resolve)

### Error: "Can't reach database server"

**Cause**: Database connection issue

**Solution**: 
1. Check `.env` file has correct `DATABASE_URL`
2. Verify database is running
3. Check network connectivity
4. Try `DIRECT_URL` if using connection pooler

## Next Steps After Migration

1. ✅ Verify migration succeeded
2. ✅ Test API endpoint: `POST /api/blobs/[id]/detect-faces`
3. ✅ Deploy Face Detection service (see `FACE_DETECTION/DEPLOYMENT.md`)
4. ✅ Test end-to-end face detection workflow
5. ✅ Build person management UI

## Files That Need the Migration

These files depend on the `FaceInstance` and `Person` models:

- ✅ `app/api/blobs/[id]/detect-faces/route.ts` (already updated)
- ⏳ `FACE_DETECTION/app.py` (will create records)
- ⏳ Future: Person management UI
- ⏳ Future: Face search feature

## Current State

```
Schema:        ✅ Updated with FaceInstance and Person models
TypeScript:    ✅ No errors in route.ts
Migration:     ⏳ Pending (needs database connection)
Prisma Client: ⏳ Needs regeneration after migration
Service Ready: ✅ Face Detection service code complete
```

## Quick Commands Reference

```powershell
# When database is accessible:

# 1. Run migration
cd next-js
npx prisma migrate dev --name add_face_recognition

# 2. Generate client
npx prisma generate

# 3. Verify
npx prisma studio

# 4. Deploy face detection service
cd ../FACE_DETECTION
.\deploy.ps1 -Step all
```
