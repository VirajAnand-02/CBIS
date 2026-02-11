"use client";

import { useEffect, useState } from "react";

export function usePreprocessingStatus() {
  const [processingCount, setProcessingCount] = useState(0);
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
    let eventSource: EventSource | null = null;
    let reconnectTimeout: NodeJS.Timeout | null = null;

    const connect = () => {
      try {
        eventSource = new EventSource("/api/preprocessing/status");

        eventSource.onopen = () => {
          console.log("[Preprocessing] Connected to status stream");
          setIsConnected(true);
        };

        eventSource.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            setProcessingCount(data.count);
          } catch (error) {
            console.error("[Preprocessing] Error parsing message:", error);
          }
        };

        eventSource.onerror = (error) => {
          console.error("[Preprocessing] EventSource error:", error);
          setIsConnected(false);
          eventSource?.close();

          // Reconnect after 5 seconds
          reconnectTimeout = setTimeout(() => {
            console.log("[Preprocessing] Attempting to reconnect...");
            connect();
          }, 5000);
        };
      } catch (error) {
        console.error("[Preprocessing] Error creating EventSource:", error);
      }
    };

    connect();

    // Cleanup on unmount
    return () => {
      if (reconnectTimeout) {
        clearTimeout(reconnectTimeout);
      }
      if (eventSource) {
        eventSource.close();
      }
    };
  }, []);

  return { processingCount, isConnected };
}
