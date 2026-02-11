"use client";

import { AppSidebar } from "@/components/app-sidebar";
import { ThemeToggle } from "@/components/theme-toggle";
import { Card, CardContent } from "@/components/ui/card";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Users, User, Loader2, ImageIcon } from "lucide-react";
import { UploadModal } from "@/components/upload-modal";
import { useState, useEffect } from "react";
import Link from "next/link";

interface Person {
  id: string;
  name: string | null;
  thumbnail: string | null;
  faceCount: number;
  tags: string[];
  createdAt: string;
}

export default function PeoplesPage() {
  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  const [uploadMode, setUploadMode] = useState<"file" | "folder">("file");
  const [persons, setPersons] = useState<Person[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchPersons();
  }, []);

  const fetchPersons = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await fetch('/api/persons?threshold=5');
      if (!response.ok) {
        throw new Error('Failed to fetch persons');
      }
      const data = await response.json();
      setPersons(data.persons);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setIsLoading(false);
    }
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
    fetchPersons();
  };

  const getInitials = (name: string | null) => {
    if (!name) return null;
    return name
      .split(' ')
      .map(word => word.charAt(0))
      .join('')
      .toUpperCase()
      .slice(0, 2);
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
            <Users className="h-6 w-6" />
            <h1 className="text-2xl font-bold tracking-tight">People</h1>
            {!isLoading && persons.length > 0 && (
              <Badge variant="secondary">{persons.length}</Badge>
            )}
          </div>
          <ThemeToggle />
        </div>
      </div>
    </header>

    {/* Main Content */}
    <main className="container mx-auto px-4 py-8 flex-1">
      {/* Loading State */}
      {isLoading && (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-16">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground mb-4" />
            <p className="text-sm text-muted-foreground">Loading people...</p>
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

      {/* Empty State */}
      {!isLoading && !error && persons.length === 0 && (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-16">
            <ImageIcon className="h-16 w-16 text-muted-foreground/50 mb-4" />
            <p className="text-lg font-semibold mb-2">
              No People Discovered Yet
            </p>
            <p className="text-sm text-muted-foreground text-center max-w-md">
              Upload images with faces to start detecting and grouping people.
            </p>
          </CardContent>
        </Card>
      )}

      {/* People Grid - Circular Avatars */}
      {!isLoading && !error && persons.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-6">
          {persons.map((person) => (
            <Link 
              key={person.id} 
              href={`/peoples/${person.id}`}
              className="flex flex-col items-center group"
            >
              {/* Circular Avatar */}
              <div className="relative mb-3">
                <Avatar className="h-24 w-24 border-2 border-background group-hover:border-primary/50 transition-all duration-200 shadow-md group-hover:shadow-lg">
                  {person.thumbnail && (
                    <AvatarImage 
                      src={person.thumbnail} 
                      alt={person.name || `Person ${person.id.slice(0, 8)}`}
                      className="object-cover"
                    />
                  )}
                  <AvatarFallback className="text-2xl font-semibold bg-linear-to-br from-primary/20 to-primary/10">
                    {person.name 
                      ? getInitials(person.name)
                      : <User className="h-10 w-10 text-muted-foreground" />
                    }
                  </AvatarFallback>
                </Avatar>
                
                {/* Face Count Badge */}
                <Badge 
                  variant="secondary" 
                  className="absolute -bottom-1 -right-1 h-6 min-w-6 flex items-center justify-center px-1.5 text-xs font-semibold"
                >
                  {person.faceCount}
                </Badge>
              </div>

              {/* Name */}
              <p className="text-sm font-medium text-center max-w-[120px] truncate group-hover:text-primary transition-colors">
                {person.name || `Person ${person.id.slice(0, 8)}`}
              </p>
            </Link>
          ))}
        </div>
      )}
    </main>
  </div>      {/* Upload Modal */}
      <UploadModal
        open={uploadModalOpen}
        onOpenChange={setUploadModalOpen}
        mode={uploadMode}
        onUploadComplete={handleUploadComplete}
      />
    </div>
  );
}
