"use client";

import { SearchFilterBar, SearchFilters } from "@/components/search-filter-bar";
import { Card, CardContent } from "@/components/ui/card";
import { useState, useMemo } from "react";
import { File } from "lucide-react";
import { ThemeToggle } from "@/components/theme-toggle";
import { MediaGrid } from "@/components/media-grid";
import { ResultsHeader } from "@/components/results-header";
import { MediaGridSkeleton } from "@/components/media-grid-skeleton";
import { MediaItemsSkeleton } from "@/components/media-items-skeleton";
import { AppSidebar } from "@/components/app-sidebar";
import { UploadModal } from "@/components/upload-modal";
import { ImageViewModal } from "@/components/image-view-modal";
import { useBlobStorage } from "@/hooks/use-blob-storage";
import { useInfiniteScroll } from "@/hooks/use-infinite-scroll";
import { MediaItem } from "@/components/media-card";

export default function Home() {
	const [filters, setFilters] = useState<SearchFilters | null>(null);
	const [uploadModalOpen, setUploadModalOpen] = useState(false);
	const [uploadMode, setUploadMode] = useState<"file" | "folder">("file");
	const [selectedItem, setSelectedItem] = useState<MediaItem | null>(null);
	const [imageViewOpen, setImageViewOpen] = useState(false);

	// Prepare fetch options from filters
	const fetchOptions = useMemo(() => ({
		pageSize: 20,
		query: filters?.query || undefined,
		type: filters?.type !== "All" ? filters?.type : undefined,
		dateMode: filters?.dateStart ? filters.dateMode : undefined,
		dateStart: filters?.dateStart || undefined,
		dateEnd: filters?.dateEnd || undefined,
	}), [filters]);
	
	const { 
		items: blobItems, 
		isLoading, 
		isLoadingMore,
		pagination,
		loadMore,
		refetch 
	} = useBlobStorage(fetchOptions);

	const handleFilterChange = (newFilters: SearchFilters) => {
		setFilters(newFilters);
		console.log("Filters applied:", newFilters);
	};

	// Set up infinite scroll
	const loadMoreRef = useInfiniteScroll({
		onLoadMore: loadMore,
		hasMore: pagination?.hasMore || false,
		isLoading: isLoadingMore,
		threshold: 0.8,
	});

	const hasActiveFilters = !!(filters && (filters.query || filters.type !== "All" || filters.dateStart));

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
		// Refresh the media list
		refetch();
	};

	const handleImageClick = (item: MediaItem) => {
		setSelectedItem(item);
		setImageViewOpen(true);
	};

	const handleNavigate = (direction: "prev" | "next") => {
		if (!selectedItem) return;
		
		const currentIndex = blobItems.findIndex((item) => item.id === selectedItem.id);
		if (currentIndex === -1) return;

		if (direction === "prev" && currentIndex > 0) {
			setSelectedItem(blobItems[currentIndex - 1]);
		} else if (direction === "next" && currentIndex < blobItems.length - 1) {
			setSelectedItem(blobItems[currentIndex + 1]);
		}
	};

	const handleDelete = (itemId: string) => {
		console.log("Deleted item ID:", itemId);
		// Refresh the media list to remove the deleted item
		refetch();
	};

	return (
		<div className="flex min-h-screen bg-linear-to-b from-background to-muted/20">
			{/* Sidebar */}
			<AppSidebar 
				onUploadImage={handleUploadImage} 
				onUploadFolder={handleUploadFolder}
				currentPage="home"
			/>

			{/* Main Content Area */}
			<div className="flex-1 flex flex-col">
				{/* Header */}
				<header className="border-b bg-background/95 backdrop-blur supports-backdrop-filter:bg-background/60 sticky top-0 z-50">
					<div className="container mx-auto px-4 py-4">
						<div className="flex items-center gap-4">
							<div className="flex-1">
								<SearchFilterBar
									onFilterChange={handleFilterChange}
									types={["All", "Image", "Video", "Document", "Audio"]}
									placeholder="Search your content..."
								/>
							</div>

							<ThemeToggle />
						</div>
					</div>
				</header>

				{/* Main Content */}
				<main className="container mx-auto px-4 py-8 flex-1">
				{/* Results Count */}
				<ResultsHeader
					isLoading={isLoading}
					totalCount={pagination?.total || 0}
					hasActiveFilters={hasActiveFilters}
					searchQuery={filters?.query}
				/>

				{/* Results Grid - Grouped by Date */}
				{isLoading ? (
					<MediaGridSkeleton />
				) : blobItems.length > 0 ? (
					<>
						<MediaGrid items={blobItems} onItemClick={handleImageClick} />
						
						{/* Infinite Scroll Trigger */}
						{pagination?.hasMore && (
							<div ref={loadMoreRef} className="py-8">
								{isLoadingMore && <MediaItemsSkeleton count={6} />}
							</div>
						)}
					</>
				) : (
					<Card>
						<CardContent className="flex flex-col items-center justify-center py-16">
							<File className="h-16 w-16 text-muted-foreground/50 mb-4" />
							<p className="text-lg font-semibold mb-2">
								{pagination?.total === 0 && !hasActiveFilters ? "No media uploaded yet" : "No media found"}
							</p>
							<p className="text-sm text-muted-foreground">
								{pagination?.total === 0 && !hasActiveFilters
									? "Upload files using the sidebar to get started" 
									: "Try adjusting your search filters"}
							</p>
						</CardContent>
					</Card>
				)}
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
				onNavigate={handleNavigate}
				onDelete={handleDelete}
			/>
		</div>
	);
}
