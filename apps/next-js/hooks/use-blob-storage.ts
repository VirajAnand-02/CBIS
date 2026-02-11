"use client";

import { useState, useEffect, useCallback } from "react";
import { MediaItem, MediaType } from "@/components/media-card";

interface BlobMeta {
  id: string;
  filename: string;
  storageFilename: string;
  size: number;
  mimeType: string;
  uploadedAt: string;
  blurhash?: string;
  width?: number;
  height?: number;
}

interface PaginationInfo {
  page: number;
  pageSize: number;
  total: number;
  totalPages: number;
  hasMore: boolean;
}

interface FetchOptions {
  page?: number;
  pageSize?: number;
  query?: string;
  type?: string;
  dateMode?: string;
  dateStart?: Date;
  dateEnd?: Date;
}

function formatFileSize(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(2)} ${sizes[i]}`;
}

function getMediaTypeFromMime(mimeType: string): MediaType {
  if (mimeType.startsWith("image/")) return "Image";
  if (mimeType.startsWith("video/")) return "Video";
  if (mimeType.startsWith("audio/")) return "Audio";
  return "Document";
}

export function useBlobStorage(options: FetchOptions = {}) {
  const [items, setItems] = useState<MediaItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pagination, setPagination] = useState<PaginationInfo | null>(null);

  const fetchBlobs = useCallback(async (page: number = 1, append: boolean = false) => {
    try {
      if (append) {
        setIsLoadingMore(true);
      } else {
        setIsLoading(true);
      }
      setError(null);

      // Build query params
      const params = new URLSearchParams({
        page: page.toString(),
        pageSize: (options.pageSize || 20).toString(),
      });

      if (options.query) params.append('query', options.query);
      if (options.type && options.type !== 'All') params.append('type', options.type);
      if (options.dateMode) params.append('dateMode', options.dateMode);
      if (options.dateStart) params.append('dateStart', options.dateStart.toISOString());
      if (options.dateEnd) params.append('dateEnd', options.dateEnd.toISOString());
      
      const response = await fetch(`/api/blobs?${params.toString()}`);
      if (!response.ok) {
        throw new Error("Failed to fetch blobs");
      }

      const data = await response.json();
      const blobs: BlobMeta[] = data.items || [];

      const mediaItems: MediaItem[] = blobs.map((blob) => ({
        id: blob.id,
        name: blob.filename,
        type: getMediaTypeFromMime(blob.mimeType),
        date: new Date(blob.uploadedAt),
        size: formatFileSize(blob.size),
        blobId: blob.id,
        thumbnailUrl: blob.mimeType.startsWith("image/")
          ? `/api/blobs/${blob.id}/thumbnail`
          : undefined,
        mimeType: blob.mimeType,
        blurhash: blob.blurhash,
        width: blob.width,
        height: blob.height,
      }));

      if (append) {
        setItems((prev) => [...prev, ...mediaItems]);
      } else {
        setItems(mediaItems);
      }

      setPagination(data.pagination);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load media");
      console.error("Error fetching blobs:", err);
    } finally {
      setIsLoading(false);
      setIsLoadingMore(false);
    }
  }, [options.pageSize, options.query, options.type, options.dateMode, options.dateStart, options.dateEnd]);

  const loadMore = useCallback(() => {
    if (pagination && pagination.hasMore && !isLoadingMore) {
      fetchBlobs(pagination.page + 1, true);
    }
  }, [pagination, isLoadingMore, fetchBlobs]);

  const refetch = useCallback(() => {
    fetchBlobs(1, false);
  }, [fetchBlobs]);

  useEffect(() => {
    fetchBlobs(1, false);
  }, [fetchBlobs]);

  return {
    items,
    isLoading,
    isLoadingMore,
    error,
    pagination,
    loadMore,
    refetch,
  };
}
