// app/api/faces/search/route.ts
// API endpoint for face similarity search using pgvector

import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/db';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { embedding, threshold = 0.4, limit = 1 } = body;

    if (!embedding || !Array.isArray(embedding)) {
      return NextResponse.json(
        { error: 'Invalid embedding format' },
        { status: 400 }
      );
    }

    // Convert embedding array to pgvector format
    const embeddingStr = '[' + embedding.join(',') + ']';

    // Find similar faces using pgvector cosine distance
    // cosine distance: 1 - cosine similarity
    const similarFaces = await prisma.$queryRawUnsafe<Array<{
      id: string;
      personId: string;
      similarity: number;
    }>>(`
      SELECT 
        fi.id,
        fi."personId",
        1 - (fi.embedding <=> $1::vector) as similarity
      FROM face_instances fi
      WHERE fi."personId" IS NOT NULL
        AND fi.embedding IS NOT NULL
        AND (1 - (fi.embedding <=> $1::vector)) >= $2
      ORDER BY fi.embedding <=> $1::vector
      LIMIT $3
    `, embeddingStr, 1 - threshold, limit);

    // Return matches
    const matches = similarFaces.map((face) => ({
      faceId: face.id,
      personId: face.personId,
      similarity: face.similarity
    }));

    return NextResponse.json({ matches });

  } catch (error) {
    console.error('Face search error:', error);
    const errorMessage = error instanceof Error ? error.message : 'Face search failed';
    return NextResponse.json(
      { error: errorMessage },
      { status: 500 }
    );
  }
}
