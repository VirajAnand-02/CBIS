import { NextRequest, NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

const STORAGE_DIR = path.join(process.cwd(), 'storage', 'blobs');

function metaPath(id: string) {
  return path.join(STORAGE_DIR, `${id}.meta.json`);
}

function findStorageFile(id: string) {
  const files = fs.readdirSync(STORAGE_DIR);
  const match = files.find((f) => f.startsWith(id) && !f.endsWith('.meta.json'));
  if (!match) return null;
  return path.join(STORAGE_DIR, match);
}

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;

  if (!id) {
    return NextResponse.json({ error: 'Missing id' }, { status: 400 });
  }

  const metaFile = metaPath(id);
  if (!fs.existsSync(metaFile)) {
    return NextResponse.json({ error: 'Not found' }, { status: 404 });
  }

  const meta = JSON.parse(fs.readFileSync(metaFile, 'utf8'));
  const fileOnDisk = findStorageFile(id);
  
  if (!fileOnDisk || !fs.existsSync(fileOnDisk)) {
    return NextResponse.json({ error: 'Blob file missing' }, { status: 404 });
  }

  try {
    const fileBuffer = fs.readFileSync(fileOnDisk);
    
    return new NextResponse(fileBuffer, {
      status: 200,
      headers: {
        'Content-Type': meta.mimeType || 'application/octet-stream',
        'Content-Disposition': `attachment; filename="${meta.filename}"`,
        'Content-Length': String(fileBuffer.length),
      },
    });
  } catch (error) {
    console.error('Download error:', error);
    return NextResponse.json({ error: 'Download failed' }, { status: 500 });
  }
}
