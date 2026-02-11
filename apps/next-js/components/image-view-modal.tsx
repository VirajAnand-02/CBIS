"use client";

import { Dialog } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { ChevronLeft, ChevronRight, X, Download, Calendar, FileType, HardDrive, Clock, Trash2, Tag, Star, Users, Image as ImageIcon, FileText, Camera } from "lucide-react";
import Image from "next/image";
import { MediaItem } from "@/components/media-card";
import { format } from "date-fns";
import { useState, useEffect, useCallback } from "react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { motion, AnimatePresence } from "framer-motion";
import { Blurhash } from "react-blurhash";
import { toast } from "sonner";

interface ImageViewModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  item: MediaItem | null;
  items: MediaItem[];
  onNavigate?: (direction: "prev" | "next") => void;
  onDelete?: (itemId: string) => void; // Callback when item is deleted
}

interface BlobMetadata {
  id: string;
  filename: string;
  storageFilename: string;
  size: number;
  mimeType: string;
  uploadedAt: string;
  processingStatus: string;
  
  // Embedding data
  embedding?: {
    caption?: string;
    modelName?: string;
    device?: string;
    embeddingTime?: number;
    captionTime?: number;
  } | null;
  
  // Attributes
  attributes?: {
    isDocument: boolean;
    hasPeople: boolean;
    isScreenshot: boolean;
    isAnimal: boolean;
    documentProb: number;
    peopleProb: number;
    screenshotProb: number;
    animalProb: number;
    nimaScore?: number;
    nimaTechnical?: number;
    nimaAesthetic?: number;
    nimaDistribution?: number[];
  } | null;
  
  // OCR results
  ocrResults?: Array<{
    text: string;
    language?: string;
    confidence?: number;
    engine?: string;
    processingTime?: number;
  }>;
  
  // Face detection results
  faces?: Array<{
    id: string;
    boundingBox: { x: number; y: number; width: number; height: number };
    confidence?: number;
    quality?: number;
    personId?: string;
    personName?: string;
  }>;
  
  // Add any extracted metadata fields here
  extractedInfo?: {
    dimensions?: { width: number; height: number };
    duration?: number;
    bitrate?: number;
    codec?: string;
    [key: string]: string | number | boolean | object | undefined;
  };
}

export function ImageViewModal({ open, onOpenChange, item, items, onNavigate, onDelete }: ImageViewModalProps) {
  const [metadata, setMetadata] = useState<BlobMetadata | null>(null);
  const [isLoadingMetadata, setIsLoadingMetadata] = useState(false);
  const [currentIndex, setCurrentIndex] = useState(-1);
  const [direction, setDirection] = useState<"left" | "right">("left");
  const [imageLoaded, setImageLoaded] = useState(false);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [metadataAbortController, setMetadataAbortController] = useState<AbortController | null>(null);

  // Calculate blurhash dimensions maintaining aspect ratio
  const getBlurhashDimensions = () => {
    if (!item?.width || !item?.height) {
      // Default to square if dimensions unknown
      return { width: 400, height: 400 };
    }

    const containerWidth = typeof window !== 'undefined' ? window.innerWidth * 0.78 : 1200; // 78vw
    const containerHeight = typeof window !== 'undefined' ? window.innerHeight * 0.76 : 800; // 76vh
    
    const aspectRatio = item.width / item.height;
    
    let width = containerWidth;
    let height = width / aspectRatio;
    
    // If height exceeds container, scale by height instead
    if (height > containerHeight) {
      height = containerHeight;
      width = height * aspectRatio;
    }
    
    return { width, height };
  };

  const blurhashDims = getBlurhashDimensions();

  // Memoized metadata fetching function
  const fetchMetadata = useCallback(async (blobId: string) => {
    setIsLoadingMetadata(true);
    try {
      // Use AbortController for potential cleanup
      const controller = new AbortController();
      setMetadataAbortController(controller);
      const timeoutId = setTimeout(() => controller.abort(), 10000); // 10s timeout
      
      const response = await fetch(`/api/blobs/${blobId}/metadata`, {
        signal: controller.signal,
      });
      
      clearTimeout(timeoutId);
      
      if (response.ok) {
        const data = await response.json();
        setMetadata(data);
      } else {
        console.error("Failed to fetch metadata:", response.statusText);
        setMetadata(null);
      }
    } catch (error) {
      if (error instanceof Error && error.name !== 'AbortError') {
        console.error("Failed to fetch metadata:", error);
      }
      setMetadata(null);
    } finally {
      setIsLoadingMetadata(false);
      setMetadataAbortController(null);
    }
  }, []);

  // Find current item index
  useEffect(() => {
    if (item && items.length > 0) {
      const index = items.findIndex((i) => i.id === item.id);
      setCurrentIndex(index);
      setImageLoaded(false); // Reset image loaded state when item changes
    } else {
      setCurrentIndex(-1);
    }
  }, [item, items]);

  // Fetch metadata when item changes - with delay to prioritize image loading
  useEffect(() => {
    // Cleanup previous fetch if any
    if (metadataAbortController) {
      metadataAbortController.abort();
    }

    if (!item?.blobId || !open) {
      setMetadata(null);
      setIsLoadingMetadata(false);
      return;
    }

    // Reset metadata state immediately
    setMetadata(null);
    
    // Defer metadata loading to allow image to load first
    const timeoutId = setTimeout(() => {
      if (item.blobId) {
        fetchMetadata(item.blobId);
      }
    }, 100); // Small delay to prioritize image loading

    return () => {
      clearTimeout(timeoutId);
      // Cleanup on unmount or item change
      if (metadataAbortController) {
        metadataAbortController.abort();
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [item?.blobId, open, fetchMetadata]);

  const handlePrevious = useCallback(() => {
    if (currentIndex > 0) {
      setDirection("right");
      onNavigate?.("prev");
      // Parent component should update the item prop
    }
  }, [currentIndex, onNavigate]);

  const handleNext = useCallback(() => {
    if (currentIndex < items.length - 1) {
      setDirection("left");
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

  const handleDelete = async () => {
    if (!item?.blobId) return;
    
    setIsDeleting(true);
    try {
      const response = await fetch(`/api/blobs/${item.blobId}`, {
        method: 'DELETE',
      });
      
      if (response.ok) {
        toast.success("Image deleted successfully");
        
        // Close the delete confirmation dialog
        setShowDeleteDialog(false);
        
        // Close the image viewer modal
        onOpenChange(false);
        
        // Notify parent component to refresh the list
        onDelete?.(String(item.id));
      } else {
        const error = await response.json();
        toast.error(error.error || "Failed to delete image");
      }
    } catch (error) {
      console.error("Delete failed:", error);
      toast.error("Failed to delete image");
    } finally {
      setIsDeleting(false);
    }
  };

  if (!item) return null;

  const canGoPrevious = currentIndex > 0;
  const canGoNext = currentIndex < items.length - 1;
  const imageUrl = item.blobId ? `/api/blobs/${item.blobId}` : null;

  // Animation variants for image transitions
  const slideVariants = {
    enter: (direction: "left" | "right") => ({
      x: direction === "left" ? 1000 : -1000,
      opacity: 0,
    }),
    center: {
      x: 0,
      opacity: 1,
    },
    exit: (direction: "left" | "right") => ({
      x: direction === "left" ? -1000 : 1000,
      opacity: 0,
    }),
  };

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
              className="absolute left-4 top-1/2 -translate-y-1/2 z-30 bg-background/80 hover:bg-background"
              onClick={handlePrevious}
              disabled={!canGoPrevious}
            >
              <ChevronLeft className="h-6 w-6" />
            </Button>

            <Button
              variant="ghost"
              size="icon"
              className="absolute right-4 top-1/2 -translate-y-1/2 z-30 bg-background/80 hover:bg-background"
              onClick={handleNext}
              disabled={!canGoNext}
            >
              <ChevronRight className="h-6 w-6" />
            </Button>

            {/* Close Button */}
            <Button
              variant="ghost"
              size="icon"
              className="absolute top-4 left-4 z-30 bg-background/80 hover:bg-background"
              onClick={() => onOpenChange(false)}
            >
              <X className="h-5 w-5" />
            </Button>

            {/* Image Counter */}
            <div className="absolute top-4 left-1/2 -translate-x-1/2 z-30 bg-background/80 px-3 py-1 rounded-full text-sm">
              {currentIndex + 1} / {items.length}
            </div>

            {/* Image Display */}
            <AnimatePresence initial={false} custom={direction} mode="popLayout">
              <motion.div
                key={item.id}
                custom={direction}
                variants={slideVariants}
                initial="enter"
                animate="center"
                exit="exit"
                transition={{
                  x: { type: "spring", stiffness: 400, damping: 35 },
                  opacity: { duration: 0.15 },
                }}
                className="absolute inset-0 flex items-center justify-center"
              >
                {item.type === "Image" && imageUrl ? (
                  <div className="relative w-full h-full max-h-full">
                    {/* Blurhash placeholder - always render, fade out when image loads */}
                    {item.blurhash && (
                      <div 
                        className={`absolute inset-0 flex items-center justify-center z-10 transition-opacity duration-700 ${
                          imageLoaded ? "opacity-0" : "opacity-100"
                        }`}
                        style={{ pointerEvents: imageLoaded ? "none" : "auto" }}
                      >
                        <Blurhash
                          hash={item.blurhash}
                          width={blurhashDims.width}
                          height={blurhashDims.height}
                          resolutionX={32}
                          resolutionY={32}
                          punch={1}
                        />
                      </div>
                    )}
                    
                    {/* Image - fades in when loaded */}
                    <Image
                      src={imageUrl}
                      alt={item.name}
                      fill
                      className={`object-contain max-h-full z-20 transition-opacity duration-700 ease-in-out ${
                        imageLoaded ? "opacity-100" : "opacity-0"
                      }`}
                      unoptimized
                      priority
                      onLoad={() => setImageLoaded(true)}
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
              </motion.div>
            </AnimatePresence>
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

                    {/* Database Information */}
                    <div className="space-y-3">
                      <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
                        AI Analysis
                      </h3>
                      
                      {metadata ? (
                        <div className="space-y-4">
                          {/* CLIP Caption */}
                          {metadata.embedding?.caption && (
                            <div className="space-y-2">
                              <div className="flex items-center gap-2">
                                <ImageIcon className="h-4 w-4 text-muted-foreground" />
                                <span className="text-xs font-medium text-muted-foreground">
                                  AI Caption
                                </span>
                              </div>
                              <p className="text-sm bg-muted/50 p-2 rounded">
                                {metadata.embedding.caption}
                              </p>
                            </div>
                          )}

                          {/* Detected Types */}
                          {metadata.attributes && (
                            <div className="space-y-2">
                              <div className="flex items-center gap-2">
                                <Tag className="h-4 w-4 text-muted-foreground" />
                                <span className="text-xs font-medium text-muted-foreground">
                                  Detected Types
                                </span>
                              </div>
                              <div className="flex flex-wrap gap-2">
                                {metadata.attributes.isDocument && (
                                  <Badge variant="secondary" className="text-xs">
                                    <FileText className="h-3 w-3 mr-1" />
                                    Document ({(metadata.attributes.documentProb * 100).toFixed(0)}%)
                                  </Badge>
                                )}
                                {metadata.attributes.hasPeople && (
                                  <Badge variant="secondary" className="text-xs">
                                    <Users className="h-3 w-3 mr-1" />
                                    People ({(metadata.attributes.peopleProb * 100).toFixed(0)}%)
                                  </Badge>
                                )}
                                {metadata.attributes.isScreenshot && (
                                  <Badge variant="secondary" className="text-xs">
                                    <Camera className="h-3 w-3 mr-1" />
                                    Screenshot ({(metadata.attributes.screenshotProb * 100).toFixed(0)}%)
                                  </Badge>
                                )}
                                {metadata.attributes.isAnimal && (
                                  <Badge variant="secondary" className="text-xs">
                                    🐾 Animal ({(metadata.attributes.animalProb * 100).toFixed(0)}%)
                                  </Badge>
                                )}
                              </div>
                            </div>
                          )}

                          {/* NIMA Score */}
                          {metadata.attributes?.nimaScore && (
                            <div className="space-y-2">
                              <div className="flex items-center gap-2">
                                <Star className="h-4 w-4 text-muted-foreground" />
                                <span className="text-xs font-medium text-muted-foreground">
                                  Quality Score (NIMA)
                                </span>
                              </div>
                              <div className="space-y-1">
                                <div className="flex justify-between items-center">
                                  <span className="text-xs text-muted-foreground">Overall</span>
                                  <span className="text-sm font-medium">
                                    {metadata.attributes.nimaScore.toFixed(2)} / 10
                                  </span>
                                </div>
                                {metadata.attributes.nimaTechnical && (
                                  <div className="flex justify-between items-center">
                                    <span className="text-xs text-muted-foreground">Technical</span>
                                    <span className="text-sm">
                                      {metadata.attributes.nimaTechnical.toFixed(2)} / 10
                                    </span>
                                  </div>
                                )}
                                {metadata.attributes.nimaAesthetic && (
                                  <div className="flex justify-between items-center">
                                    <span className="text-xs text-muted-foreground">Aesthetic</span>
                                    <span className="text-sm">
                                      {metadata.attributes.nimaAesthetic.toFixed(2)} / 10
                                    </span>
                                  </div>
                                )}
                              </div>
                            </div>
                          )}

                          {/* Detected Faces */}
                          {metadata.faces && metadata.faces.length > 0 && (
                            <div className="space-y-2">
                              <div className="flex items-center gap-2">
                                <Users className="h-4 w-4 text-muted-foreground" />
                                <span className="text-xs font-medium text-muted-foreground">
                                  Detected Faces ({metadata.faces.length})
                                </span>
                              </div>
                              <div className="space-y-1">
                                {metadata.faces.map((face, index) => (
                                  <div key={face.id} className="flex justify-between items-center text-sm">
                                    <span className="text-muted-foreground">
                                      {face.personName || `Unknown Person ${index + 1}`}
                                    </span>
                                    {face.confidence && (
                                      <span className="text-xs text-muted-foreground">
                                        {(face.confidence * 100).toFixed(0)}%
                                      </span>
                                    )}
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}

                          {/* OCR Results */}
                          {metadata.ocrResults && metadata.ocrResults.length > 0 && (
                            <div className="space-y-2">
                              <div className="flex items-center gap-2">
                                <FileText className="h-4 w-4 text-muted-foreground" />
                                <span className="text-xs font-medium text-muted-foreground">
                                  Extracted Text (OCR)
                                </span>
                              </div>
                              <div className="max-h-32 overflow-y-auto">
                                <p className="text-xs bg-muted/50 p-2 rounded whitespace-pre-wrap">
                                  {metadata.ocrResults[0].text}
                                </p>
                              </div>
                            </div>
                          )}

                          {/* Processing Status */}
                          <div className="space-y-2">
                            <div className="flex items-center gap-2">
                              <Clock className="h-4 w-4 text-muted-foreground" />
                              <span className="text-xs font-medium text-muted-foreground">
                                Processing Status
                              </span>
                            </div>
                            <Badge 
                              variant={metadata.processingStatus === 'completed' ? 'default' : 'secondary'}
                              className="text-xs"
                            >
                              {metadata.processingStatus}
                            </Badge>
                          </div>
                        </div>
                      ) : (
                        <p className="text-sm text-muted-foreground italic">
                          No AI analysis data available
                        </p>
                      )}
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
            <div className="p-4 border-t space-y-2">
              <Button onClick={handleDownload} className="w-full" variant="default">
                <Download className="h-4 w-4 mr-2" />
                Download
              </Button>
              <Button 
                onClick={() => setShowDeleteDialog(true)} 
                className="w-full" 
                variant="destructive"
              >
                <Trash2 className="h-4 w-4 mr-2" />
                Delete
              </Button>
            </div>
          </div>
        </div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Are you sure?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently delete <strong>{item?.name}</strong> from both the database and blob storage. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isDeleting}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              disabled={isDeleting}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {isDeleting ? "Deleting..." : "Delete"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </Dialog>
  );
}
