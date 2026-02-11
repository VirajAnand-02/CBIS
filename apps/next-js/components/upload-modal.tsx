"use client";

import { useState, useRef } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Upload, File, X, CheckCircle, AlertCircle } from "lucide-react";
import { cn } from "@/lib/utils";

interface UploadModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  mode: "file" | "folder";
  onUploadComplete?: (ids: string[]) => void;
}

interface FileUploadState {
  file: File;
  status: "pending" | "uploading" | "success" | "error";
  progress: number;
  id?: string;
  error?: string;
}

export function UploadModal({ open, onOpenChange, mode, onUploadComplete }: UploadModalProps) {
  const [files, setFiles] = useState<FileUploadState[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [isDragOver, setIsDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileSelect = (selectedFiles: FileList | null) => {
    if (!selectedFiles) return;

    const newFiles: FileUploadState[] = Array.from(selectedFiles).map((file) => ({
      file,
      status: "pending",
      progress: 0,
    }));

    setFiles((prev) => [...prev, ...newFiles]);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);

    const droppedFiles = e.dataTransfer.files;
    handleFileSelect(droppedFiles);
  };

  const removeFile = (index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const uploadFile = async (file: File): Promise<{ id?: string; error?: string }> => {
    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await fetch("/api/blobs", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || "Upload failed");
      }

      const result = await response.json();
      return { id: result.id };
    } catch (error) {
      return { error: error instanceof Error ? error.message : "Upload failed" };
    }
  };

  const handleUploadAll = async () => {
    if (files.length === 0) return;

    setIsUploading(true);
    const uploadedIds: string[] = [];

    for (let i = 0; i < files.length; i++) {
      const fileState = files[i];
      if (fileState.status !== "pending") continue;

      // Update status to uploading
      setFiles((prev) =>
        prev.map((f, idx) => (idx === i ? { ...f, status: "uploading", progress: 50 } : f))
      );

      const result = await uploadFile(fileState.file);

      if (result.id) {
        uploadedIds.push(result.id);
        setFiles((prev) =>
          prev.map((f, idx) =>
            idx === i ? { ...f, status: "success", progress: 100, id: result.id } : f
          )
        );
      } else {
        setFiles((prev) =>
          prev.map((f, idx) =>
            idx === i ? { ...f, status: "error", progress: 0, error: result.error } : f
          )
        );
      }
    }

    setIsUploading(false);
    
    if (uploadedIds.length > 0) {
      onUploadComplete?.(uploadedIds);
    }
  };

  const handleClose = () => {
    if (!isUploading) {
      setFiles([]);
      onOpenChange(false);
    }
  };

  const pendingCount = files.filter((f) => f.status === "pending").length;
  const successCount = files.filter((f) => f.status === "success").length;
  const errorCount = files.filter((f) => f.status === "error").length;

  return (
    <>
      <input
        ref={fileInputRef}
        type="file"
        multiple={mode === "file"}
        {...(mode === "folder" ? { webkitdirectory: "", directory: "" } : {})}
        onChange={(e) => handleFileSelect(e.target.files)}
        className="hidden"
      />

      <Dialog open={open} onOpenChange={handleClose}>
        <DialogContent className="max-w-2xl max-h-[80vh] flex flex-col">
          <DialogHeader>
            <DialogTitle>
              {mode === "file" ? "Upload Files" : "Upload Folder"}
            </DialogTitle>
            <DialogDescription>
              {mode === "file"
                ? "Select one or more files to upload to storage"
                : "Select a folder to upload all its contents"}
            </DialogDescription>
          </DialogHeader>

          <div className="flex-1 overflow-y-auto space-y-4">
            {/* Upload Area */}
            {files.length === 0 && (
              <div
                onClick={() => fileInputRef.current?.click()}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                className={cn(
                  "border-2 border-dashed rounded-lg p-12 text-center cursor-pointer transition-colors",
                  isDragOver
                    ? "border-primary bg-primary/5"
                    : "border-muted-foreground/25 hover:border-muted-foreground/50"
                )}
              >
                <Upload className="h-12 w-12 mx-auto mb-4 text-muted-foreground" />
                <p className="text-sm text-muted-foreground mb-2">
                  {isDragOver ? "Drop files here" : "Click to browse or drag and drop"}
                </p>
                <p className="text-xs text-muted-foreground">
                  {mode === "file" ? "Select files to upload" : "Select a folder to upload"}
                </p>
              </div>
            )}

            {/* File List */}
            {files.length > 0 && (
              <div className="space-y-3">
                {/* Always-on Drop Zone */}
                <div
                  onClick={() => fileInputRef.current?.click()}
                  onDragOver={handleDragOver}
                  onDragLeave={handleDragLeave}
                  onDrop={handleDrop}
                  className={cn(
                    "border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors",
                    isDragOver
                      ? "border-primary bg-primary/10"
                      : "border-muted-foreground/25 hover:border-muted-foreground/50"
                  )}
                >
                  <Upload className={cn(
                    "h-8 w-8 mx-auto mb-2",
                    isDragOver ? "text-primary" : "text-muted-foreground"
                  )} />
                  <p className={cn(
                    "text-sm font-medium",
                    isDragOver ? "text-primary" : "text-muted-foreground"
                  )}>
                    {isDragOver ? "Drop to add more files" : "Click or drag files here to add more"}
                  </p>
                </div>

                <div className="flex items-center justify-between">
                  <p className="text-sm font-medium">
                    {files.length} file{files.length !== 1 ? "s" : ""} selected
                  </p>
                </div>

                <div className="space-y-2 max-h-[400px] overflow-y-auto">
                  {files.map((fileState, index) => (
                    <div
                      key={index}
                      className={cn(
                        "flex items-center gap-3 p-3 rounded-lg border",
                        fileState.status === "success" && "bg-green-50 dark:bg-green-950/20",
                        fileState.status === "error" && "bg-red-50 dark:bg-red-950/20"
                      )}
                    >
                      <File className="h-5 w-5 shrink-0 text-muted-foreground" />
                      
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium truncate">{fileState.file.name}</p>
                        <p className="text-xs text-muted-foreground">
                          {(fileState.file.size / 1024).toFixed(2)} KB
                        </p>
                        {fileState.status === "uploading" && (
                          <Progress value={fileState.progress} className="mt-2 h-1" />
                        )}
                        {fileState.status === "error" && (
                          <p className="text-xs text-red-600 dark:text-red-400 mt-1">
                            {fileState.error}
                          </p>
                        )}
                      </div>

                      {fileState.status === "success" && (
                        <CheckCircle className="h-5 w-5 text-green-600 dark:text-green-400" />
                      )}
                      {fileState.status === "error" && (
                        <AlertCircle className="h-5 w-5 text-red-600 dark:text-red-400" />
                      )}
                      {fileState.status === "pending" && !isUploading && (
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8"
                          onClick={() => removeFile(index)}
                        >
                          <X className="h-4 w-4" />
                        </Button>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Footer */}
          {files.length > 0 && (
            <div className="flex items-center justify-between pt-4 border-t">
              <div className="text-sm text-muted-foreground">
                {successCount > 0 && (
                  <span className="text-green-600 dark:text-green-400">
                    {successCount} uploaded
                  </span>
                )}
                {errorCount > 0 && (
                  <span className="text-red-600 dark:text-red-400 ml-3">
                    {errorCount} failed
                  </span>
                )}
              </div>

              <div className="flex gap-2">
                <Button variant="outline" onClick={handleClose} disabled={isUploading}>
                  {successCount > 0 && pendingCount === 0 ? "Done" : "Cancel"}
                </Button>
                {pendingCount > 0 && (
                  <Button onClick={handleUploadAll} disabled={isUploading}>
                    {isUploading ? "Uploading..." : `Upload ${pendingCount} file${pendingCount !== 1 ? "s" : ""}`}
                  </Button>
                )}
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
