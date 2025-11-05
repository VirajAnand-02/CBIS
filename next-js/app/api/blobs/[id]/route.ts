import { NextRequest, NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';
import { prisma } from '@/lib/db';

const STORAGE_DIR = path.join(process.cwd(), 'storage', 'blobs');

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;

  if (!id) {
    return NextResponse.json({ error: 'Missing id' }, { status: 400 });
  }

  try {
    // Get blob from database
    const blob = await prisma.blob.findUnique({
      where: { id },
      select: {
        filename: true,
        mimeType: true,
        size: true,
        originalName: true,
      },
    });

    if (!blob) {
      return NextResponse.json({ error: 'Not found' }, { status: 404 });
    }

    // Construct file path from database filename
    const fileOnDisk = path.join(STORAGE_DIR, blob.filename);
    
    if (!fs.existsSync(fileOnDisk)) {
      return NextResponse.json({ error: 'Blob file missing' }, { status: 404 });
    }
    
    const stat = fs.statSync(fileOnDisk);
    const total = stat.size;
    const range = req.headers.get('range');

    if (range) {
      const parts = /bytes=(\d*)-(\d*)/.exec(range);
      if (!parts) {
        return new NextResponse('Invalid Range', { status: 416 });
      }

      const start = parts[1] ? parseInt(parts[1], 10) : 0;
      const end = parts[2] ? parseInt(parts[2], 10) : total - 1;

      if (isNaN(start) || isNaN(end) || start > end || end >= total) {
        return new NextResponse('Requested Range Not Satisfiable', { status: 416 });
      }

      const chunk = fs.readFileSync(fileOnDisk, { encoding: null }).slice(start, end + 1);

      return new NextResponse(chunk, {
        status: 206,
        headers: {
          'Content-Range': `bytes ${start}-${end}/${total}`,
          'Content-Length': String(end - start + 1),
          'Content-Type': blob.mimeType || 'application/octet-stream',
          'Accept-Ranges': 'bytes',
        },
      });
    }

    const fileBuffer = fs.readFileSync(fileOnDisk);
    
    return new NextResponse(fileBuffer, {
      status: 200,
      headers: {
        'Content-Length': String(total),
        'Content-Type': blob.mimeType || 'application/octet-stream',
        'Accept-Ranges': 'bytes',
        'Content-Disposition': `inline; filename="${blob.originalName || blob.filename}"`,
      },
    });
  } catch (error) {
    console.error('[Blob GET] Error:', error);
    return NextResponse.json({ error: 'Failed to serve blob' }, { status: 500 });
  }
}

export async function HEAD(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;

  if (!id) {
    return new NextResponse(null, { status: 400 });
  }

  try {
    // Get blob from database
    const blob = await prisma.blob.findUnique({
      where: { id },
      select: {
        filename: true,
        mimeType: true,
        size: true,
      },
    });

    if (!blob) {
      return new NextResponse(null, { status: 404 });
    }

    const fileOnDisk = path.join(STORAGE_DIR, blob.filename);

    if (!fs.existsSync(fileOnDisk)) {
      return new NextResponse(null, { status: 404 });
    }

    return new NextResponse(null, {
      status: 200,
      headers: {
        'Content-Length': String(blob.size),
        'Content-Type': blob.mimeType || 'application/octet-stream',
        'Accept-Ranges': 'bytes',
      },
    });
  } catch (error) {
    console.error('[Blob HEAD] Error:', error);
    return new NextResponse(null, { status: 500 });
  }
}

export async function DELETE(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;

  if (!id) {
    return NextResponse.json({ error: 'Missing id' }, { status: 400 });
  }

  try {
    // Get blob from database
    const blob = await prisma.blob.findUnique({
      where: { id },
      select: {
        filename: true,
      },
    });

    if (!blob) {
      return NextResponse.json({ error: 'Not found' }, { status: 404 });
    }

    const fileOnDisk = path.join(STORAGE_DIR, blob.filename);
    const metaFile = path.join(STORAGE_DIR, `${id}.meta.json`);
    const processingFile = path.join(STORAGE_DIR, `${id}.processing.json`);

    // Delete files
    if (fs.existsSync(fileOnDisk)) {
      fs.unlinkSync(fileOnDisk);
    }
    if (fs.existsSync(metaFile)) {
      fs.unlinkSync(metaFile);
    }
    if (fs.existsSync(processingFile)) {
      fs.unlinkSync(processingFile);
    }

    // Delete from database (cascades to embeddings, attributes, etc.)
    await prisma.blob.delete({
      where: { id },
    });

    return new NextResponse(null, { status: 204 });
  } catch (error) {
    console.error('[Blob DELETE] Error:', error);
    return NextResponse.json({ error: 'Delete failed' }, { status: 500 });
  }
}
