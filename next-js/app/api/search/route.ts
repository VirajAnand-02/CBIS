import { NextRequest, NextResponse } from 'next/server';
import { searchManager } from '@/lib/search-manager';

export const dynamic = 'force-dynamic';

/**
 * Search API Endpoint
 * 
 * POST /api/search
 * {
 *   "query": "beautiful sunset photos",
 *   "filters": {
 *     "mimeType": ["image/jpeg", "image/png"],
 *     "minNimaScore": 6.0
 *   },
 *   "limit": 20,
 *   "offset": 0
 * }
 * 
 * GET /api/search?q=sunset&limit=20&offset=0
 */

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { query, filters, limit = 20, offset = 0 } = body;

    if (!query || typeof query !== 'string' || query.trim() === '') {
      return NextResponse.json(
        { error: 'Query parameter is required and must be a non-empty string' },
        { status: 400 }
      );
    }

    console.log(`[Search API] POST /api/search: "${query}"`);

    const result = await searchManager.search(
      query,
      filters,
      parseInt(String(limit)),
      parseInt(String(offset))
    );

    return NextResponse.json(result);
  } catch (error) {
    console.error('[Search API] Error:', error);
    return NextResponse.json(
      {
        error: 'Search failed',
        message: error instanceof Error ? error.message : 'Unknown error',
      },
      { status: 500 }
    );
  }
}

export async function GET(req: NextRequest) {
  try {
    const searchParams = req.nextUrl.searchParams;
    const query = searchParams.get('q') || searchParams.get('query');
    const limit = parseInt(searchParams.get('limit') || '20');
    const offset = parseInt(searchParams.get('offset') || '0');

    // Build filters from query params
    const filters: Record<string, unknown> = {};
    
    const mimeType = searchParams.get('mimeType');
    if (mimeType) {
      filters.mimeType = mimeType.split(',');
    }
    
    const minNimaScore = searchParams.get('minNimaScore');
    if (minNimaScore) {
      filters.minNimaScore = parseFloat(minNimaScore);
    }
    
    const maxNimaScore = searchParams.get('maxNimaScore');
    if (maxNimaScore) {
      filters.maxNimaScore = parseFloat(maxNimaScore);
    }

    if (!query || query.trim() === '') {
      return NextResponse.json(
        { error: 'Query parameter (q or query) is required' },
        { status: 400 }
      );
    }

    console.log(`[Search API] GET /api/search?q=${query}`);

    const result = await searchManager.search(
      query,
      Object.keys(filters).length > 0 ? filters : undefined,
      limit,
      offset
    );

    return NextResponse.json(result);
  } catch (error) {
    console.error('[Search API] Error:', error);
    return NextResponse.json(
      {
        error: 'Search failed',
        message: error instanceof Error ? error.message : 'Unknown error',
      },
      { status: 500 }
    );
  }
}
