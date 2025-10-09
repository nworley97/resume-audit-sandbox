"use client";

import { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface MarkdownRendererProps {
  content: string;
  className?: string;
  children?: ReactNode;
}

/**
 * ET-12: Markdown Renderer Component
 * Renders markdown content with beautiful styling inspired by Vercel, OpenAI, and Claude
 * 
 * Usage:
 * <MarkdownRenderer content="# Hello World\nThis is **bold** text." />
 * 
 * Or with children:
 * <MarkdownRenderer>
 *   <div dangerouslySetInnerHTML={{ __html: processedMarkdown }} />
 * </MarkdownRenderer>
 */
export function MarkdownRenderer({ 
  content, 
  className, 
  children 
}: MarkdownRendererProps) {
  // If children are provided, render them with markdown styling
  if (children) {
    return (
      <div className={cn("markdown-content", className)}>
        {children}
      </div>
    );
  }

  // If content is provided, render it directly
  // Note: In a real implementation, you would use a markdown parser like react-markdown
  // or markdown-it to convert the markdown string to HTML
  return (
    <div 
      className={cn("markdown-content", className)}
      dangerouslySetInnerHTML={{ __html: content }}
    />
  );
}

/**
 * ET-12: Markdown Preview Component
 * For use in markdown editors to show live preview
 */
export function MarkdownPreview({ 
  content, 
  className 
}: { 
  content: string; 
  className?: string; 
}) {
  return (
    <div className={cn(
      "markdown-content border border-border/60 rounded-lg p-6 bg-card/50",
      className
    )}>
      <div dangerouslySetInnerHTML={{ __html: content }} />
    </div>
  );
}

/**
 * ET-12: Markdown Editor Container
 * Wrapper for markdown editor with preview
 */
export function MarkdownEditorContainer({ 
  children, 
  className 
}: { 
  children: ReactNode; 
  className?: string; 
}) {
  return (
    <div className={cn(
      "markdown-editor-container",
      "grid grid-cols-1 lg:grid-cols-2 gap-6",
      "min-h-[400px]",
      className
    )}>
      {children}
    </div>
  );
}

/**
 * ET-12: Markdown Editor Sidebar
 * For editor controls and formatting buttons
 */
export function MarkdownEditorSidebar({ 
  children, 
  className 
}: { 
  children: ReactNode; 
  className?: string; 
}) {
  return (
    <div className={cn(
      "markdown-editor-sidebar",
      "flex flex-col gap-2 p-4 bg-muted/30 rounded-lg",
      "lg:order-first",
      className
    )}>
      {children}
    </div>
  );
}
