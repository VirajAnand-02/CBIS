import { NextRequest, NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';
import crypto from 'crypto';
import { createBlob } from '@/lib/db';
import sharp from 'sharp';

export const dynamic = 'force-dynamic';

const STORAGE_DIR = path.join(process.cwd(), 'storage', 'blobs');
if (!fs.existsSync(STORAGE_DIR)) {
  fs.mkdirSync(STORAGE_DIR, { recursive: true });
}

function makeId() {
  return crypto.randomBytes(12).toString('hex'); // 24 chars
}

function metaPath(id: string) {
  return path.join(STORAGE_DIR, `${id}.meta.json`);
}

export async function POST(req: NextRequest) {
  try {
    const formData = await req.formData();
    const file = formData.get('file') as File;

    if (!file) {
      return NextResponse.json({ error: 'No file uploaded' }, { status: 400 });
    }

    const bytes = await file.arrayBuffer();
    const buffer = Buffer.from(bytes);

    const id = makeId();
    const originalName = file.name || 'unknown';
    const ext = path.extname(originalName) || '';
    const destPath = path.join(STORAGE_DIR, `${id}${ext}`);
    const storageFilename = path.basename(destPath);

    // Write file
    fs.writeFileSync(destPath, buffer);

    // Extract image dimensions if it's an image
    let width: number | undefined;
    let height: number | undefined;
    const mimeType = file.type || 'application/octet-stream';
    
    if (mimeType.startsWith('image/')) {
      try {
        const metadata = await sharp(buffer).metadata();
        width = metadata.width;
        height = metadata.height;
      } catch (err) {
        console.warn('[Blob Upload] Failed to extract image dimensions:', err);
      }
    }

    // Create database record
    const blob = await createBlob({
      filename: storageFilename,
      originalName,
      mimeType,
      size: buffer.length,
      width,
      height,
      storagePath: `storage/blobs/${storageFilename}`,
    });

    // Also save metadata JSON for backward compatibility
    const meta = {
      id: blob.id,
      filename: originalName,
      storageFilename,
      size: buffer.length,
      mimeType,
      uploadedAt: blob.createdAt.toISOString(),
      width,
      height,
    };

    fs.writeFileSync(metaPath(blob.id), JSON.stringify(meta, null, 2));

    // Trigger preprocessing pipeline
    try {
      const baseUrl = process.env.NEXT_PUBLIC_BASE_URL || 'http://localhost:3000';
      const fileUrl = `${baseUrl}/api/blobs/${blob.id}`;
      
      // Call preprocessing API (fire and forget)
      fetch(`${baseUrl}/api/preprocessing`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          blobId: blob.id,
          filename: originalName,
          fileUrl,
        }),
      }).catch((err) => {
        console.error('[Blob Upload] Failed to trigger preprocessing:', err);
      });
      
      console.log(`[Blob Upload] Triggered preprocessing for blob ${blob.id}`);
    } catch (err) {
      console.error('[Blob Upload] Error triggering preprocessing:', err);
      // Don't fail the upload if preprocessing trigger fails
    }

    return NextResponse.json({ 
      message: 'uploaded', 
      id: blob.id, 
      meta,
      blob: {
        id: blob.id,
        filename: blob.filename,
        originalName: blob.originalName,
        size: blob.size,
        mimeType: blob.mimeType,
        createdAt: blob.createdAt,
      }
    }, { status: 201 });
  } catch (error) {
    console.error('Upload error', error);
    return NextResponse.json({ error: 'Upload failed' }, { status: 500 });
  }
}



export async function GET(req: NextRequest) {
  const startTime = Date.now();
  
  try {
    const { prisma } = await import('@/lib/db');
    const { searchParams } = new URL(req.url);
    
    // Pagination params
    const page = parseInt(searchParams.get('page') || '1', 10);
    const pageSize = parseInt(searchParams.get('pageSize') || '20', 10);
    
    // Filter params
    const query = searchParams.get('query') || '';
    const type = searchParams.get('type') || 'All';
    const dateMode = searchParams.get('dateMode') as 'before' | 'after' | 'range' | null;
    const dateStart = searchParams.get('dateStart') ? new Date(searchParams.get('dateStart')!) : null;
    const dateEnd = searchParams.get('dateEnd') ? new Date(searchParams.get('dateEnd')!) : null;

    // Log search request
    console.log('=== Blob Search Request ===');
    console.log('Timestamp:', new Date().toISOString());
    console.log('Page:', page, '| Page Size:', pageSize);
    if (query) console.log('Search Query:', query);
    if (type !== 'All') console.log('Type Filter:', type);
    if (dateMode && dateStart) {
      console.log('Date Filter:', dateMode);
      console.log('Date Start:', dateStart.toISOString());
      if (dateMode === 'range' && dateEnd) {
        console.log('Date End:', dateEnd.toISOString());
      }
    }

    // Build where clause for filters
    const where: Record<string, unknown> = {};
    
    // Query filter (search in originalName)
    if (query) {
      where.OR = [
        { originalName: { contains: query, mode: 'insensitive' } },
        { filename: { contains: query, mode: 'insensitive' } },
      ];
    }

    // Type filter
    if (type !== 'All') {
      const mimePrefix = type === 'Image' ? 'image/' 
        : type === 'Video' ? 'video/'
        : type === 'Audio' ? 'audio/'
        : type === 'Document' ? 'application/'
        : '';
      
      if (mimePrefix) {
        where.mimeType = { startsWith: mimePrefix };
      }
    }

    // Date filter
    if (dateStart && dateMode) {
      if (dateMode === 'before') {
        where.createdAt = { lte: dateStart };
      } else if (dateMode === 'after') {
        where.createdAt = { gte: dateStart };
      } else if (dateMode === 'range' && dateEnd) {
        where.createdAt = { gte: dateStart, lte: dateEnd };
      }
    }

    // Get total count
    const total = await prisma.blob.count({ where });
    console.log('Total Blobs in Database:', total);

    // Get paginated results
    const blobs = await prisma.blob.findMany({
      where,
      orderBy: { createdAt: 'desc' },
      skip: (page - 1) * pageSize,
      take: pageSize,
      include: {
        embeddings: {
          select: { caption: true },
        },
        attributes: {
          select: {
            isDocument: true,
            hasPeople: true,
            isScreenshot: true,
            isAnimal: true,
            nimaScore: true,
          },
        },
      },
    });

    // Transform to match existing format for backward compatibility
    const items = blobs.map(blob => ({
      id: blob.id,
      filename: blob.originalName || blob.filename,
      storageFilename: blob.filename,
      size: blob.size,
      mimeType: blob.mimeType,
      uploadedAt: blob.createdAt.toISOString(),
      width: blob.width,
      height: blob.height,
      caption: blob.embeddings?.[0]?.caption,
      attributes: blob.attributes,
      processingStatus: blob.processingStatus,
    }));

    // Calculate pagination
    const totalPages = Math.ceil(total / pageSize);

    // Log results
    const duration = Date.now() - startTime;
    console.log('Results Found:', total);
    console.log('Returned Items:', items.length);
    console.log('Has More:', page < totalPages);
    console.log('Duration:', duration, 'ms');
    console.log('===========================\n');

    return NextResponse.json({
      items,
      pagination: {
        page,
        pageSize,
        total,
        totalPages,
        hasMore: page < totalPages,
      },
    });
  } catch (error) {
    console.error('=== Blob Search Error ===');
    console.error('Timestamp:', new Date().toISOString());
    console.error('Error:', error);
    console.error('=========================\n');
    return NextResponse.json({ error: 'Failed to list blobs' }, { status: 500 });
  }
}
