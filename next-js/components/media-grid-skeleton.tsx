import { Skeleton } from "@/components/ui/skeleton";

export function MediaGridSkeleton() {
  return (
    <div className="space-y-8">
      <div>
        <Skeleton className="h-6 w-32 mb-4" />
        <div className="grid grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-2">
          {[...Array(12)].map((_, i) => (
            <Skeleton key={i} className="aspect-square rounded-lg" />
          ))}
        </div>
      </div>
    </div>
  );
}
