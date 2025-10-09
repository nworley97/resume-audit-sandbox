"use client";

import { useState, useRef, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { 
  Bold, 
  Italic, 
  List, 
  ListOrdered, 
  Link, 
  Code, 
  Quote, 
  Heading1, 
  Heading2, 
  Heading3,
  Eye,
  Edit3,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { MarkdownRenderer, MarkdownEditorContainer } from "./markdown-renderer";

interface MarkdownEditorProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  className?: string;
  showPreview?: boolean;
  showToolbar?: boolean;
  maxLength?: number;
  disabled?: boolean;
}

/**
 * ET-12: Markdown Editor Component
 * A rich text editor with markdown support, inspired by Vercel, OpenAI, and Claude
 * 
 * Features:
 * - Live preview toggle
 * - Formatting toolbar
 * - Keyboard shortcuts
 * - Responsive design
 * - Character count
 * - Beautiful markdown rendering
 */
export function MarkdownEditor({
  value,
  onChange,
  placeholder = "Start writing...",
  className,
  showPreview = true,
  showToolbar = true,
  maxLength,
  disabled = false,
}: MarkdownEditorProps) {
  const [isPreview, setIsPreview] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Formatting functions
  const insertText = useCallback((before: string, after: string = "", placeholder: string = "") => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const selectedText = value.substring(start, end);
    const textToInsert = selectedText || placeholder;
    
    const newText = value.substring(0, start) + before + textToInsert + after + value.substring(end);
    onChange(newText);
    
    // Focus and set cursor position
    setTimeout(() => {
      textarea.focus();
      const newCursorPos = start + before.length + textToInsert.length;
      textarea.setSelectionRange(newCursorPos, newCursorPos);
    }, 0);
  }, [value, onChange]);

  // Toolbar actions
  const formatBold = useCallback(() => insertText("**", "**", "bold text"), [insertText]);
  const formatItalic = useCallback(() => insertText("*", "*", "italic text"), [insertText]);
  const formatCode = useCallback(() => insertText("`", "`", "code"), [insertText]);
  const formatLink = useCallback(() => insertText("[", "](url)", "link text"), [insertText]);
  const formatQuote = useCallback(() => insertText("> ", "", "quote"), [insertText]);
  const formatHeading1 = useCallback(() => insertText("# ", "", "Heading 1"), [insertText]);
  const formatHeading2 = useCallback(() => insertText("## ", "", "Heading 2"), [insertText]);
  const formatHeading3 = useCallback(() => insertText("### ", "", "Heading 3"), [insertText]);
  const formatList = useCallback(() => insertText("- ", "", "list item"), [insertText]);
  const formatOrderedList = useCallback(() => insertText("1. ", "", "list item"), [insertText]);

  // Keyboard shortcuts
  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.ctrlKey || e.metaKey) {
      switch (e.key) {
        case 'b':
          e.preventDefault();
          formatBold();
          break;
        case 'i':
          e.preventDefault();
          formatItalic();
          break;
        case 'k':
          e.preventDefault();
          formatLink();
          break;
        case '`':
          e.preventDefault();
          formatCode();
          break;
        case 'Enter':
          e.preventDefault();
          setIsPreview(!isPreview);
          break;
      }
    }
  }, [formatBold, formatItalic, formatLink, formatCode, isPreview]);

  const toolbarButtons = [
    { icon: Bold, action: formatBold, shortcut: "Ctrl+B", label: "Bold" },
    { icon: Italic, action: formatItalic, shortcut: "Ctrl+I", label: "Italic" },
    { icon: Code, action: formatCode, shortcut: "Ctrl+`", label: "Code" },
    { icon: Link, action: formatLink, shortcut: "Ctrl+K", label: "Link" },
    { icon: Quote, action: formatQuote, shortcut: "", label: "Quote" },
    { icon: Heading1, action: formatHeading1, shortcut: "", label: "H1" },
    { icon: Heading2, action: formatHeading2, shortcut: "", label: "H2" },
    { icon: Heading3, action: formatHeading3, shortcut: "", label: "H3" },
    { icon: List, action: formatList, shortcut: "", label: "List" },
    { icon: ListOrdered, action: formatOrderedList, shortcut: "", label: "Ordered List" },
  ];

  return (
    <div className={cn("markdown-editor", className)}>
      {showToolbar && (
        <div className="flex items-center justify-between p-4 border-b border-border/60 bg-muted/20">
          <div className="flex items-center gap-1">
            {toolbarButtons.map((button, index) => (
              <Button
                key={index}
                variant="ghost"
                size="sm"
                onClick={button.action}
                disabled={disabled}
                className="h-8 w-8 p-0 hover:bg-muted/50"
                title={`${button.label} ${button.shortcut ? `(${button.shortcut})` : ''}`}
              >
                <button.icon className="size-4" />
              </Button>
            ))}
          </div>
          
          <div className="flex items-center gap-2">
            {maxLength && (
              <Badge variant="outline" className="text-xs">
                {value.length}/{maxLength}
              </Badge>
            )}
            {showPreview && (
              <div className="flex items-center gap-1">
                <Button
                  variant={!isPreview ? "default" : "ghost"}
                  size="sm"
                  onClick={() => setIsPreview(false)}
                  className="h-8 gap-2"
                >
                  <Edit3 className="size-4" />
                  Edit
                </Button>
                <Button
                  variant={isPreview ? "default" : "ghost"}
                  size="sm"
                  onClick={() => setIsPreview(true)}
                  className="h-8 gap-2"
                >
                  <Eye className="size-4" />
                  Preview
                </Button>
              </div>
            )}
          </div>
        </div>
      )}

      <div className="relative">
        {!isPreview ? (
          <textarea
            ref={textareaRef}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            disabled={disabled}
            maxLength={maxLength}
            className={cn(
              "w-full min-h-[300px] p-4 border-0 resize-none",
              "focus:outline-none focus:ring-0",
              "font-mono text-sm leading-relaxed",
              "bg-background text-foreground",
              "placeholder:text-muted-foreground",
              disabled && "opacity-50 cursor-not-allowed"
            )}
            style={{ fontFamily: 'var(--font-mono), "SF Mono", "Monaco", "Inconsolata", "Roboto Mono", "Source Code Pro", monospace' }}
          />
        ) : (
          <div className="p-4 min-h-[300px]">
            <MarkdownRenderer content={value} />
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * ET-12: Simple Markdown Display Component
 * For displaying read-only markdown content
 */
export function MarkdownDisplay({ 
  content, 
  className 
}: { 
  content: string; 
  className?: string; 
}) {
  return (
    <div className={cn("markdown-content", className)}>
      <div dangerouslySetInnerHTML={{ __html: content }} />
    </div>
  );
}

/**
 * ET-12: Markdown Editor with Split View
 * Shows editor and preview side by side
 */
export function MarkdownEditorSplit({ 
  value, 
  onChange, 
  className 
}: { 
  value: string; 
  onChange: (value: string) => void; 
  className?: string; 
}) {
  return (
    <MarkdownEditorContainer className={className}>
      <div className="space-y-4">
        <div className="flex items-center gap-2">
          <Edit3 className="size-4 text-muted-foreground" />
          <h3 className="font-medium">Editor</h3>
        </div>
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="Start writing in markdown..."
          className={cn(
            "w-full h-full min-h-[400px] p-4 border border-border/60 rounded-lg",
            "focus:outline-none focus:ring-2 focus:ring-brand/20 focus:border-brand/40",
            "font-mono text-sm leading-relaxed resize-none",
            "bg-background text-foreground",
            "placeholder:text-muted-foreground"
          )}
        />
      </div>
      
      <div className="space-y-4">
        <div className="flex items-center gap-2">
          <Eye className="size-4 text-muted-foreground" />
          <h3 className="font-medium">Preview</h3>
        </div>
        <div className="h-full min-h-[400px] p-4 border border-border/60 rounded-lg bg-card/50 overflow-auto">
          <MarkdownRenderer content={value} />
        </div>
      </div>
    </MarkdownEditorContainer>
  );
}
