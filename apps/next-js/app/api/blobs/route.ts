import { NextRequest, NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';
import crypto from 'crypto';
import { createBlob } from '@/lib/db';
import sharp from 'sharp';
import { encode } from 'blurhash';

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
    let blurhash: string | undefined;
    const mimeType = file.type || 'application/octet-stream';
    
    if (mimeType.startsWith('image/')) {
      try {
        const metadata = await sharp(buffer).metadata();
        width = metadata.width;
        height = metadata.height;
        
        // Generate blurhash for smooth loading
        const resized = await sharp(buffer)
          .resize(32, 32, { fit: 'inside' })
          .ensureAlpha()
          .raw()
          .toBuffer({ resolveWithObject: true });
        
        blurhash = encode(
          new Uint8ClampedArray(resized.data),
          resized.info.width,
          resized.info.height,
          4,
          3
        );
      } catch (err) {
        console.warn('[Blob Upload] Failed to extract image metadata/blurhash:', err);
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
      blurhash,
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

    // If there's a query, use the search router pipeline
    if (query && query.trim()) {
      console.log('Using Search Router pipeline for query:', query);
      
      const { searchManager } = await import('@/lib/search-manager');
      
      // Build filters for search
      const filters: Record<string, unknown> = {};
      
      // Type filter
      if (type !== 'All') {
        const mimeTypes: string[] = [];
        if (type === 'Image') mimeTypes.push('image/jpeg', 'image/png', 'image/gif', 'image/webp');
        else if (type === 'Video') mimeTypes.push('video/mp4', 'video/webm', 'video/quicktime');
        else if (type === 'Audio') mimeTypes.push('audio/mpeg', 'audio/wav', 'audio/ogg');
        else if (type === 'Document') mimeTypes.push('application/pdf', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document');
        
        if (mimeTypes.length > 0) {
          filters.mimeType = mimeTypes;
        }
      }
      
      // Date filters (we'll apply these after search)
      const dateFilter = dateMode && dateStart ? { dateMode, dateStart, dateEnd } : null;
      
      // Call search pipeline
      const searchResult = await searchManager.search(
        query,
        filters,
        pageSize,
        (page - 1) * pageSize
      );
      
      // Apply date filter if needed
      let results = searchResult.results;
      if (dateFilter) {
        results = results.filter(item => {
          const itemDate = new Date(item.uploadedAt);
          if (dateFilter.dateMode === 'before') {
            return itemDate <= dateFilter.dateStart!;
          } else if (dateFilter.dateMode === 'after') {
            return itemDate >= dateFilter.dateStart!;
          } else if (dateFilter.dateMode === 'range' && dateFilter.dateEnd) {
            return itemDate >= dateFilter.dateStart! && itemDate <= dateFilter.dateEnd;
          }
          return true;
        });
      }
      
      // Transform search results to blob format
      const items = results.map(result => ({
        id: result.id,
        filename: result.originalName || result.filename,
        storageFilename: result.filename,
        size: result.size,
        mimeType: result.mimeType,
        uploadedAt: result.uploadedAt.toISOString ? result.uploadedAt.toISOString() : result.uploadedAt,
        width: result.width,
        height: result.height,
        blurhash: undefined, // Not included in search results
        caption: result.caption,
        attributes: result.attributes,
        processingStatus: 'completed', // Assume completed for search results
        similarity_score: result.similarity_score,
        combined_score: result.combined_score,
      }));
      
      const total = dateFilter ? results.length : searchResult.total_count;
      const totalPages = Math.ceil(total / pageSize);
      
      // Log results
      const duration = Date.now() - startTime;
      console.log('Search Results:', items.length);
      console.log('Total Found:', total);
      console.log('Pipeline Times:', searchResult.pipeline_times);
      console.log('Strategy Used:', searchResult.strategy);
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
        search_metadata: {
          query: searchResult.query,
          strategy: searchResult.strategy,
          reasoning: searchResult.reasoning,
          pipeline_times: searchResult.pipeline_times,
        },
      });
    }

    // No query - use simple database listing
    // Build where clause for filters
    const where: Record<string, unknown> = {};

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
      blurhash: blob.blurhash,
      caption: blob.embeddings?.caption,
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
