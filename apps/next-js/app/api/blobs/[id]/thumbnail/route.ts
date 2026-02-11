import { NextRequest, NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';
import sharp from 'sharp';
import { prisma } from '@/lib/db';

const STORAGE_DIR = path.join(process.cwd(), 'storage', 'blobs');
const THUMBNAIL_DIR = path.join(STORAGE_DIR, 'thumbnails');

if (!fs.existsSync(THUMBNAIL_DIR)) {
  fs.mkdirSync(THUMBNAIL_DIR, { recursive: true });
}

function thumbnailPath(id: string) {
  return path.join(THUMBNAIL_DIR, `${id}.jpg`);
}

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;

  if (!id) {
    return NextResponse.json({ error: 'Missing id' }, { status: 400 });
  }

  try {
    // Query database for blob metadata
    const blob = await prisma.blob.findUnique({
      where: { id },
      select: { filename: true, mimeType: true },
    });

    if (!blob) {
      return NextResponse.json({ error: 'Not found' }, { status: 404 });
    }

    const thumbPath = thumbnailPath(id);

    // If thumbnail exists, serve it
    if (fs.existsSync(thumbPath)) {
      const thumbBuffer = fs.readFileSync(thumbPath);
      return new NextResponse(new Uint8Array(thumbBuffer), {
        status: 200,
        headers: {
          'Content-Type': 'image/jpeg',
          'Content-Length': String(thumbBuffer.length),
          'Cache-Control': 'public, max-age=31536000, immutable',
        },
      });
    }

    // Generate thumbnail for images only
    if (blob.mimeType?.startsWith('image/')) {
      const fileOnDisk = path.join(STORAGE_DIR, blob.filename);
      
      if (!fs.existsSync(fileOnDisk)) {
        return NextResponse.json({ error: 'File not found' }, { status: 404 });
      }

      try {
        const thumbnail = await sharp(fileOnDisk)
          .resize(400, 400, { fit: 'cover', position: 'center' })
          .jpeg({ quality: 80 })
          .toBuffer();

        // Save thumbnail for future requests
        fs.writeFileSync(thumbPath, thumbnail);

        return new NextResponse(new Uint8Array(thumbnail), {
          status: 200,
          headers: {
            'Content-Type': 'image/jpeg',
            'Content-Length': String(thumbnail.length),
            'Cache-Control': 'public, max-age=31536000, immutable',
          },
        });
      } catch (error) {
        console.error('Thumbnail generation error:', error);
        return NextResponse.json(
          { error: 'Failed to generate thumbnail', details: error instanceof Error ? error.message : 'Unknown error' },
          { status: 500 }
        );
      }
    }

    // For non-images, return error
    return NextResponse.json({ error: 'Thumbnail not available for non-image files' }, { status: 404 });
  } catch (error) {
    console.error('Thumbnail route error:', error);
    return NextResponse.json(
      { error: 'Internal server error', details: error instanceof Error ? error.message : 'Unknown error' },
      { status: 500 }
    );
  }
}
