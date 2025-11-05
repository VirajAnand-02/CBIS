"use client";

import { Dialog } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { ScrollArea } from "@/components/ui/scroll-area";
import { ChevronLeft, ChevronRight, X, Download, Calendar, FileType, HardDrive, Clock } from "lucide-react";
import Image from "next/image";
import { MediaItem } from "@/components/media-card";
import { format } from "date-fns";
import { useState, useEffect, useCallback } from "react";
import * as DialogPrimitive from "@radix-ui/react-dialog";

interface ImageViewModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  item: MediaItem | null;
  items: MediaItem[];
  onNavigate?: (direction: "prev" | "next") => void;
}

interface BlobMetadata {
  id: string;
  filename: string;
  storageFilename: string;
  size: number;
  mimeType: string;
  uploadedAt: string;
  // Add any extracted metadata fields here
  extractedInfo?: {
    dimensions?: { width: number; height: number };
    duration?: number;
    bitrate?: number;
    codec?: string;
    [key: string]: string | number | boolean | object | undefined;
  };
}

export function ImageViewModal({ open, onOpenChange, item, items, onNavigate }: ImageViewModalProps) {
  const [metadata, setMetadata] = useState<BlobMetadata | null>(null);
  const [isLoadingMetadata, setIsLoadingMetadata] = useState(false);
  const [currentIndex, setCurrentIndex] = useState(-1);

  // Find current item index
  useEffect(() => {
    if (item && items.length > 0) {
      const index = items.findIndex((i) => i.id === item.id);
      setCurrentIndex(index);
    } else {
      setCurrentIndex(-1);
    }
  }, [item, items]);

  // Fetch metadata when item changes
  useEffect(() => {
    if (item?.blobId && open) {
      fetchMetadata(item.blobId);
    } else {
      setMetadata(null);
    }
  }, [item, open]);

  const fetchMetadata = async (blobId: string) => {
    setIsLoadingMetadata(true);
    try {
      const response = await fetch(`/api/blobs/${blobId}/metadata`);
      if (response.ok) {
        const data = await response.json();
        setMetadata(data);
      }
    } catch (error) {
      console.error("Failed to fetch metadata:", error);
    } finally {
      setIsLoadingMetadata(false);
    }
  };

  const handlePrevious = useCallback(() => {
    if (currentIndex > 0) {
      onNavigate?.("prev");
      // Parent component should update the item prop
    }
  }, [currentIndex, onNavigate]);

  const handleNext = useCallback(() => {
    if (currentIndex < items.length - 1) {
      onNavigate?.("next");
      // Parent component should update the item prop
    }
  }, [currentIndex, items.length, onNavigate]);

  // Keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!open) return;
      
      if (e.key === "ArrowLeft") {
        handlePrevious();
      } else if (e.key === "ArrowRight") {
        handleNext();
      } else if (e.key === "Escape") {
        onOpenChange(false);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [open, handlePrevious, handleNext, onOpenChange]);

  const handleDownload = async () => {
    if (!item?.blobId) return;
    
    try {
      const response = await fetch(`/api/blobs/${item.blobId}/download`);
      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = item.name;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
      }
    } catch (error) {
      console.error("Download failed:", error);
    }
  };

  if (!item) return null;

  const canGoPrevious = currentIndex > 0;
  const canGoNext = currentIndex < items.length - 1;
  const imageUrl = item.blobId ? `/api/blobs/${item.blobId}` : null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/60 backdrop-blur-md data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0" />
        <DialogPrimitive.Content 
          className="fixed top-[50%] left-[50%] z-50 translate-x-[-50%] translate-y-[-50%] max-w-[78vw]! w-[78vw]! h-[76vh] p-0 gap-0 bg-background rounded-lg border shadow-lg data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 duration-200"
        >
          <DialogPrimitive.Title className="sr-only">{item.name}</DialogPrimitive.Title>
        <div className="flex h-full overflow-hidden">
          {/* Left Side - Image Display */}
          <div className="flex-1 relative bg-black/5 dark:bg-black/20 flex items-center justify-center overflow-hidden">
            {/* Navigation Buttons */}
            <Button
              variant="ghost"
              size="icon"
              className="absolute left-4 top-1/2 -translate-y-1/2 z-10 bg-background/80 hover:bg-background"
              onClick={handlePrevious}
              disabled={!canGoPrevious}
            >
              <ChevronLeft className="h-6 w-6" />
            </Button>

            <Button
              variant="ghost"
              size="icon"
              className="absolute right-4 top-1/2 -translate-y-1/2 z-10 bg-background/80 hover:bg-background"
              onClick={handleNext}
              disabled={!canGoNext}
            >
              <ChevronRight className="h-6 w-6" />
            </Button>

            {/* Close Button */}
            <Button
              variant="ghost"
              size="icon"
              className="absolute top-4 left-4 z-10 bg-background/80 hover:bg-background"
              onClick={() => onOpenChange(false)}
            >
              <X className="h-5 w-5" />
            </Button>

            {/* Image Counter */}
            <div className="absolute top-4 left-1/2 -translate-x-1/2 z-10 bg-background/80 px-3 py-1 rounded-full text-sm">
              {currentIndex + 1} / {items.length}
            </div>

            {/* Image Display */}
            {item.type === "Image" && imageUrl ? (
              <div className="relative w-full h-full max-h-full">
                <Image
                  src={imageUrl}
                  alt={item.name}
                  fill
                  className="object-contain max-h-full"
                  unoptimized
                  priority
                />
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center text-muted-foreground">
                {item.type === "Video" && (
                  <video
                    src={imageUrl || ""}
                    controls
                    className="max-w-full max-h-full"
                  >
                    Your browser does not support the video tag.
                  </video>
                )}
                {item.type !== "Video" && item.type !== "Image" && (
                  <>
                    <FileType className="h-16 w-16 mb-4" />
                    <p>Preview not available for this file type</p>
                  </>
                )}
              </div>
            )}
          </div>

          {/* Right Side - Metadata Panel */}
          <div className="w-80 border-l bg-background flex flex-col overflow-hidden">
            {/* Header */}
            <div className="p-6 border-b shrink-0">
              <h2 className="text-lg font-semibold truncate mb-2">{item.name}</h2>
              <Badge variant="secondary">{item.type}</Badge>
            </div>

            {/* Metadata Content */}
            <ScrollArea className="flex-1 h-0">
              <div className="p-6 space-y-6">
                {/* Basic Info */}
                <div className="space-y-3">
                  <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
                    Basic Information
                  </h3>
                  
                  <div className="space-y-2">
                    <div className="flex items-start gap-3">
                      <Calendar className="h-4 w-4 mt-0.5 text-muted-foreground" />
                      <div className="flex-1 min-w-0">
                        <p className="text-xs text-muted-foreground">Upload Date</p>
                        <p className="text-sm">{format(item.date, "PPpp")}</p>
                      </div>
                    </div>

                    <div className="flex items-start gap-3">
                      <HardDrive className="h-4 w-4 mt-0.5 text-muted-foreground" />
                      <div className="flex-1 min-w-0">
                        <p className="text-xs text-muted-foreground">File Size</p>
                        <p className="text-sm">{item.size}</p>
                      </div>
                    </div>

                    {item.mimeType && (
                      <div className="flex items-start gap-3">
                        <FileType className="h-4 w-4 mt-0.5 text-muted-foreground" />
                        <div className="flex-1 min-w-0">
                          <p className="text-xs text-muted-foreground">MIME Type</p>
                          <p className="text-xs font-mono">{item.mimeType}</p>
                        </div>
                      </div>
                    )}
                  </div>
                </div>

                <Separator />

                {/* Blob Storage Metadata */}
                {metadata && (
                  <>
                    <div className="space-y-3">
                      <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
                        Storage Metadata
                      </h3>
                      
                      <div className="space-y-2">
                        <div className="flex items-start gap-3">
                          <Clock className="h-4 w-4 mt-0.5 text-muted-foreground" />
                          <div className="flex-1 min-w-0">
                            <p className="text-xs text-muted-foreground">Blob ID</p>
                            <p className="text-xs font-mono break-all">{metadata.id}</p>
                          </div>
                        </div>

                        <div className="flex items-start gap-3">
                          <FileType className="h-4 w-4 mt-0.5 text-muted-foreground" />
                          <div className="flex-1 min-w-0">
                            <p className="text-xs text-muted-foreground">Storage Filename</p>
                            <p className="text-xs font-mono break-all">{metadata.storageFilename}</p>
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Extracted Information */}
                    {metadata.extractedInfo && Object.keys(metadata.extractedInfo).length > 0 && (
                      <>
                        <Separator />
                        <div className="space-y-3">
                          <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
                            Extracted Information
                          </h3>
                          
                          <div className="space-y-2">
                            {metadata.extractedInfo.dimensions && (
                              <div className="flex justify-between">
                                <span className="text-xs text-muted-foreground">Dimensions</span>
                                <span className="text-sm">
                                  {metadata.extractedInfo.dimensions.width} × {metadata.extractedInfo.dimensions.height}
                                </span>
                              </div>
                            )}
                            
                            {metadata.extractedInfo.duration && (
                              <div className="flex justify-between">
                                <span className="text-xs text-muted-foreground">Duration</span>
                                <span className="text-sm">{metadata.extractedInfo.duration}s</span>
                              </div>
                            )}
                            
                            {metadata.extractedInfo.bitrate && (
                              <div className="flex justify-between">
                                <span className="text-xs text-muted-foreground">Bitrate</span>
                                <span className="text-sm">{metadata.extractedInfo.bitrate} kbps</span>
                              </div>
                            )}

                            {metadata.extractedInfo.codec && (
                              <div className="flex justify-between">
                                <span className="text-xs text-muted-foreground">Codec</span>
                                <span className="text-xs font-mono">{metadata.extractedInfo.codec}</span>
                              </div>
                            )}

                            {/* Display any other extracted info */}
                            {Object.entries(metadata.extractedInfo).map(([key, value]) => {
                              if (['dimensions', 'duration', 'bitrate', 'codec'].includes(key)) return null;
                              return (
                                <div key={key} className="flex justify-between">
                                  <span className="text-xs text-muted-foreground capitalize">
                                    {key.replace(/([A-Z])/g, ' $1').trim()}
                                  </span>
                                  <span className="text-sm">{String(value)}</span>
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      </>
                    )}

                    <Separator />

                    {/* Database Information (Placeholder) */}
                    <div className="space-y-3">
                      <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
                        Database Information
                      </h3>
                      <p className="text-sm text-muted-foreground italic">
                        To be implemented
                      </p>
                      {/* TODO: Add database-fetched information here */}
                    </div>
                  </>
                )}

                {isLoadingMetadata && (
                  <div className="flex items-center justify-center py-8">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
                  </div>
                )}
              </div>
            </ScrollArea>

            {/* Footer Actions */}
            <div className="p-4 border-t">
              <Button onClick={handleDownload} className="w-full" variant="default">
                <Download className="h-4 w-4 mr-2" />
                Download
              </Button>
            </div>
          </div>
        </div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </Dialog>
  );
}
