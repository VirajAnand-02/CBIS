import { NextRequest, NextResponse } from 'next/server';
import db from '@/lib/db';

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ personId: string }> }
) {
  try {
    const { personId } = await params;

    const person = await db.person.findUnique({
      where: { id: personId },
    });

    if (!person) {
      return NextResponse.json(
        { error: 'Person not found' },
        { status: 404 }
      );
    }

    return NextResponse.json(person);
  } catch (error) {
    console.error('Error fetching person:', error);
    return NextResponse.json(
      { error: 'Failed to fetch person' },
      { status: 500 }
    );
  }
}

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ personId: string }> }
) {
  try {
    const { personId } = await params;
    const body = await request.json();
    const { name, notes, tags, thumbnail } = body;

    const updateData: {
      name?: string;
      notes?: string | null;
      tags?: string[];
      thumbnail?: string | null;
    } = {};
    if (name !== undefined) updateData.name = name;
    if (notes !== undefined) updateData.notes = notes;
    if (tags !== undefined) updateData.tags = tags;
    if (thumbnail !== undefined) updateData.thumbnail = thumbnail;

    const updatedPerson = await db.person.update({
      where: { id: personId },
      data: updateData,
    });

    return NextResponse.json(updatedPerson);
  } catch (error) {
    console.error('Error updating person:', error);
    return NextResponse.json(
      { error: 'Failed to update person' },
      { status: 500 }
    );
  }
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ personId: string }> }
) {
  try {
    const { personId } = await params;

    // Delete all face instances first (cascade should handle this, but being explicit)
    await db.faceInstance.deleteMany({
      where: { personId },
    });

    // Delete the person
    await db.person.delete({
      where: { id: personId },
    });

    return NextResponse.json({ success: true });
  } catch (error) {
    console.error('Error deleting person:', error);
    return NextResponse.json(
      { error: 'Failed to delete person' },
      { status: 500 }
    );
  }
}
