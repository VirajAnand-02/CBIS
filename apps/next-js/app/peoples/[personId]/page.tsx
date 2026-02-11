"use client";

import { AppSidebar } from "@/components/app-sidebar";
import { ThemeToggle } from "@/components/theme-toggle";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { MediaGrid } from "@/components/media-grid";
import { MediaItem } from "@/components/media-card";
import { UploadModal } from "@/components/upload-modal";
import { ImageViewModal } from "@/components/image-view-modal";
import { User, ArrowLeft, Loader2, Pencil, Check, X, Image as ImageIcon } from "lucide-react";
import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";

interface Person {
  id: string;
  name: string | null;
  thumbnail: string | null;
  faceCount: number;
  tags: string[];
  notes: string | null;
  createdAt: string;
}

interface FaceInstance {
  id: string;
  blobId: string;
  boundingBox: { x: number; y: number; w: number; h: number };
  confidence: number;
  quality: number | null;
  createdAt: string;
}

export default function PersonDetailPage() {
  const params = useParams();
  const personId = params.personId as string;

  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  const [uploadMode, setUploadMode] = useState<"file" | "folder">("file");
  const [selectedItem, setSelectedItem] = useState<MediaItem | null>(null);
  const [imageViewOpen, setImageViewOpen] = useState(false);
  
  const [person, setPerson] = useState<Person | null>(null);
  const [blobIds, setBlobIds] = useState<string[]>([]);
  const [blobItems, setBlobItems] = useState<MediaItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [isEditing, setIsEditing] = useState(false);
  const [editedName, setEditedName] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  const fetchPersonData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      // Fetch person details
      const personResponse = await fetch(`/api/persons/${personId}`);
      if (!personResponse.ok) {
        throw new Error('Failed to fetch person details');
      }
      const personData = await personResponse.json();
      setPerson(personData);
      setEditedName(personData.name || "");

      // Fetch face instances
      const facesResponse = await fetch(`/api/persons/${personId}/faces`);
      if (!facesResponse.ok) {
        throw new Error('Failed to fetch face instances');
      }
      const facesData = await facesResponse.json();

      // Extract unique blob IDs
      const uniqueBlobIds = Array.from(
        new Set(facesData.faces.map((f: FaceInstance) => f.blobId))
      ) as string[];
      setBlobIds(uniqueBlobIds);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setIsLoading(false);
    }
  }, [personId]);

  useEffect(() => {
    if (personId) {
      fetchPersonData();
    }
  }, [personId, fetchPersonData]);

  // Fetch blob metadata for MediaGrid
  useEffect(() => {
    const fetchBlobMetadata = async () => {
      if (blobIds.length === 0) {
        setBlobItems([]);
        return;
      }

      try {
        const promises = blobIds.map(async (id) => {
          const response = await fetch(`/api/blobs/${id}/metadata`);
          if (!response.ok) return null;
          const blob = await response.json();
          
          return {
            id: blob.id,
            name: blob.filename,
            type: blob.mimeType.startsWith('image/') ? 'Image' as const : 'Video' as const,
            date: new Date(blob.uploadedAt),
            size: `${(blob.size / 1024 / 1024).toFixed(2)} MB`,
            blobId: blob.id,
            thumbnailUrl: `/api/blobs/${blob.id}/thumbnail`,
            mimeType: blob.mimeType,
            blurhash: blob.blurhash,
            width: blob.width,
            height: blob.height,
          } as MediaItem;
        });

        const results = await Promise.all(promises);
        const items = results.filter((item): item is MediaItem => item !== null);
        setBlobItems(items);
      } catch (error) {
        console.error('Failed to fetch blob metadata:', error);
      }
    };

    fetchBlobMetadata();
  }, [blobIds]);

  const handleSaveName = async () => {
    if (!person) return;
    
    setIsSaving(true);
    try {
      const response = await fetch(`/api/persons/${personId}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ name: editedName }),
      });

      if (!response.ok) {
        throw new Error('Failed to update person name');
      }

      const updatedPerson = await response.json();
      setPerson(updatedPerson);
      setIsEditing(false);
    } catch (err) {
      console.error('Error updating name:', err);
      alert('Failed to update name. Please try again.');
    } finally {
      setIsSaving(false);
    }
  };

  const handleCancelEdit = () => {
    setEditedName(person?.name || "");
    setIsEditing(false);
  };

  const handleUploadImage = () => {
    setUploadMode("file");
    setUploadModalOpen(true);
  };

  const handleUploadFolder = () => {
    setUploadMode("folder");
    setUploadModalOpen(true);
  };

  const handleUploadComplete = (ids: string[]) => {
    console.log("Uploaded blob IDs:", ids);
    fetchPersonData(); // Refresh data
  };

  const handleImageClick = (item: MediaItem) => {
    setSelectedItem(item);
    setImageViewOpen(true);
  };

  return (
    <div className="flex min-h-screen bg-linear-to-b from-background to-muted/20">
      {/* Sidebar */}
      <AppSidebar 
        onUploadImage={handleUploadImage} 
        onUploadFolder={handleUploadFolder}
        currentPage="peoples"
      />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <header className="border-b bg-background/95 backdrop-blur supports-backdrop-filter:bg-background/60 sticky top-0 z-50">
          <div className="container mx-auto px-4 py-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Link href="/peoples">
                  <Button variant="ghost" size="icon">
                    <ArrowLeft className="h-5 w-5" />
                  </Button>
                </Link>
                <User className="h-6 w-6" />
                <h1 className="text-2xl font-bold tracking-tight">
                  {person?.name || `Person ${personId.slice(0, 8)}`}
                </h1>
                {person && (
                  <Badge variant="secondary">
                    {person.faceCount} {person.faceCount === 1 ? 'instance' : 'instances'}
                  </Badge>
                )}
              </div>
              <ThemeToggle />
            </div>
          </div>
        </header>

        {/* Main Content */}
        <main className="container mx-auto px-4 py-8 flex-1">
          <div className="space-y-6">
            {/* Loading State */}
            {isLoading && (
              <Card>
                <CardContent className="flex flex-col items-center justify-center py-16">
                  <Loader2 className="h-8 w-8 animate-spin text-muted-foreground mb-4" />
                  <p className="text-sm text-muted-foreground">Loading person details...</p>
                </CardContent>
              </Card>
            )}

            {/* Error State */}
            {error && (
              <Card>
                <CardContent className="flex flex-col items-center justify-center py-16">
                  <p className="text-sm text-destructive">{error}</p>
                </CardContent>
              </Card>
            )}

            {/* Person Info Card */}
            {!isLoading && !error && person && (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <User className="h-5 w-5" />
                    Person Information
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="flex items-start gap-6">
                    {/* Avatar */}
                    <Avatar className="h-24 w-24 shrink-0">
                      {person.thumbnail && (
                        <AvatarImage 
                          src={person.thumbnail} 
                          alt={person.name || `Person ${person.id.slice(0, 8)}`}
                          className="object-cover"
                        />
                      )}
                      <AvatarFallback className="text-4xl">
                        {person.name 
                          ? person.name.charAt(0).toUpperCase() 
                          : <User className="h-12 w-12 text-muted-foreground" />
                        }
                      </AvatarFallback>
                    </Avatar>

                    {/* Name Editor */}
                    <div className="flex-1 space-y-4">
                      <div className="space-y-2">
                        <Label htmlFor="name">Name</Label>
                        {isEditing ? (
                          <div className="flex gap-2">
                            <Input
                              id="name"
                              value={editedName}
                              onChange={(e) => setEditedName(e.target.value)}
                              placeholder="Enter person's name"
                              disabled={isSaving}
                              className="flex-1"
                            />
                            <Button 
                              size="icon" 
                              onClick={handleSaveName}
                              disabled={isSaving || !editedName.trim()}
                            >
                              {isSaving ? (
                                <Loader2 className="h-4 w-4 animate-spin" />
                              ) : (
                                <Check className="h-4 w-4" />
                              )}
                            </Button>
                            <Button 
                              size="icon" 
                              variant="outline" 
                              onClick={handleCancelEdit}
                              disabled={isSaving}
                            >
                              <X className="h-4 w-4" />
                            </Button>
                          </div>
                        ) : (
                          <div className="flex gap-2 items-center">
                            <p className="text-lg font-medium flex-1">
                              {person.name || <span className="text-muted-foreground">Unnamed Person</span>}
                            </p>
                            <Button 
                              size="sm" 
                              variant="outline" 
                              onClick={() => setIsEditing(true)}
                            >
                              <Pencil className="h-4 w-4 mr-2" />
                              Edit Name
                            </Button>
                          </div>
                        )}
                      </div>

                      {/* Additional Info */}
                      <div className="grid grid-cols-2 gap-4 text-sm">
                        <div>
                          <p className="text-muted-foreground">Face Instances</p>
                          <p className="font-medium">{person.faceCount}</p>
                        </div>
                        <div>
                          <p className="text-muted-foreground">Unique Images</p>
                          <p className="font-medium">{blobIds.length}</p>
                        </div>
                        <div>
                          <p className="text-muted-foreground">First Seen</p>
                          <p className="font-medium">
                            {new Date(person.createdAt).toLocaleDateString()}
                          </p>
                        </div>
                        {person.tags && person.tags.length > 0 && (
                          <div>
                            <p className="text-muted-foreground mb-1">Tags</p>
                            <div className="flex flex-wrap gap-1">
                              {person.tags.map((tag, idx) => (
                                <Badge key={idx} variant="secondary" className="text-xs">
                                  {tag}
                                </Badge>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>

                      {person.notes && (
                        <div>
                          <p className="text-sm text-muted-foreground mb-1">Notes</p>
                          <p className="text-sm">{person.notes}</p>
                        </div>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Images Grid */}
            {!isLoading && !error && blobIds.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <ImageIcon className="h-5 w-5" />
                    Images ({blobIds.length})
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <MediaGrid items={blobItems} onItemClick={handleImageClick} />
                </CardContent>
              </Card>
            )}

            {/* No Images State */}
            {!isLoading && !error && blobIds.length === 0 && person && (
              <Card>
                <CardContent className="flex flex-col items-center justify-center py-16">
                  <ImageIcon className="h-16 w-16 text-muted-foreground/50 mb-4" />
                  <p className="text-lg font-semibold mb-2">
                    No Images Found
                  </p>
                  <p className="text-sm text-muted-foreground">
                    This person has no associated images yet.
                  </p>
                </CardContent>
              </Card>
            )}
          </div>
        </main>
      </div>

      {/* Upload Modal */}
      <UploadModal
        open={uploadModalOpen}
        onOpenChange={setUploadModalOpen}
        mode={uploadMode}
        onUploadComplete={handleUploadComplete}
      />

      {/* Image View Modal */}
      <ImageViewModal
        open={imageViewOpen}
        onOpenChange={setImageViewOpen}
        item={selectedItem}
        items={blobItems}
      />
    </div>
  );
}
