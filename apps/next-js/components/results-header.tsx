interface ResultsHeaderProps {
  isLoading: boolean;
  totalCount: number;
  hasActiveFilters: boolean;
  searchQuery?: string;
}

export function ResultsHeader({
  isLoading,
  totalCount,
  hasActiveFilters,
  searchQuery,
}: ResultsHeaderProps) {
  return (
    <div className="mb-6">
      <p className="text-sm text-muted-foreground">
        {isLoading ? (
          "Loading..."
        ) : hasActiveFilters ? (
          <>
            Showing <span className="font-semibold text-foreground">{totalCount}</span> result
            {totalCount !== 1 ? "s" : ""}
            {searchQuery && ` for "${searchQuery}"`}
          </>
        ) : (
          <>
            Total <span className="font-semibold text-foreground">{totalCount}</span> media item
            {totalCount !== 1 ? "s" : ""}
          </>
        )}
      </p>
    </div>
  );
}
