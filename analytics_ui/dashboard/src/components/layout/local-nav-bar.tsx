"use client";

import { Button } from "@/components/ui/button";
import { ArrowLeft, RefreshCw, Download, Calendar, Filter } from "lucide-react";
import { cn } from "@/lib/utils";

interface LocalNavBarProps {
  title: string;
  subtitle?: string;
  showBackButton?: boolean;
  onBackClick?: () => void;
  showRefreshButton?: boolean;
  onRefreshClick?: () => void;
  showExportButton?: boolean;
  onExportClick?: () => void;
  showDateRange?: boolean;
  dateRange?: string;
  onDateRangeClick?: () => void;
  showFilters?: boolean;
  onFiltersClick?: () => void;
  className?: string;
}

export function LocalNavBar({
  title,
  subtitle,
  showBackButton = false,
  onBackClick,
  showRefreshButton = false,
  onRefreshClick,
  showExportButton = false,
  onExportClick,
  showDateRange = false,
  dateRange,
  onDateRangeClick,
  showFilters = false,
  onFiltersClick,
  className,
}: LocalNavBarProps) {
  return (
    <div className={cn(
      "sticky top-0 z-40 w-full border-b border-border/60 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60",
      className
    )}>
      <div className="px-6 py-3">
        {/* ET-12: Back button above title */}
        {showBackButton && (
          <div className="mb-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={onBackClick}
              className="h-8 w-8 p-0 hover:bg-[#F2F1EE] cursor-pointer"
            >
              <ArrowLeft className="size-4" />
            </Button>
          </div>
        )}
        
        {/* ET-12: Title and action buttons row */}
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-lg font-semibold text-foreground">{title}</h1>
            {subtitle && (
              <p className="text-sm text-muted-foreground">{subtitle}</p>
            )}
          </div>
          
          <div className="flex items-center gap-2">
            {showDateRange && (
              <Button
                variant="outline"
                size="sm"
                onClick={onDateRangeClick}
                className="h-8 gap-2 hover:bg-[#F2F1EE] cursor-pointer"
              >
                <Calendar className="size-4" />
                {dateRange || "Last 30 days"}
              </Button>
            )}
            
            {showFilters && (
              <Button
                variant="outline"
                size="sm"
                onClick={onFiltersClick}
                className="h-8 gap-2 hover:bg-[#F2F1EE] cursor-pointer"
              >
                <Filter className="size-4" />
                Filters
              </Button>
            )}
            
            {showRefreshButton && (
              <Button
                variant="outline"
                size="sm"
                onClick={onRefreshClick}
                className="h-8 gap-2 hover:bg-[#F2F1EE] cursor-pointer"
              >
                <RefreshCw className="size-4" />
                Refresh
              </Button>
            )}
            
            {showExportButton && (
              <Button
                variant="outline"
                size="sm"
                onClick={onExportClick}
                className="h-8 gap-2 hover:bg-[#F2F1EE] cursor-pointer"
              >
                <Download className="size-4" />
                Export
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
