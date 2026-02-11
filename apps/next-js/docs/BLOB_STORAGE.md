# Blob Storage System

A complete blob storage implementation for Next.js with file and folder upload capabilities.

## Features

- ✅ **File Upload**: Upload single or multiple files
- ✅ **Folder Upload**: Upload entire folder structures
- ✅ **Range Support**: HTTP range requests for streaming large files
- ✅ **Metadata Storage**: Stores file metadata (name, size, mime type, upload date)
- ✅ **Delete Support**: Remove uploaded blobs
- ✅ **Modern UI**: Beautiful upload modal with progress tracking

## File Structure

```
next-js/
├── app/
│   └── api/
│       └── blobs/
│           ├── route.ts           # POST (upload) & GET (list)
│           └── [id]/
│               └── route.ts       # GET (download), HEAD (meta), DELETE
├── components/
│   └── upload-modal.tsx          # Upload modal component
├── storage/
│   └── blobs/                    # File storage (in .gitignore)
└── types/
    └── html-attributes.d.ts      # TypeScript types for folder upload
```

## API Endpoints

### POST `/api/blobs`
Upload a file to blob storage.

**Request:**
- Method: `POST`
- Content-Type: `multipart/form-data`
- Body: FormData with `file` field

**Response:**
```json
{
  "message": "uploaded",
  "id": "abc123def456...",
  "meta": {
    "id": "abc123def456...",
    "filename": "example.jpg",
    "storageFilename": "abc123def456.jpg",
    "size": 123456,
    "mimeType": "image/jpeg",
    "uploadedAt": "2024-10-31T12:00:00.000Z"
  }
}
```

### GET `/api/blobs`
List all uploaded blobs.

**Response:**
```json
{
  "count": 2,
  "items": [
    {
      "id": "abc123def456...",
      "filename": "example.jpg",
      "storageFilename": "abc123def456.jpg",
      "size": 123456,
      "mimeType": "image/jpeg",
      "uploadedAt": "2024-10-31T12:00:00.000Z"
    }
  ]
}
```

### GET `/api/blobs/[id]`
Download a blob file. Supports HTTP range requests for streaming.

**Headers:**
- `Range: bytes=0-1023` (optional) - Request partial content

**Response:**
- Status: 200 (full file) or 206 (partial content)
- Headers: Content-Type, Content-Length, Accept-Ranges
- Body: File content

### HEAD `/api/blobs/[id]`
Get blob metadata without downloading.

**Response:**
- Status: 200
- Headers: Content-Type, Content-Length, Accept-Ranges

### DELETE `/api/blobs/[id]`
Delete a blob and its metadata.

**Response:**
- Status: 204 (success)

## Usage

### In Your Component

```tsx
import { useState } from "react";
import { UploadModal } from "@/components/upload-modal";

export default function MyPage() {
  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  const [uploadMode, setUploadMode] = useState<"file" | "folder">("file");

  const handleUploadComplete = (ids: string[]) => {
    console.log("Uploaded blob IDs:", ids);
    // Refresh your media list or update state
  };

  return (
    <>
      <button onClick={() => {
        setUploadMode("file");
        setUploadModalOpen(true);
      }}>
        Upload Files
      </button>

      <button onClick={() => {
        setUploadMode("folder");
        setUploadModalOpen(true);
      }}>
        Upload Folder
      </button>

      <UploadModal
        open={uploadModalOpen}
        onOpenChange={setUploadModalOpen}
        mode={uploadMode}
        onUploadComplete={handleUploadComplete}
      />
    </>
  );
}
```

### Direct API Usage

```typescript
// Upload a file
const formData = new FormData();
formData.append("file", file);

const response = await fetch("/api/blobs", {
  method: "POST",
  body: formData,
});

const result = await response.json();
console.log("Blob ID:", result.id);

// List all blobs
const listResponse = await fetch("/api/blobs");
const { items } = await listResponse.json();

// Download a blob
window.open(`/api/blobs/${blobId}`, "_blank");

// Delete a blob
await fetch(`/api/blobs/${blobId}`, {
  method: "DELETE",
});
```

## Storage

Files are stored in `storage/blobs/` with the following structure:

```
storage/blobs/
├── abc123def456.jpg          # Actual file with ID + extension
├── abc123def456.meta.json    # Metadata file
├── xyz789ghi012.pdf
└── xyz789ghi012.meta.json
```

The `storage/` directory is automatically added to `.gitignore`.

## Features in Upload Modal

- **Drag & Drop** (coming soon - currently click to browse)
- **Multiple Files**: Select multiple files at once
- **Folder Upload**: Upload entire folder structures
- **Progress Tracking**: Visual progress for each file
- **Error Handling**: Shows errors for failed uploads
- **Success Indicators**: Green checkmarks for successful uploads
- **Remove Files**: Remove files from queue before upload
- **Status Display**: Shows pending, uploading, success, and error states

## Security Considerations

⚠️ **Production Recommendations:**

1. **Add Authentication**: Protect upload/delete endpoints
2. **File Validation**: Validate file types and sizes
3. **Rate Limiting**: Prevent abuse
4. **Virus Scanning**: Scan uploaded files
5. **Storage Limits**: Implement per-user storage quotas
6. **CORS**: Configure CORS if needed

## Next Steps

1. Connect blob storage to your media grid
2. Add thumbnail generation for images
3. Implement search/filter for uploaded files
4. Add batch operations (delete multiple files)
5. Create public/private file permissions
