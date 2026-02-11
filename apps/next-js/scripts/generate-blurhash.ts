#!/usr/bin/env ts-node
/**
 * Generate blurhash for all existing images in the database
 * 
 * Usage: npx ts-node scripts/generate-blurhash.ts
 */

import { PrismaClient } from '../lib/generated/prisma/index.js';
import sharp from 'sharp';
import { encode } from 'blurhash';
import * as fs from 'fs';
import * as path from 'path';

const prisma = new PrismaClient();

/**
 * Generate blurhash from image buffer
 */
async function generateBlurhash(imagePath: string): Promise<string | null> {
  try {
    const imageBuffer = await fs.promises.readFile(imagePath);
    
    // Resize image to small size for blurhash generation (faster)
    const image = sharp(imageBuffer)
      .resize(32, 32, { fit: 'inside' });
    
    const { data, info } = await image
      .ensureAlpha()
      .raw()
      .toBuffer({ resolveWithObject: true });
    
    // Generate blurhash (4x3 components for good quality/speed balance)
    const blurhash = encode(
      new Uint8ClampedArray(data),
      info.width,
      info.height,
      4,
      3
    );
    
    return blurhash;
  } catch (error) {
    console.error(`Error generating blurhash for ${imagePath}:`, error);
    return null;
  }
}

/**
 * Main function
 */
async function main() {
  console.log('🔍 Fetching all blobs from database...');
  
  // Get all blobs that are images and don't have blurhash yet
  const blobs = await prisma.blob.findMany({
    where: {
      mimeType: {
        startsWith: 'image/'
      },
      blurhash: null
    },
    select: {
      id: true,
      filename: true,
      storagePath: true,
      mimeType: true
    }
  });
  
  console.log(`📸 Found ${blobs.length} images without blurhash`);
  
  if (blobs.length === 0) {
    console.log('✅ All images already have blurhash!');
    return;
  }
  
  let processed = 0;
  let succeeded = 0;
  let failed = 0;
  
  for (const blob of blobs) {
    processed++;
    // storagePath already includes 'storage/blobs/' prefix
    const imagePath = path.join(process.cwd(), blob.storagePath);
    
    // Check if file exists
    if (!fs.existsSync(imagePath)) {
      console.log(`⚠️  [${processed}/${blobs.length}] File not found: ${blob.filename} at ${imagePath}`);
      failed++;
      continue;
    }
    
    // Generate blurhash
    const blurhash = await generateBlurhash(imagePath);
    
    if (blurhash) {
      // Update database
      await prisma.blob.update({
        where: { id: blob.id },
        data: { blurhash }
      });
      
      succeeded++;
      console.log(`✅ [${processed}/${blobs.length}] Generated blurhash for: ${blob.filename}`);
    } else {
      failed++;
      console.log(`❌ [${processed}/${blobs.length}] Failed to generate blurhash for: ${blob.filename}`);
    }
  }
  
  console.log('\n📊 Summary:');
  console.log(`   Total processed: ${processed}`);
  console.log(`   Succeeded: ${succeeded}`);
  console.log(`   Failed: ${failed}`);
  console.log('\n✨ Done!');
}

// Run the script
main()
  .catch((error) => {
    console.error('Fatal error:', error);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
