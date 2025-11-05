import { NextRequest, NextResponse } from 'next/server';
import { getBlobWithDetails } from '@/lib/db';

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;

  if (!id) {
    return NextResponse.json({ error: 'Missing id' }, { status: 400 });
  }

  try {
    const blob = await getBlobWithDetails(id);
    
    if (!blob) {
      return NextResponse.json({ error: 'Not found' }, { status: 404 });
    }

    // Transform to include all relevant metadata
    const metadata = {
      id: blob.id,
      filename: blob.originalName || blob.filename,
      storageFilename: blob.filename,
      size: blob.size,
      mimeType: blob.mimeType,
      width: blob.width,
      height: blob.height,
      uploadedAt: blob.createdAt.toISOString(),
      processingStatus: blob.processingStatus,
      
      // Embedding data
      embedding: blob.embeddings[0] ? {
        caption: blob.embeddings[0].caption,
        modelName: blob.embeddings[0].modelName,
        device: blob.embeddings[0].device,
        embeddingTime: blob.embeddings[0].embeddingTime,
        captionTime: blob.embeddings[0].captionTime,
      } : null,
      
      // Attributes
      attributes: blob.attributes ? {
        isDocument: blob.attributes.isDocument,
        hasPeople: blob.attributes.hasPeople,
        isScreenshot: blob.attributes.isScreenshot,
        isAnimal: blob.attributes.isAnimal,
        documentProb: blob.attributes.documentProb,
        peopleProb: blob.attributes.peopleProb,
        screenshotProb: blob.attributes.screenshotProb,
        animalProb: blob.attributes.animalProb,
        nimaScore: blob.attributes.nimaScore,
        nimaTechnical: blob.attributes.nimaTechnical,
        nimaAesthetic: blob.attributes.nimaAesthetic,
        nimaDistribution: blob.attributes.nimaDistribution,
      } : null,
      
      // OCR results
      ocrResults: blob.ocrResults.map(ocr => ({
        text: ocr.text,
        language: ocr.language,
        confidence: ocr.confidence,
        engine: ocr.engine,
        processingTime: ocr.processingTime,
      })),
    };
    
    return NextResponse.json(metadata, { status: 200 });
  } catch (error) {
    console.error('Error reading metadata:', error);
    return NextResponse.json({ error: 'Failed to read metadata' }, { status: 500 });
  }
}
