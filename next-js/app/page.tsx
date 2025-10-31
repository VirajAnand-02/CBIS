"use client";

import { SearchFilterBar, SearchFilters } from "@/components/search-filter-bar";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useState } from "react";
import { FileImage, FileVideo, FileText, Music, File } from "lucide-react";
import { format } from "date-fns";
import { ThemeToggle } from "@/components/theme-toggle";

// Mock data for demonstration
const mockResults = [
  { id: 1, name: "Summer Vacation 2024.jpg", type: "Image", date: new Date("2024-10-25"), size: "2.4 MB" },
  { id: 2, name: "Product Photo.png", type: "Image", date: new Date("2024-10-24"), size: "3.2 MB" },
  { id: 3, name: "Meeting Notes.docx", type: "Document", date: new Date("2024-10-28"), size: "0.8 MB" },
  { id: 4, name: "Weekend Trip.jpg", type: "Image", date: new Date("2024-10-20"), size: "1.8 MB" },
  { id: 5, name: "Project Presentation.pdf", type: "Document", date: new Date("2024-09-20"), size: "5.1 MB" },
  { id: 6, name: "Podcast Episode 12.mp3", type: "Audio", date: new Date("2024-09-05"), size: "45 MB" },
  { id: 7, name: "Team Photo.jpg", type: "Image", date: new Date("2024-09-15"), size: "2.1 MB" },
  { id: 8, name: "Birthday Party.mp4", type: "Video", date: new Date("2024-08-10"), size: "125 MB" },
  { id: 9, name: "Beach Sunset.jpg", type: "Image", date: new Date("2024-08-22"), size: "3.5 MB" },
  { id: 10, name: "Conference Recording.mp4", type: "Video", date: new Date("2024-08-15"), size: "98 MB" },
  { id: 11, name: "Recipe Book.pdf", type: "Document", date: new Date("2024-07-10"), size: "4.2 MB" },
  { id: 12, name: "Family Portrait.jpg", type: "Image", date: new Date("2024-07-18"), size: "2.9 MB" },
  { id: 13, name: "Jeffry Epstine.jpg", type: "Image", date: new Date("2025-07-18"), size: "2.9 MB" },
];

function getFileIcon(type: string) {
	switch (type) {
		case "Image":
			return <FileImage className="h-5 w-5 text-blue-500" />;
		case "Video":
			return <FileVideo className="h-5 w-5 text-purple-500" />;
		case "Document":
			return <FileText className="h-5 w-5 text-orange-500" />;
		case "Audio":
			return <Music className="h-5 w-5 text-green-500" />;
		default:
			return <File className="h-5 w-5 text-gray-500" />;
	}
}

export default function Home() {
	const [filters, setFilters] = useState<SearchFilters | null>(null);
	const [isLoading, setIsLoading] = useState(false);

	const handleFilterChange = (newFilters: SearchFilters) => {
		setFilters(newFilters);
		setIsLoading(true);

		// Simulate API call
		setTimeout(() => {
			setIsLoading(false);
		}, 800);

		console.log("Filters applied:", newFilters);
	};

	// Filter results based on active filters
	const filteredResults = mockResults
		.filter((item) => {
			if (filters) {
				// Type filter
				if (filters.type !== "All" && item.type !== filters.type) return false;

				// Query filter
				if (filters.query && !item.name.toLowerCase().includes(filters.query.toLowerCase())) {
					return false;
				}

				// Date filter
				if (filters.dateStart) {
					if (filters.dateMode === "before" && item.date > filters.dateStart) return false;
					if (filters.dateMode === "after" && item.date < filters.dateStart) return false;
					if (filters.dateMode === "range") {
						if (item.date < filters.dateStart) return false;
						if (filters.dateEnd && item.date > filters.dateEnd) return false;
					}
				}
			}
			return true;
		})
		.sort((a, b) => b.date.getTime() - a.date.getTime()); // Sort by date descending (newest first)

	// Group results by date
	const groupedResults = filteredResults.reduce(
		(groups, item) => {
			const dateKey = format(item.date, "MMMM yyyy");
			if (!groups[dateKey]) {
				groups[dateKey] = [];
			}
			groups[dateKey].push(item);
			return groups;
		},
		{} as Record<string, typeof mockResults>
	);

	const hasActiveFilters = filters && (filters.query || filters.type !== "All" || filters.dateStart);

	return (
		<div className="min-h-screen bg-linear-to-b from-background to-muted/20">
			{/* Header */}
			<header className="border-b bg-background/95 backdrop-blur supports-backdrop-filter:bg-background/60 sticky top-0 z-50">
				<div className="container mx-auto px-4 py-4">
					<div className="flex items-center gap-4">
						<h1 className="text-2xl font-bold tracking-tight whitespace-nowrap">CBIS</h1>

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
			<main className="container mx-auto px-4 py-8">
				{/* Results Count */}
				<div className="mb-6">
					<p className="text-sm text-muted-foreground">
						{isLoading ? (
							"Loading..."
						) : hasActiveFilters ? (
							<>
								Showing{" "}
								<span className="font-semibold text-foreground">{filteredResults.length}</span> result
								{filteredResults.length !== 1 ? "s" : ""}
								{filters?.query && ` for "${filters.query}"`}
							</>
						) : (
							<>
								Total{" "}
								<span className="font-semibold text-foreground">{filteredResults.length}</span> media item
								{filteredResults.length !== 1 ? "s" : ""}
							</>
						)}
					</p>
				</div>

				{/* Results Grid - Grouped by Date */}
				{isLoading ? (
					<div className="space-y-8">
						<div>
							<Skeleton className="h-6 w-32 mb-4" />
							<div className="grid grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-2">
								{[...Array(6)].map((_, i) => (
									<Skeleton key={i} className="aspect-square rounded-lg" />
								))}
							</div>
						</div>
					</div>
				) : filteredResults.length > 0 ? (
					<div className="space-y-8">
						{Object.entries(groupedResults).map(([dateGroup, items]) => (
							<div key={dateGroup}>
								<h2 className="text-lg font-semibold mb-4 sticky top-[73px] bg-background/80 backdrop-blur-sm py-2 z-10">
									{dateGroup}
								</h2>
								<div className="grid grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-2">
									{items.map((item) => (
										<div
											key={item.id}
											className="group relative aspect-square rounded-lg overflow-hidden bg-muted hover:ring-2 hover:ring-primary transition-all cursor-pointer"
										>
											<div className="absolute inset-0 flex items-center justify-center">
												{getFileIcon(item.type)}
											</div>
											<div className="absolute inset-0 bg-linear-to-t from-black/60 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity">
												<div className="absolute bottom-0 left-0 right-0 p-3">
													<p className="text-white text-sm font-medium truncate">{item.name}</p>
													<div className="flex items-center justify-between text-xs text-white/80 mt-1">
														<span>{format(item.date, "dd MMM yyyy")}</span>
														<span>{item.size}</span>
													</div>
												</div>
											</div>
										</div>
									))}
								</div>
							</div>
						))}
					</div>
				) : (
					<Card>
						<CardContent className="flex flex-col items-center justify-center py-16">
							<File className="h-16 w-16 text-muted-foreground/50 mb-4" />
							<p className="text-lg font-semibold mb-2">No media found</p>
							<p className="text-sm text-muted-foreground">Try adjusting your search filters</p>
						</CardContent>
					</Card>
				)}
			</main>
		</div>
	);
}
