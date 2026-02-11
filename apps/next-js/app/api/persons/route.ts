// app/api/persons/route.ts
// API endpoint for creating persons

import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/db';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { name, notes, tags, thumbnail } = body;

    const person = await prisma.person.create({
      data: {
        name: name || null,
        notes: notes || null,
        tags: tags || [],
        thumbnail: thumbnail || null,
        faceCount: 0
      }
    });

    return NextResponse.json({ id: person.id, name: person.name });

  } catch (error) {
    console.error('Create person error:', error);
    const errorMessage = error instanceof Error ? error.message : 'Failed to create person';
    return NextResponse.json(
      { error: errorMessage },
      { status: 500 }
    );
  }
}

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const limit = parseInt(searchParams.get('limit') || '50');
    const offset = parseInt(searchParams.get('offset') || '0');

    const persons = await prisma.person.findMany({
      take: limit,
      skip: offset,
      orderBy: { faceCount: 'desc' },
      include: {
        _count: {
          select: { faces: true }
        }
      }
    });

    return NextResponse.json({ persons });

  } catch (error) {
    console.error('Get persons error:', error);
    const errorMessage = error instanceof Error ? error.message : 'Failed to get persons';
    return NextResponse.json(
      { error: errorMessage },
      { status: 500 }
    );
  }
}
