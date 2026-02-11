import { format } from "date-fns";
import { MediaCard, MediaItem } from "./media-card";

interface MediaGridProps {
  items: MediaItem[];
  onItemClick?: (item: MediaItem) => void;
}

export function MediaGrid({ items, onItemClick }: MediaGridProps) {
  // Group items by month
  const groupedItems = items.reduce(
    (groups, item) => {
      const dateKey = format(item.date, "MMMM yyyy");
      if (!groups[dateKey]) {
        groups[dateKey] = [];
      }
      groups[dateKey].push(item);
      return groups;
    },
    {} as Record<string, MediaItem[]>
  );

  return (
    <div className="space-y-8">
      {Object.entries(groupedItems).map(([dateGroup, groupItems]) => (
        <div key={dateGroup}>
          <h2 className="text-lg font-semibold mb-4 sticky top-[73px] bg-background/80 backdrop-blur-sm py-2 z-10">
            {dateGroup}
          </h2>
          <div className="grid grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-2">
            {groupItems.map((item) => (
              <MediaCard
                key={item.id}
                item={item}
                onClick={() => onItemClick?.(item)}
              />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
