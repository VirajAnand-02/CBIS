import { NextRequest, NextResponse } from 'next/server';
import { preprocessingManager } from '@/lib/preprocessing-manager';

export const dynamic = 'force-dynamic';

// POST: Start preprocessing a blob
export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { blobId, filename, fileUrl } = body;

    if (!blobId || !filename) {
      return NextResponse.json(
        { error: 'Missing required fields: blobId, filename' },
        { status: 400 }
      );
    }

    console.log(`[Preprocessing API] Received request for blob ${blobId} (${filename})`);
    console.log(`[Preprocessing API] File URL: ${fileUrl}`);

    // Add job to preprocessing queue
    const jobId = preprocessingManager.addJob(blobId, filename, fileUrl);

    return NextResponse.json({
      success: true,
      jobId,
      message: 'Preprocessing started',
    });
  } catch (error) {
    console.error('[Preprocessing API] Error:', error);
    return NextResponse.json(
      { error: 'Failed to start preprocessing' },
      { status: 500 }
    );
  }
}

// GET: Get current preprocessing status
export async function GET() {
  try {
    const count = preprocessingManager.getJobCount();
    const jobs = preprocessingManager.getAllJobs().map((job) => ({
      id: job.id,
      blobId: job.blobId,
      filename: job.filename,
      startedAt: job.startedAt.toISOString(),
    }));

    return NextResponse.json({
      count,
      jobs,
    });
  } catch (error) {
    console.error('[Preprocessing API] Error:', error);
    return NextResponse.json(
      { error: 'Failed to get preprocessing status' },
      { status: 500 }
    );
  }
}
