# CBIS Database Setup Guide

This guide will help you set up the PostgreSQL database for the CBIS project using Supabase.

## Prerequisites

- Supabase account (free tier works fine)
- Node.js and npm installed
- Prisma CLI installed (`npm install -g prisma`)

## Schema Overview

The CBIS database includes the following tables:

| Table | Purpose |
|-------|---------|
| `blobs` | Main metadata for uploaded images/documents |
| `embeddings` | CLIP vector embeddings (512-dim) for semantic search |
| `blob_attributes` | Image classification results (Type Router + NIMA scores) |
| `ocr_results` | Extracted text from documents/images |
| `search_queries` | Search history and analytics |
| `collections` | User-created groups of blobs |
| `collection_items` | Many-to-many relationship for collections |
| `processing_jobs` | Background job queue for async processing |

## Step 1: Create Supabase Project

1. Go to [https://supabase.com](https://supabase.com) and sign in
2. Click "New Project"
3. Choose your organization and fill in:
   - **Project Name**: `cbis-project` (or your choice)
   - **Database Password**: Generate a strong password and **save it**
   - **Region**: Choose closest to your location
4. Wait for the project to be created (~2 minutes)

## Step 2: Enable pgvector Extension

The CBIS project uses pgvector for vector similarity search.

1. In your Supabase dashboard, go to **Database** → **Extensions**
2. Search for `vector`
3. Enable the `vector` extension
4. Alternatively, run this SQL in the SQL Editor:
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```

## Step 3: Configure Environment Variables

1. In Supabase dashboard, go to **Settings** → **Database**
2. Find the **Connection String** section
3. Copy the **URI** connection string (not the pooler)
4. Update your `.env` file:

```env
# Replace [YOUR-PASSWORD] with your actual database password
# Replace [YOUR-PROJECT-REF] with your project reference (e.g., abcdefghijk)
DATABASE_URL="postgresql://postgres:[YOUR-PASSWORD]@db.[YOUR-PROJECT-REF].supabase.co:5432/postgres"
```

**Example:**
```env
DATABASE_URL="postgresql://postgres:MyS3cureP@ss@db.abcdefghijk.supabase.co:5432/postgres"
```

## Step 4: Install Dependencies

```bash
cd E:\programming\CBIS_Project\next-js
npm install @prisma/client
npm install -D prisma
```

## Step 5: Generate Prisma Client

```bash
npx prisma generate
```

This will generate the Prisma Client in `lib/generated/prisma/`.

## Step 6: Push Schema to Database

For initial setup, you can use `prisma db push`:

```bash
npx prisma db push
```

Or create a migration (recommended for production):

```bash
npx prisma migrate dev --name init
```

This will:
- Create all tables in your Supabase database
- Create the vector extension
- Set up all indexes and relationships

## Step 7: Verify Setup

1. Check Prisma Studio:
   ```bash
   npx prisma studio
   ```
   This opens a browser UI to view your database.

2. Verify in Supabase:
   - Go to **Database** → **Tables**
   - You should see all 8 tables listed

3. Test a query:
   ```bash
   npx prisma db execute --stdin <<< "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';"
   ```

## Schema Features

### Vector Embeddings
- **512-dimensional vectors** for CLIP embeddings
- Uses `pgvector` extension for similarity search
- Supports cosine similarity, L2 distance, and inner product

### Long Text Support
- OCR results use `@db.Text` for unlimited length
- Supports full document text extraction
- Can store structured OCR data (bounding boxes, confidence scores)

### Blob Metadata
- Comprehensive file metadata (size, dimensions, mime type)
- Processing status tracking
- Thumbnail path storage
- Upload metadata (user, IP, timestamp)

### Image Attributes
- Type classification (document, people, screenshot, animal)
- Confidence probabilities for each classification
- NIMA aesthetic scores (technical, aesthetic, overall)
- Score distributions stored as JSON

### Search & Analytics
- Search query history
- Performance metrics (search time, result count)
- User session tracking
- Filter application tracking

## Usage Examples

### Insert a New Blob

```typescript
import { PrismaClient } from './lib/generated/prisma';

const prisma = new PrismaClient();

const blob = await prisma.blob.create({
  data: {
    filename: 'image-123.jpg',
    originalName: 'my-photo.jpg',
    mimeType: 'image/jpeg',
    size: 1024000,
    width: 1920,
    height: 1080,
    storagePath: 'storage/blobs/image-123.jpg',
    processingStatus: 'pending'
  }
});
```

### Store CLIP Embedding

```typescript
// Note: Vector insertion requires raw SQL for now
await prisma.$executeRaw`
  INSERT INTO embeddings (id, "blobId", vector, caption, "modelName", device)
  VALUES (
    ${embeddingId},
    ${blobId},
    ${embedding}::vector(512),
    ${caption},
    'openai/clip-vit-base-patch32',
    'cuda'
  )
`;
```

### Vector Similarity Search

```typescript
// Find similar images using cosine similarity
const similar = await prisma.$queryRaw`
  SELECT 
    b.id, 
    b.filename,
    e.caption,
    1 - (e.vector <=> ${queryVector}::vector(512)) as similarity
  FROM embeddings e
  JOIN blobs b ON b.id = e."blobId"
  ORDER BY e.vector <=> ${queryVector}::vector(512)
  LIMIT 20
`;
```

### Search with Filters

```typescript
const results = await prisma.blob.findMany({
  where: {
    attributes: {
      isDocument: true,
      nimaScore: { gte: 5.0 }
    },
    processingStatus: 'completed'
  },
  include: {
    embeddings: true,
    attributes: true,
    ocrResults: true
  },
  orderBy: {
    createdAt: 'desc'
  },
  take: 20
});
```

### Store OCR Results

```typescript
await prisma.oCRResult.create({
  data: {
    blobId: blob.id,
    text: extractedText,
    language: 'en',
    confidence: 0.95,
    engine: 'paddleocr',
    processingTime: 1.23
  }
});
```

## Maintenance

### Backup Database

```bash
# Export schema
npx prisma db pull

# Create migration
npx prisma migrate dev --name backup
```

### View Database

```bash
# Open Prisma Studio
npx prisma studio
```

### Reset Database (⚠️ Destructive)

```bash
# Only for development!
npx prisma migrate reset
```

## Troubleshooting

### Error: "Extension vector is not available"
**Solution:** Enable pgvector extension in Supabase dashboard or run:
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

### Error: "P1001: Can't reach database server"
**Solution:** 
- Check your internet connection
- Verify DATABASE_URL is correct
- Ensure Supabase project is active
- Check firewall settings

### Error: "relation does not exist"
**Solution:** Run `npx prisma db push` to create tables

### Slow Vector Queries
**Solution:** Create an index on the vector column:
```sql
CREATE INDEX ON embeddings USING ivfflat (vector vector_cosine_ops)
WITH (lists = 100);
```

## Next Steps

1. ✅ Set up database schema
2. ✅ Enable pgvector extension
3. 🔲 Implement blob upload API with database insertion
4. 🔲 Create vector search API endpoint
5. 🔲 Add OCR results storage
6. 🔲 Implement collections feature
7. 🔲 Set up background job processing

## Resources

- [Prisma Documentation](https://www.prisma.io/docs)
- [Supabase Documentation](https://supabase.com/docs)
- [pgvector GitHub](https://github.com/pgvector/pgvector)
- [CLIP Model](https://github.com/openai/CLIP)
