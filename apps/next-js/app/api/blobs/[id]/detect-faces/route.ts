// app/api/blobs/[id]/detect-faces/route.ts
// API endpoint to trigger face detection for an uploaded image

import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/db';

// Type for face instance from database
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

const FACE_DETECTION_SERVICE_URL = process.env.FACE_DETECTION_SERVICE_URL || 'http://localhost:8005';

export async function POST(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  const blobId = params.id;

  try {
    // Get blob info from database
    const blob = await prisma.blob.findUnique({
      where: { id: blobId },
      select: {
        id: true,
        storagePath: true,
        mimeType: true,
        processingStatus: true
      }
    });

    if (!blob) {
      return NextResponse.json(
        { error: 'Blob not found' },
        { status: 404 }
      );
    }

    // Check if it's an image
    if (!blob.mimeType.startsWith('image/')) {
      return NextResponse.json(
        { error: 'Blob is not an image' },
        { status: 400 }
      );
    }

    // Get priority from request body (optional)
    const body = await request.json().catch(() => ({}));
    const priority = body.priority || 5;

    // Call face detection service
    const response = await fetch(`${FACE_DETECTION_SERVICE_URL}/detect`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        blob_id: blobId,
        file_path: blob.storagePath,
        priority: priority
      })
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Face detection service error');
    }

    const result = await response.json();

    // Update blob processing status
    await prisma.blob.update({
      where: { id: blobId },
      data: {
        processingStatus: 'processing'
      }
    });

    return NextResponse.json({
      success: true,
      task_id: result.task_id,
      status: result.status,
      message: result.message,
      queue_position: result.queue_position
    });

  } catch (error) {
    console.error('Face detection error:', error);
    const errorMessage = error instanceof Error ? error.message : 'Failed to trigger face detection';
    return NextResponse.json(
      { error: errorMessage },
      { status: 500 }
    );
  }
}

// GET endpoint to check face detection results
export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  const blobId = params.id;

  try {
    // Get all detected faces for this blob
    const faces = await prisma.faceInstance.findMany({
      where: { blobId },
      include: {
        person: {
          select: {
            id: true,
            name: true,
            faceCount: true
          }
        }
      },
      orderBy: {
        confidence: 'desc'
      }
    });

    // Get blob info
    const blob = await prisma.blob.findUnique({
      where: { id: blobId },
      select: {
        id: true,
        filename: true,
        width: true,
        height: true
      }
    });

    return NextResponse.json({
      blob,
      faces_detected: faces.length,
      faces: faces.map((face: FaceWithPerson) => ({
        id: face.id,
        bounding_box: face.boundingBox,
        confidence: face.confidence,
        quality: face.quality,
        person: face.person ? {
          id: face.person.id,
          name: face.person.name,
          total_faces: face.person.faceCount
        } : null
      }))
    });

  } catch (error) {
    console.error('Error fetching face detection results:', error);
    const errorMessage = error instanceof Error ? error.message : 'Failed to fetch results';
    return NextResponse.json(
      { error: errorMessage },
      { status: 500 }
    );
  }
}
