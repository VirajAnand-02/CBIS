import { NextRequest, NextResponse } from 'next/server';
import db from '@/lib/db';

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ personId: string }> }
) {
  try {
    const { personId } = await params;

    const faces = await db.faceInstance.findMany({
      where: { personId },
      orderBy: { createdAt: 'desc' },
    });

    return NextResponse.json({ 
      faces,
      count: faces.length 
    });
  } catch (error) {
    console.error('Error fetching face instances:', error);
    return NextResponse.json(
      { error: 'Failed to fetch face instances' },
      { status: 500 }
    );
  }
}
