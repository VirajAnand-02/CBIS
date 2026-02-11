"use client";

import { useState } from "react";
import { ChevronLeft, ChevronRight, FolderUp, Image as ImageIcon, Loader2, Home, Users, Tags } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { usePreprocessingStatus } from "@/hooks/use-preprocessing-status";
import Link from "next/link";

interface AppSidebarProps {
  onUploadImage?: () => void;
  onUploadFolder?: () => void;
  currentPage?: "home" | "peoples" | "clustering";
}

export function AppSidebar({ onUploadImage, onUploadFolder, currentPage = "home" }: AppSidebarProps) {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const { processingCount } = usePreprocessingStatus();

  return (
    <aside
      className={cn(
        "sticky top-0 h-screen border-r bg-background/95 backdrop-blur supports-backdrop-filter:bg-background/60 transition-all duration-300 flex flex-col",
        isCollapsed ? "w-14" : "w-46"
      )}
    >
      {/* Logo Section */}
      <div className="flex items-center justify-center p-4 h-[72px]">
        {!isCollapsed && (
          <h1 className="text-2xl font-bold tracking-tight ">___CBIS___</h1>
        )}
        {isCollapsed && (
          <h1 className="text-2xl font-bold tracking-tight mx-auto">CB</h1>
        )}
      </div>

      <Separator />

      {/* Navigation/Actions */}
      <div className="flex-1 overflow-y-auto py-4">
        <div className="space-y-1 px-2">
          <TooltipProvider delayDuration={0}>
            {/* Navigation Tabs */}
            <div className="space-y-1 mb-4">
              {/* Home Tab */}
              <Tooltip>
                <TooltipTrigger asChild>
                  <Link href="/" passHref>
                    <Button
                      variant={currentPage === "home" ? "secondary" : "ghost"}
                      className={cn(
                        "w-full justify-start",
                        isCollapsed && "justify-center px-2"
                      )}
                    >
                      <Home className={cn("h-5 w-5", !isCollapsed && "mr-3")} />
                      {!isCollapsed && <span>Home</span>}
                    </Button>
                  </Link>
                </TooltipTrigger>
                {isCollapsed && (
                  <TooltipContent side="right">
                    <p>Home</p>
                  </TooltipContent>
                )}
              </Tooltip>

              {/* Peoples Tab */}
              <Tooltip>
                <TooltipTrigger asChild>
                  <Link href="/peoples" passHref>
                    <Button
                      variant={currentPage === "peoples" ? "secondary" : "ghost"}
                      className={cn(
                        "w-full justify-start",
                        isCollapsed && "justify-center px-2"
                      )}
                    >
                      <Users className={cn("h-5 w-5", !isCollapsed && "mr-3")} />
                      {!isCollapsed && <span>Peoples</span>}
                    </Button>
                  </Link>
                </TooltipTrigger>
                {isCollapsed && (
                  <TooltipContent side="right">
                    <p>Peoples</p>
                  </TooltipContent>
                )}
              </Tooltip>

              {/* Clustering / Smart Tags Tab */}
              <Tooltip>
                <TooltipTrigger asChild>
                  <Link href="/clustering" passHref>
                    <Button
                      variant={currentPage === "clustering" ? "secondary" : "ghost"}
                      className={cn(
                        "w-full justify-start",
                        isCollapsed && "justify-center px-2"
                      )}
                    >
                      <Tags className={cn("h-5 w-5", !isCollapsed && "mr-3")} />
                      {!isCollapsed && <span>Smart Tags</span>}
                    </Button>
                  </Link>
                </TooltipTrigger>
                {isCollapsed && (
                  <TooltipContent side="right">
                    <p>Smart Tags</p>
                  </TooltipContent>
                )}
              </Tooltip>
            </div>

            <Separator className="my-2" />

            {/* Upload Actions */}
            <div className="space-y-1">
              {/* Upload Image */}
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    className={cn(
                      "w-full justify-start",
                      isCollapsed && "justify-center px-2"
                    )}
                    onClick={onUploadImage}
                  >
                    <ImageIcon className={cn("h-5 w-5", !isCollapsed && "mr-3")} />
                    {!isCollapsed && <span>Upload Image</span>}
                  </Button>
                </TooltipTrigger>
                {isCollapsed && (
                  <TooltipContent side="right">
                    <p>Upload Image</p>
                  </TooltipContent>
                )}
              </Tooltip>

              {/* Upload Folder */}
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    className={cn(
                      "w-full justify-start",
                      isCollapsed && "justify-center px-2"
                    )}
                    onClick={onUploadFolder}
                  >
                    <FolderUp className={cn("h-5 w-5", !isCollapsed && "mr-3")} />
                    {!isCollapsed && <span>Upload Folder</span>}
                  </Button>
                </TooltipTrigger>
                {isCollapsed && (
                  <TooltipContent side="right">
                    <p>Upload Folder</p>
                  </TooltipContent>
                )}
              </Tooltip>
            </div>
          </TooltipProvider>
        </div>
      </div>

      <Separator />

      {/* Processing Status */}
      {processingCount > 0 && (
        <>
          <div className="px-2 py-3">
            <TooltipProvider delayDuration={0}>
              <Tooltip>
                <TooltipTrigger asChild>
                  <div
                    className={cn(
                      "flex items-center gap-2 px-2 py-1 rounded-md bg-muted/50 text-muted-foreground",
                      isCollapsed && "justify-center"
                    )}
                  >
                    <Loader2 className="h-4 w-4 animate-spin" />
                    {!isCollapsed && (
                      <span className="text-sm font-medium">
                        Processing - {processingCount}
                      </span>
                    )}
                    {isCollapsed && (
                      <span className="text-xs font-medium">{processingCount}</span>
                    )}
                  </div>
                </TooltipTrigger>
                {isCollapsed && (
                  <TooltipContent side="right">
                    <p>Processing {processingCount} {processingCount === 1 ? 'image' : 'images'}</p>
                  </TooltipContent>
                )}
              </Tooltip>
            </TooltipProvider>
          </div>
          <Separator />
        </>
      )}

      {/* Collapse Toggle */}
      <div className="p-2">
        <Button
          variant="ghost"
          size="icon"
          className="w-full"
          onClick={() => setIsCollapsed(!isCollapsed)}
        >
          {isCollapsed ? (
            <ChevronRight className="h-4 w-4" />
          ) : (
            <ChevronLeft className="h-4 w-4" />
          )}
        </Button>
      </div>
    </aside>
  );
}
