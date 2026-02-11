"use client";

import { useState } from "react";
import { Search, Filter, X, Calendar } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Calendar as CalendarComponent } from "@/components/ui/calendar";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { format } from "date-fns";

export type DateFilterMode = "before" | "after" | "range";

export interface SearchFilters {
  query: string;
  type: string;
  dateMode: DateFilterMode;
  dateStart?: Date;
  dateEnd?: Date;
}

interface SearchFilterBarProps {
  onFilterChange?: (filters: SearchFilters) => void;
  types?: string[];
  placeholder?: string;
}

export function SearchFilterBar({
  onFilterChange,
  types = ["All", "Image", "Video", "Document", "Audio"],
  placeholder = "Search content...",
}: SearchFilterBarProps) {
  const [query, setQuery] = useState("");
  const [selectedType, setSelectedType] = useState("All");
  const [dateMode, setDateMode] = useState<DateFilterMode>("after");
  const [dateStart, setDateStart] = useState<Date>();
  const [dateEnd, setDateEnd] = useState<Date>();
  const [isFilterOpen, setIsFilterOpen] = useState(false);

  const handleSearch = () => {
    onFilterChange?.({
      query,
      type: selectedType,
      dateMode,
      dateStart,
      dateEnd,
    });
  };

  const clearFilters = () => {
    setQuery("");
    setSelectedType("All");
    setDateMode("after");
    setDateStart(undefined);
    setDateEnd(undefined);
    onFilterChange?.({
      query: "",
      type: "All",
      dateMode: "after",
      dateStart: undefined,
      dateEnd: undefined,
    });
  };

  const activeFilterCount = [
    selectedType !== "All" ? 1 : 0,
    dateStart ? 1 : 0,
  ].reduce((a, b) => a + b, 0);

  return (
    <div className="w-full space-y-3">
      {/* Main Search Bar */}
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            type="text"
            placeholder={placeholder}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            className="pl-10 pr-4 h-10 text-base"
          />
        </div>

        {/* Type Filter Dropdown */}
        <Select value={selectedType} onValueChange={setSelectedType}>
          <SelectTrigger className="w-[120px] h-10">
            <SelectValue placeholder="Type" />
          </SelectTrigger>
          <SelectContent>
            {types.map((type) => (
              <SelectItem key={type} value={type}>
                {type}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        {/* Advanced Filters Button */}
        <Popover open={isFilterOpen} onOpenChange={setIsFilterOpen}>
          <PopoverTrigger asChild>
            <Button variant="outline" className="h-10 gap-2 relative px-3">
              <Filter className="h-4 w-4" />
              <span className="hidden md:inline">Filters</span>
              {activeFilterCount > 0 && (
                <Badge
                  variant="destructive"
                  className="absolute -top-2 -right-2 h-5 w-5 rounded-full p-0 flex items-center justify-center text-xs"
                >
                  {activeFilterCount}
                </Badge>
              )}
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-80" align="end">
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h4 className="font-semibold text-sm">Date Filter</h4>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setDateStart(undefined);
                    setDateEnd(undefined);
                  }}
                  className="h-8 px-2"
                >
                  Clear
                </Button>
              </div>

              {/* Date Mode Selection */}
              <RadioGroup value={dateMode} onValueChange={(v) => setDateMode(v as DateFilterMode)}>
                <div className="flex items-center space-x-2">
                  <RadioGroupItem value="before" id="before" />
                  <Label htmlFor="before" className="font-normal cursor-pointer">
                    Before
                  </Label>
                </div>
                <div className="flex items-center space-x-2">
                  <RadioGroupItem value="after" id="after" />
                  <Label htmlFor="after" className="font-normal cursor-pointer">
                    After
                  </Label>
                </div>
                <div className="flex items-center space-x-2">
                  <RadioGroupItem value="range" id="range" />
                  <Label htmlFor="range" className="font-normal cursor-pointer">
                    Date Range
                  </Label>
                </div>
              </RadioGroup>

              {/* Date Picker(s) */}
              {dateMode === "range" ? (
                <div className="space-y-3">
                  <div>
                    <Label className="text-xs text-muted-foreground mb-1 block">
                      Start Date
                    </Label>
                    <Popover>
                      <PopoverTrigger asChild>
                        <Button
                          variant="outline"
                          className="w-full justify-start text-left font-normal"
                        >
                          <Calendar className="mr-2 h-4 w-4" />
                          {dateStart ? format(dateStart, "PPP") : "Pick a date"}
                        </Button>
                      </PopoverTrigger>
                      <PopoverContent className="w-auto p-0" align="start">
                        <CalendarComponent
                          mode="single"
                          selected={dateStart}
                          onSelect={setDateStart}
                          initialFocus
                        />
                      </PopoverContent>
                    </Popover>
                  </div>
                  <div>
                    <Label className="text-xs text-muted-foreground mb-1 block">
                      End Date
                    </Label>
                    <Popover>
                      <PopoverTrigger asChild>
                        <Button
                          variant="outline"
                          className="w-full justify-start text-left font-normal"
                        >
                          <Calendar className="mr-2 h-4 w-4" />
                          {dateEnd ? format(dateEnd, "PPP") : "Pick a date"}
                        </Button>
                      </PopoverTrigger>
                      <PopoverContent className="w-auto p-0" align="start">
                        <CalendarComponent
                          mode="single"
                          selected={dateEnd}
                          onSelect={setDateEnd}
                          initialFocus
                        />
                      </PopoverContent>
                    </Popover>
                  </div>
                </div>
              ) : (
                <Popover>
                  <PopoverTrigger asChild>
                    <Button
                      variant="outline"
                      className="w-full justify-start text-left font-normal"
                    >
                      <Calendar className="mr-2 h-4 w-4" />
                      {dateStart ? format(dateStart, "PPP") : "Pick a date"}
                    </Button>
                  </PopoverTrigger>
                  <PopoverContent className="w-auto p-0" align="start">
                    <CalendarComponent
                      mode="single"
                      selected={dateStart}
                      onSelect={setDateStart}
                      initialFocus
                    />
                  </PopoverContent>
                </Popover>
              )}

              <Button onClick={() => setIsFilterOpen(false)} className="w-full">
                Apply Filters
              </Button>
            </div>
          </PopoverContent>
        </Popover>

        {/* Search Button */}
        <Button onClick={handleSearch} className="h-10 px-4 gap-2">
          <Search className="h-4 w-4" />
          <span className="hidden sm:inline">Search</span>
        </Button>
      </div>

      {/* Active Filters Display */}
      {(activeFilterCount > 0 || query) && (
        <div className="flex items-center gap-2 flex-wrap text-sm">
          <span className="text-sm text-muted-foreground">Active filters:</span>
          
          {query && (
            <Badge variant="secondary" className="gap-1">
              Query: {query}
              <X
                className="h-3 w-3 cursor-pointer"
                onClick={() => setQuery("")}
              />
            </Badge>
          )}
          
          {selectedType !== "All" && (
            <Badge variant="secondary" className="gap-1">
              Type: {selectedType}
              <X
                className="h-3 w-3 cursor-pointer"
                onClick={() => setSelectedType("All")}
              />
            </Badge>
          )}
          
          {dateStart && (
            <Badge variant="secondary" className="gap-1">
              {dateMode === "before" && "Before: "}
              {dateMode === "after" && "After: "}
              {dateMode === "range" && "From: "}
              {format(dateStart, "PP")}
              {dateMode === "range" && dateEnd && ` - ${format(dateEnd, "PP")}`}
              <X
                className="h-3 w-3 cursor-pointer"
                onClick={() => {
                  setDateStart(undefined);
                  setDateEnd(undefined);
                }}
              />
            </Badge>
          )}
          
          <Button
            variant="ghost"
            size="sm"
            onClick={clearFilters}
            className="h-7 text-xs"
          >
            Clear all
          </Button>
        </div>
      )}
    </div>
  );
}
