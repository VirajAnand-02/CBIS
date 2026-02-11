# CBIS - Content Browser & Image Search

A modern, feature-rich search interface built with Next.js 15, React, and shadcn/ui components.

## Features

### 🔍 Advanced Search Bar
- Real-time search input with Enter key support
- Clean, modern UI with icon indicators
- Responsive design that works on all screen sizes

### 🎯 Smart Filtering
- **Type Filter**: Quick dropdown to filter by content type (Image, Video, Document, Audio)
- **Date Filter**: Three powerful modes:
  - **Before**: Find content created before a specific date
  - **After**: Find content created after a specific date
  - **Date Range**: Search within a specific date range
- **Calendar Picker**: Intuitive date selection with a visual calendar

### 🏷️ Active Filter Display
- Visual badges showing all active filters
- One-click removal of individual filters
- "Clear all" button to reset search
- Real-time filter count indicator

### 📊 Results Display
- Grid layout with responsive columns (1/2/3 columns based on screen size)
- File type indicators with color-coded icons
- Hover effects and smooth transitions
- Loading skeletons during search
- Empty state with helpful message

### 🎨 Modern UI Components
- Built with shadcn/ui for consistent, accessible components
- Smooth animations and transitions
- Dark mode support (built-in with Tailwind)
- Sticky header that stays visible while scrolling

## Tech Stack

- **Framework**: Next.js 15 (App Router)
- **UI Library**: shadcn/ui
- **Styling**: Tailwind CSS
- **Icons**: Lucide React
- **Date Handling**: date-fns
- **TypeScript**: Full type safety

## Getting Started

```bash
# Install dependencies
npm install

# Run development server
npm run dev

# Open http://localhost:3000
```

## Component Structure

```
components/
├── search-filter-bar.tsx  # Main search and filter component
├── ui/                    # shadcn/ui components
    ├── button.tsx
    ├── input.tsx
    ├── select.tsx
    ├── calendar.tsx
    ├── popover.tsx
    ├── badge.tsx
    └── ... (other UI components)
```

## Usage Example

```tsx
import { SearchFilterBar } from "@/components/search-filter-bar";

function MyPage() {
  const handleFilterChange = (filters) => {
    console.log("Search query:", filters.query);
    console.log("Type:", filters.type);
    console.log("Date mode:", filters.dateMode);
    console.log("Date range:", filters.dateStart, filters.dateEnd);
    
    // Make API call with filters
    // fetchResults(filters);
  };

  return (
    <SearchFilterBar
      onFilterChange={handleFilterChange}
      types={["All", "Image", "Video", "Document", "Audio"]}
      placeholder="Search your content..."
    />
  );
}
```

## Filter Interface

```typescript
interface SearchFilters {
  query: string;           // Search text
  type: string;            // Content type filter
  dateMode: "before" | "after" | "range";
  dateStart?: Date;        // Start date for filtering
  dateEnd?: Date;          // End date (only for range mode)
}
```

## Customization

### Change Content Types
Modify the `types` prop in the SearchFilterBar component:

```tsx
<SearchFilterBar
  types={["All", "Photos", "Videos", "Music", "Files"]}
  // ...
/>
```

### Customize Placeholder
```tsx
<SearchFilterBar
  placeholder="Find your files..."
  // ...
/>
```

### Backend Integration
Replace the mock data in `app/page.tsx` with your API calls:

```tsx
const handleFilterChange = async (filters: SearchFilters) => {
  setIsLoading(true);
  const results = await fetch('/api/search', {
    method: 'POST',
    body: JSON.stringify(filters)
  }).then(r => r.json());
  setResults(results);
  setIsLoading(false);
};
```

## Features Showcase

1. **Responsive Design**: Works seamlessly on mobile, tablet, and desktop
2. **Keyboard Shortcuts**: Press Enter to search
3. **Visual Feedback**: Loading states, hover effects, and smooth animations
4. **Accessibility**: Built with accessibility in mind using shadcn/ui
5. **Type Safety**: Full TypeScript support

## License

MIT
