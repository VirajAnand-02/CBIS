import { Skeleton } from "@/components/ui/skeleton";

export function MediaItemsSkeleton({ count = 6 }: { count?: number }) {
  return (
    <div className="grid grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-2">
      {[...Array(count)].map((_, i) => (
        <Skeleton key={i} className="aspect-square rounded-lg" />
      ))}
    </div>
  );
}
