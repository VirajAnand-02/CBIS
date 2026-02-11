# Face Detection and Recognition Implementation Guide

## Overview

This guide explains how to implement face detection and person recognition using ArcFace embeddings in the CBIS project.

## Database Schema

### `FaceInstance` Table
Stores individual detected faces from images:
- **One image** can have **multiple faces**
- Each face has:
  - Bounding box coordinates
  - ArcFace embedding (512-dim vector)
  - Quality metrics
  - Optional link to a `Person`

### `Person` Table
Represents unique individuals:
- **One person** can appear in **multiple images**
- Stores:
  - Optional name/label
  - Metadata and tags
  - Count of face instances

## Implementation Steps

### 1. Face Detection Service

Create a new Python microservice for face detection:

```python
# face_detection_service.py
import cv2
import numpy as np
from insightface.app import FaceAnalysis
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict

app = FastAPI(title="Face Detection & Recognition API")

# Initialize InsightFace (includes RetinaFace + ArcFace)
face_analyzer = FaceAnalysis(providers=['CUDAExecutionProvider', 'CPUExecutionProvider'])
face_analyzer.prepare(ctx_id=0, det_size=(640, 640))

class FaceDetectionRequest(BaseModel):
    url: str  # Image URL
    min_confidence: float = 0.5
    min_face_size: int = 20  # minimum face size in pixels

class DetectedFace(BaseModel):
    bounding_box: Dict[str, float]  # {x, y, width, height}
    confidence: float
    embedding: List[float]  # 512-dim ArcFace embedding
    quality: float
    landmarks: List[List[float]]  # facial landmarks (eyes, nose, mouth)

class FaceDetectionResponse(BaseModel):
    faces: List[DetectedFace]
    image_width: int
    image_height: int
    face_count: int

@app.post("/detect", response_model=FaceDetectionResponse)
async def detect_faces(request: FaceDetectionRequest):
    """
    Detect faces in image and extract ArcFace embeddings
    """
    import requests
    from io import BytesIO
    from PIL import Image
    
    try:
        # Download image
        response = requests.get(request.url, timeout=15)
        img = Image.open(BytesIO(response.content)).convert('RGB')
        img_array = np.array(img)
        
        # Detect faces
        faces = face_analyzer.get(img_array)
        
        detected_faces = []
        for face in faces:
            # Filter by confidence and size
            if face.det_score < request.min_confidence:
                continue
            
            bbox = face.bbox.astype(int)
            face_width = bbox[2] - bbox[0]
            face_height = bbox[3] - bbox[1]
            
            if face_width < request.min_face_size or face_height < request.min_face_size:
                continue
            
            # Normalize bounding box to 0-1
            normalized_bbox = {
                "x": float(bbox[0]) / img.width,
                "y": float(bbox[1]) / img.height,
                "width": float(face_width) / img.width,
                "height": float(face_height) / img.height
            }
            
            # Extract embedding (ArcFace)
            embedding = face.normed_embedding.tolist()
            
            # Calculate quality score
            quality = calculate_face_quality(face)
            
            detected_faces.append(DetectedFace(
                bounding_box=normalized_bbox,
                confidence=float(face.det_score),
                embedding=embedding,
                quality=quality,
                landmarks=face.landmark_2d_106.tolist() if hasattr(face, 'landmark_2d_106') else []
            ))
        
        return FaceDetectionResponse(
            faces=detected_faces,
            image_width=img.width,
            image_height=img.height,
            face_count=len(detected_faces)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def calculate_face_quality(face) -> float:
    """
    Calculate face quality score based on:
    - Pose (frontal faces = higher quality)
    - Size (larger faces = higher quality)
    - Landmarks visibility
    """
    # Implement quality calculation
    # This is a simplified version
    pose_quality = 1.0 - (abs(face.pose[0]) + abs(face.pose[1])) / 180.0
    return max(0.0, min(1.0, pose_quality))

@app.post("/match")
async def match_face(embedding: List[float], threshold: float = 0.4):
    """
    Find matching person for a face embedding
    This would query the database for similar embeddings
    """
    # Implementation depends on your database setup
    # Use pgvector for similarity search
    pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8005)
```

### 2. Database Integration

Update your Next.js API to store face data:

```typescript
// app/api/blobs/[id]/detect-faces/route.ts
import { NextRequest, NextResponse } from 'next/server';
import { createFaceInstance } from '@/lib/db';

export async function POST(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  const blobId = params.id;
  
  try {
    // Call face detection service
    const response = await fetch('http://localhost:8005/detect', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        url: `http://localhost:3000/api/blobs/${blobId}`,
        min_confidence: 0.6
      })
    });
    
    const result = await response.json();
    
    // Store each detected face
    const faceInstances = await Promise.all(
      result.faces.map(face => 
        createFaceInstance({
          blobId,
          boundingBox: face.bounding_box,
          embedding: face.embedding,
          confidence: face.confidence,
          quality: face.quality,
          detectorModel: 'retinaface',
          embeddingModel: 'arcface'
        })
      )
    );
    
    return NextResponse.json({
      success: true,
      faces_detected: result.face_count,
      face_instances: faceInstances
    });
    
  } catch (error) {
    return NextResponse.json(
      { error: 'Face detection failed' },
      { status: 500 }
    );
  }
}
```

### 3. Person Matching with ArcFace

```typescript
// lib/face-recognition.ts
import { prisma } from '@/lib/db';

/**
 * Find person by face embedding using cosine similarity
 * ArcFace embeddings are normalized, so cosine similarity = dot product
 */
export async function findMatchingPerson(
  embedding: number[],
  threshold: number = 0.4 // ArcFace threshold (higher = more strict)
) {
  // Use pgvector for efficient similarity search
  const result = await prisma.$queryRaw`
    SELECT 
      fi."personId",
      p.name,
      1 - (fi.embedding <=> ${embedding}::vector) as similarity
    FROM face_instances fi
    LEFT JOIN persons p ON fi."personId" = p.id
    WHERE fi."personId" IS NOT NULL
      AND 1 - (fi.embedding <=> ${embedding}::vector) >= ${threshold}
    ORDER BY similarity DESC
    LIMIT 1
  `;
  
  return result[0] || null;
}

/**
 * Cluster unknown faces and create new persons
 * Groups similar faces together using DBSCAN or HDBSCAN
 */
export async function clusterUnknownFaces(threshold: number = 0.4) {
  // Get all faces without person assignment
  const unknownFaces = await prisma.$queryRaw`
    SELECT id, embedding
    FROM face_instances
    WHERE "personId" IS NULL
    ORDER BY "createdAt" DESC
  `;
  
  // Implement clustering algorithm (DBSCAN/HDBSCAN)
  // This would be done in Python service
  const clusters = await clusterFaceEmbeddings(unknownFaces, threshold);
  
  // Create Person for each cluster
  for (const cluster of clusters) {
    const person = await prisma.person.create({
      data: {
        faceCount: cluster.faceIds.length
      }
    });
    
    // Assign faces to person
    await prisma.faceInstance.updateMany({
      where: { id: { in: cluster.faceIds } },
      data: { personId: person.id }
    });
  }
}

/**
 * Search for images containing a specific person
 */
export async function searchImagesByPerson(
  personId: string,
  limit: number = 50
) {
  const images = await prisma.blob.findMany({
    where: {
      faces: {
        some: {
          personId: personId
        }
      }
    },
    include: {
      faces: {
        where: { personId: personId },
        select: {
          id: true,
          boundingBox: true,
          confidence: true
        }
      }
    },
    take: limit,
    orderBy: {
      createdAt: 'desc'
    }
  });
  
  return images;
}

/**
 * Find similar faces across all images (even without person assignment)
 */
export async function findSimilarFaces(
  faceInstanceId: string,
  threshold: number = 0.3,
  limit: number = 20
) {
  // Get the reference face embedding
  const referenceFace = await prisma.faceInstance.findUnique({
    where: { id: faceInstanceId },
    select: { embedding: true }
  });
  
  if (!referenceFace) return [];
  
  // Find similar faces using pgvector
  const similarFaces = await prisma.$queryRaw`
    SELECT 
      fi.*,
      b.filename,
      b."storagePath",
      1 - (fi.embedding <=> ${referenceFace.embedding}::vector) as similarity
    FROM face_instances fi
    JOIN blobs b ON fi."blobId" = b.id
    WHERE fi.id != ${faceInstanceId}
      AND 1 - (fi.embedding <=> ${referenceFace.embedding}::vector) >= ${threshold}
    ORDER BY similarity DESC
    LIMIT ${limit}
  `;
  
  return similarFaces;
}
```

### 4. Person Management UI

```typescript
// app/persons/page.tsx
'use client';

import { useState, useEffect } from 'react';
import { Person } from '@/lib/db';

export default function PersonsPage() {
  const [persons, setPersons] = useState<Person[]>([]);
  
  useEffect(() => {
    fetchPersons();
  }, []);
  
  const fetchPersons = async () => {
    const response = await fetch('/api/persons');
    const data = await response.json();
    setPersons(data.persons);
  };
  
  const assignName = async (personId: string, name: string) => {
    await fetch(`/api/persons/${personId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name })
    });
    fetchPersons();
  };
  
  const mergPersons = async (sourceId: string, targetId: string) => {
    await fetch('/api/persons/merge', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sourceId, targetId })
    });
    fetchPersons();
  };
  
  return (
    <div>
      <h1>People ({persons.length})</h1>
      
      {persons.map(person => (
        <div key={person.id}>
          <input
            type="text"
            value={person.name || 'Unknown'}
            onChange={(e) => assignName(person.id, e.target.value)}
            placeholder="Enter name..."
          />
          <span>{person.faceCount} faces</span>
          {/* Display thumbnail grid of faces */}
        </div>
      ))}
    </div>
  );
}
```

## Processing Pipeline

1. **Upload Image** → Store in blob storage
2. **Detect Faces** → Call face detection service
3. **Extract Embeddings** → ArcFace generates 512-dim vectors
4. **Match Person** → Search for similar faces in database
   - If match found (similarity > threshold): Assign to existing person
   - If no match: Leave unassigned for clustering
5. **Periodic Clustering** → Group unknown faces into new persons
6. **Manual Review** → User assigns names and merges persons

## Search Capabilities

### 1. Find images with specific person
```sql
SELECT * FROM blobs
WHERE id IN (
  SELECT "blobId" FROM face_instances
  WHERE "personId" = 'person-uuid'
);
```

### 2. Find images with multiple people
```sql
SELECT b.*, array_agg(DISTINCT fi."personId") as person_ids
FROM blobs b
JOIN face_instances fi ON b.id = fi."blobId"
WHERE fi."personId" IS NOT NULL
GROUP BY b.id
HAVING COUNT(DISTINCT fi."personId") >= 2;
```

### 3. Find similar faces (even unknown)
```sql
SELECT *, 1 - (embedding <=> $1::vector) as similarity
FROM face_instances
WHERE 1 - (embedding <=> $1::vector) >= 0.3
ORDER BY similarity DESC
LIMIT 20;
```

## ArcFace Thresholds

- **0.2-0.3**: Very loose matching (may have false positives)
- **0.4-0.5**: Recommended for person matching
- **0.6+**: Very strict (same person, different lighting/angle)

## Performance Optimization

1. **Create pgvector index** for fast similarity search:
```sql
CREATE INDEX face_embedding_idx ON face_instances 
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
```

2. **Filter by quality** before searching:
```sql
WHERE quality >= 0.6 AND confidence >= 0.7
```

3. **Batch processing** for large image collections
4. **Cache person thumbnails** for UI performance

## Dependencies

### Python Service
```bash
pip install insightface onnxruntime-gpu opencv-python fastapi uvicorn
```

### Database
- PostgreSQL with pgvector extension enabled
- Vector operations for similarity search

## Next Steps

1. ✅ Update schema (done)
2. Create face detection microservice (Python)
3. Add face detection API endpoint (Next.js)
4. Implement person matching logic
5. Build person management UI
6. Add face clustering for unknown faces
7. Create search interface for person-based queries

Would you like me to create the face detection microservice or help with any specific part of the implementation?
