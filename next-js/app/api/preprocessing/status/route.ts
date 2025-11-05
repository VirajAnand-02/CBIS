import { NextRequest } from 'next/server';
import { preprocessingManager } from '@/lib/preprocessing-manager';

export const dynamic = 'force-dynamic';

// Server-Sent Events endpoint for real-time updates
export async function GET(req: NextRequest) {
  const responseStream = new TransformStream();
  const writer = responseStream.writable.getWriter();
  const encoder = new TextEncoder();

  // Set up SSE headers
  const headers = new Headers({
    'Content-Type': 'text/event-stream',
    'Cache-Control': 'no-cache',
    'Connection': 'keep-alive',
  });

  // Function to send SSE message
  const sendMessage = (data: { count: number }) => {
    const message = `data: ${JSON.stringify(data)}\n\n`;
    writer.write(encoder.encode(message));
  };

  // Send initial count
  const initialCount = preprocessingManager.getJobCount();
  sendMessage({ count: initialCount });

  console.log('[SSE] Client connected, initial count:', initialCount);

  // Listen for changes
  const unsubscribe = preprocessingManager.addListener((count) => {
    console.log('[SSE] Sending update to client, count:', count);
    sendMessage({ count });
  });

  // Handle client disconnect
  req.signal.addEventListener('abort', () => {
    console.log('[SSE] Client disconnected');
    unsubscribe();
    writer.close();
  });

  return new Response(responseStream.readable, { headers });
}
