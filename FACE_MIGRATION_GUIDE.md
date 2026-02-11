# Face Recognition Database Migration Guide

## Problem
Your database already has tables but no Prisma migration history (drift detected). The standard `prisma migrate dev` command wants to reset the database, which would lose all your existing data.

## Solution
Run the SQL migration manually to add only the face recognition tables.

## Steps

### Option 1: Using Supabase Dashboard (Recommended)

1. Go to your Supabase project dashboard
2. Navigate to **SQL Editor**
3. Create a new query
4. Copy the entire contents of `prisma/add_face_recognition.sql`
5. Paste and run the query
6. Verify the tables were created (you should see output showing 2 tables)

### Option 2: Using psql Command Line

```powershell
# Connect to your database
psql "postgresql://user:password@aws-1-ap-south-1.pooler.supabase.com:5432/postgres"

# Run the migration file
\i E:/programming/CBIS_Project/next-js/prisma/add_face_recognition.sql
```

### Option 3: Using npx prisma studio

After running the SQL:

```powershell
npx prisma studio
```

Check if you can see the `Person` and `FaceInstance` models.

## What Gets Created

### Tables
1. **persons** - Stores unique individuals
   - id, name, thumbnail, faceCount, tags, notes
   - Created/Updated timestamps

2. **face_instances** - Stores detected faces
   - id, blobId, personId, boundingBox, embedding
   - confidence, quality, sharpness, brightness, facingAngle
   - detectorModel, embeddingModel

### Indexes
- `persons_name_idx` - Fast person name lookup
- `face_instances_blobId_idx` - Fast lookup by image
- `face_instances_personId_idx` - Fast lookup by person
- `face_instances_embedding_idx` - Fast similarity search (vector index)

### Foreign Keys
- `face_instances.blobId` → `blobs.id` (CASCADE on delete)
- `face_instances.personId` → `persons.id` (SET NULL on delete)

## Verification

After running the SQL, verify it worked:

```powershell
# Regenerate Prisma Client (already done)
npx prisma generate

# Test the API
# Navigate to http://localhost:3000/peoples
# You should see the page without errors
```

## Current Status

✅ Prisma schema updated with FaceInstance and Person models
✅ Prisma Client generated successfully  
⏳ **Next: Run the SQL file on your database**
⏳ Then: Deploy Face Detection service (see FACE_DETECTION/DEPLOYMENT.md)

## Files

- **SQL Migration**: `next-js/prisma/add_face_recognition.sql`
- **Prisma Schema**: `next-js/prisma/schema.prisma` (updated)
- **Generated Client**: `next-js/lib/generated/prisma/` (ready to use)

## Troubleshooting

### Error: "relation 'persons' does not exist"
- The SQL hasn't been run yet. Execute the SQL file.

### Error: "column 'embedding' has type 'vector' which is not supported"
- Make sure pgvector extension is enabled:
  ```sql
  CREATE EXTENSION IF NOT EXISTS vector;
  ```

### Error: "foreign key constraint"
- Make sure the `blobs` table exists before running the migration
- Check that you're running on the correct database

## After Migration

Once the tables are created:

1. ✅ Visit `/peoples` - should load without errors
2. ✅ API `/api/peoples` - should return empty array `[]`
3. ✅ Ready for face detection service
4. ✅ Can start uploading images and detecting faces

## Next Steps

1. Run the SQL migration (above)
2. Test `/peoples` page works
3. Deploy Face Detection service:
   ```powershell
   cd ../FACE_DETECTION
   .\deploy.ps1 -Step all
   ```
4. Upload images with faces
5. See detected people appear in `/peoples`!
