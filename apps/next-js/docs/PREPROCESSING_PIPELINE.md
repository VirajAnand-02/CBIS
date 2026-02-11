# CBIS Preprocessing Pipeline

## Overview

The preprocessing pipeline automatically processes uploaded images through multiple AI services:

1. **CLIP Service** - Generates embeddings and captions
2. **Type Router** - Classifies image types (document, faces, screenshot, animal)
3. **Specialized Modules** - Processes images based on detected types (e.g., OCR for documents, face detection for people)

## Architecture

```
Image Upload → Blob Storage → Preprocessing Pipeline
                                     ↓
                              ┌──────┴──────┐
                              │  CLIP (8000) │
                              └──────┬──────┘
                                     ↓
                              ┌──────┴──────┐
                              │Type Router   │
                              │   (8001)     │
                              └──────┬──────┘
                                     ↓
                     ┌───────────────┼───────────────┐
                     ↓               ↓               ↓
              ┌──────────┐   ┌──────────┐   ┌──────────┐
              │ Document │   │   Face   │   │  Other   │
              │  Module  │   │  Module  │   │ Modules  │
              └──────────┘   └──────────┘   └──────────┘
                     ↓               ↓               ↓
                     └───────────────┼───────────────┘
                                     ↓
                            Final JSON Result
```

## Services Setup

### 1. CLIP Service (Port 8000)

**Location:** `E:\programming\CBIS_Project\clip\`

**Start:**
```bash
cd E:\programming\CBIS_Project\clip
python -m uvicorn app:app --host 0.0.0.0 --port 8000
```

**Test:**
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/process/url" `
  -Method POST `
  -Headers @{ "Content-Type" = "application/json" } `
  -Body '{"url":"http://localhost:3000/api/blobs/YOUR_BLOB_ID"}'
```

### 2. Type Router Service (Port 8001)

**Location:** `E:\programming\CBIS_Project\TYPE_ROUTER\`

**Start:**
```bash
cd E:\programming\CBIS_Project\TYPE_ROUTER
python type_router_service.py
```

**Test:**
```powershell
Invoke-RestMethod -Uri "http://localhost:8001/classify_from_image" `
  -Method POST `
  -Headers @{ "Content-Type" = "application/json" } `
  -Body '{"url":"http://localhost:3000/api/blobs/YOUR_BLOB_ID"}'
```

### 3. Next.js Application (Port 3000)

**Location:** `E:\programming\CBIS_Project\next-js\`

**Start:**
```bash
cd E:\programming\CBIS_Project\next-js
npm run dev
```

## How It Works

### 1. Upload Process

When a user uploads an image:
- Image is saved to `storage/blobs/` with metadata
- Blob API triggers preprocessing pipeline
- Sidebar shows "Processing - X" counter

### 2. Preprocessing Pipeline

**Step 1: CLIP Processing**
- Sends image URL to CLIP service
- Receives 512-dimensional embedding vector
- Receives natural language caption
- Logs processing time

**Step 2: Type Classification**
- Sends image to Type Router
- Receives boolean flags for each type:
  - `is_document`
  - `has_people`
  - `is_screenshot`
  - `is_animal`

**Step 3: Specialized Processing (Parallel)**
- If `is_document`: Calls OCR/document module
- If `has_people`: Calls face detection module
- Other modules activated based on types
- All modules run in parallel for speed

**Step 4: Result Storage**
- Compiles all results into JSON
- Saves to `storage/blobs/{blobId}.processing.json`
- Logs completion and timing

### 3. Real-Time Updates

- Frontend connects via Server-Sent Events (SSE)
- Receives instant updates when jobs start/complete
- Sidebar updates automatically

## File Structure

```
storage/blobs/
├── {blobId}.jpg               # Original image
├── {blobId}.meta.json         # Upload metadata
├── {blobId}.processing.json   # AI processing results
└── thumbnails/
    └── {blobId}.jpg           # Thumbnail image
```

## Processing Result Format

```json
{
  "blobId": "abc123...",
  "filename": "image.jpg",
  "clip": {
    "embedding": [0.123, -0.456, ...],
    "caption": "a photo of a cat",
    "device": "cpu",
    "times": {
      "embedding_s": 0.124,
      "caption_s": 2.227
    }
  },
  "types": {
    "is_document": false,
    "has_people": false,
    "is_screenshot": false,
    "is_animal": true
  },
  "moduleResults": {
    "faces": { "count": 0 },
    "document": { "status": "not_implemented" }
  },
  "processingTime": 3456,
  "completedAt": "2025-11-01T10:30:45.123Z"
}
```

## Environment Variables

Create `.env.local` in `next-js/` folder:

```bash
NEXT_PUBLIC_BASE_URL=http://localhost:3000
CLIP_SERVICE_URL=http://localhost:8000
TYPE_ROUTER_SERVICE_URL=http://localhost:8001
```

## Adding New Modules

To add a new specialized processing module:

1. Create your service (e.g., OCR, object detection)
2. Add call method in `lib/preprocessing-manager.ts`:

```typescript
private async callYourModule(fileUrl: string): Promise<unknown> {
  const response = await fetch('http://localhost:8002/process', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url: fileUrl }),
  });
  return response.json();
}
```

3. Add to `callSpecializedModules()`:

```typescript
if (types.your_type) {
  promises.push(
    this.callYourModule(fileUrl).then((result) => {
      results.yourModule = result;
    })
  );
}
```

## Monitoring

### Logs
- Frontend: Browser console for SSE connection status
- Backend: Next.js terminal for pipeline logs
- CLIP: Service terminal for embedding/caption logs
- Type Router: Service terminal for classification logs

### Pipeline Logs Format
```
[Preprocessing] Started job job-1234567890-abc123 for blob xyz789 (image.jpg)
[Pipeline job-1234567890-abc123] Step 1: Calling CLIP service...
[Pipeline job-1234567890-abc123] ✓ CLIP completed in 2.35s
[Pipeline job-1234567890-abc123] Caption: "a white cat sitting on a couch"
[Pipeline job-1234567890-abc123] Step 2: Calling Type Router...
[Pipeline job-1234567890-abc123] ✓ Type Router completed
[Pipeline job-1234567890-abc123] Types: { is_animal: true, ... }
[Pipeline job-1234567890-abc123] Step 3: Calling specialized modules...
[Pipeline job-1234567890-abc123] ✓ Specialized modules completed
[Pipeline job-1234567890-abc123] Total processing time: 3456ms
[Preprocessing] ✅ Successfully completed job job-1234567890-abc123
```

## Troubleshooting

### Services Not Connecting
1. Check all services are running (ports 3000, 8000, 8001)
2. Verify `.env.local` has correct URLs
3. Check firewall/antivirus isn't blocking ports

### Processing Stuck
1. Check service logs for errors
2. Verify blob URL is accessible
3. Restart stuck service

### SSE Not Updating
1. Check browser console for EventSource errors
2. Verify SSE endpoint: `http://localhost:3000/api/preprocessing/status`
3. Try refresh browser

## Future Enhancements

- [ ] OCR module for documents
- [ ] Face detection/recognition module
- [ ] Object detection module
- [ ] Scene classification
- [ ] Quality assessment
- [ ] Duplicate detection
- [ ] Database storage (replace JSON files)
- [ ] Result caching
- [ ] Processing queue persistence
- [ ] Webhook notifications
- [ ] Processing history UI

