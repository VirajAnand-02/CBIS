// app/api/faces/route.ts
// API endpoint for creating face instances

import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/db';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const {
      blobId,
      personId,
      boundingBox,
      embedding,
      confidence,
      quality,
      detectorModel = 'retinaface',
      embeddingModel = 'arcface'
    } = body;

    // Validate required fields
    if (!blobId || !personId || !boundingBox || !embedding) {
      return NextResponse.json(
        { error: 'Missing required fields' },
        { status: 400 }
      );
    }

    // Convert embedding array to pgvector format
    const embeddingStr = '[' + embedding.join(',') + ']';

    // Create face instance using raw SQL to handle vector type
    const result = await prisma.$queryRawUnsafe<Array<{ id: string }>>(`
      INSERT INTO face_instances (
        id, "blobId", "personId", "boundingBox", embedding,
        confidence, quality, "detectorModel", "embeddingModel",
        "createdAt", "updatedAt"
      )
      VALUES (
        gen_random_uuid(), $1, $2, $3::jsonb, $4::vector,
        $5, $6, $7, $8, NOW(), NOW()
      )
      RETURNING id
    `, blobId, personId, JSON.stringify(boundingBox), embeddingStr,
       confidence, quality, detectorModel, embeddingModel);

    const faceId = result[0].id;

    // Update person face count
    await prisma.person.update({
      where: { id: personId },
      data: {
        faceCount: { increment: 1 },
        updatedAt: new Date()
      }
    });

    return NextResponse.json({ id: faceId });

  } catch (error) {
    console.error('Create face instance error:', error);
    const errorMessage = error instanceof Error ? error.message : 'Failed to create face instance';
    return NextResponse.json(
      { error: errorMessage },
      { status: 500 }
    );
  }
}
