"use client";

import { AppSidebar } from "@/components/app-sidebar";
import { ThemeToggle } from "@/components/theme-toggle";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tags, Sparkles, Grid3x3, Layers } from "lucide-react";
import { UploadModal } from "@/components/upload-modal";
import { useState } from "react";

export default function ClusteringPage() {
  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  const [uploadMode, setUploadMode] = useState<"file" | "folder">("file");

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
    // TODO: Trigger re-clustering
  };

  return (
    <div className="flex min-h-screen bg-linear-to-b from-background to-muted/20">
      {/* Sidebar */}
      <AppSidebar 
        onUploadImage={handleUploadImage} 
        onUploadFolder={handleUploadFolder}
        currentPage="clustering"
      />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <header className="border-b bg-background/95 backdrop-blur supports-backdrop-filter:bg-background/60 sticky top-0 z-50">
          <div className="container mx-auto px-4 py-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Tags className="h-6 w-6" />
                <h1 className="text-2xl font-bold tracking-tight">Smart Tags & Clustering</h1>
              </div>
              <ThemeToggle />
            </div>
          </div>
        </header>

        {/* Main Content */}
        <main className="container mx-auto px-4 py-8 flex-1">
          <div className="space-y-6">
            {/* Page Description */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Sparkles className="h-5 w-5" />
                  Intelligent Image Organization
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-muted-foreground">
                  Automatically organize your images using AI-powered clustering. 
                  Images are grouped by visual similarity, content, and context to help you discover patterns and organize your collection.
                </p>
              </CardContent>
            </Card>

            {/* Features Grid */}
            <div className="grid md:grid-cols-2 gap-6">
              {/* CLIP Clustering */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-lg">
                    <Grid3x3 className="h-5 w-5" />
                    CLIP-based Clustering
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground">
                    Group images by visual and semantic similarity using CLIP embeddings. 
                    Discover similar scenes, objects, and concepts across your entire library.
                  </p>
                </CardContent>
              </Card>

              {/* Smart Tagging */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-lg">
                    <Tags className="h-5 w-5" />
                    Automated Smart Tags
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground">
                    Automatically generate and apply tags based on image content, detected objects, 
                    scenes, and metadata to make your images easily searchable.
                  </p>
                </CardContent>
              </Card>

              {/* Hierarchical Organization */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-lg">
                    <Layers className="h-5 w-5" />
                    Hierarchical Organization
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground">
                    Create hierarchical tag structures and clusters to organize large collections. 
                    Navigate from broad categories to specific groups effortlessly.
                  </p>
                </CardContent>
              </Card>

              {/* Quality Analysis */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-lg">
                    <Sparkles className="h-5 w-5" />
                    Quality Analysis
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground">
                    Identify and filter images by quality metrics. 
                    Find your best shots and manage duplicates or similar images.
                  </p>
                </CardContent>
              </Card>
            </div>

            {/* TODO: Placeholder for Clusters */}
            <Card>
              <CardContent className="flex flex-col items-center justify-center py-16">
                <Grid3x3 className="h-16 w-16 text-muted-foreground/50 mb-4" />
                <p className="text-lg font-semibold mb-2">
                  TODO: Clustering System Coming Soon
                </p>
                <p className="text-sm text-muted-foreground text-center max-w-md">
                  The intelligent clustering and smart tagging system is currently being developed. 
                  Once ready, your images will be automatically organized and tagged.
                </p>
              </CardContent>
            </Card>

            {/* TODO: Add cluster visualization here */}
            {/* Example structure:
            <div className="space-y-8">
              {clusters.map((cluster) => (
                <div key={cluster.id}>
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-lg font-semibold">{cluster.name}</h3>
                    <Badge variant="secondary">{cluster.imageCount} images</Badge>
                  </div>
                  <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
                    {cluster.images.map((img) => (
                      <Card key={img.id} className="overflow-hidden">
                        <img src={img.url} alt="" className="w-full aspect-square object-cover" />
                      </Card>
                    ))}
                  </div>
                </div>
              ))}
            </div>
            */}
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
    </div>
  );
}
