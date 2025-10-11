"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { MarkdownEditor, MarkdownDisplay } from "@/components/ui/markdown-editor";
import { MarkdownRenderer } from "@/components/ui/markdown-renderer";

/**
 * ET-12: Markdown Usage Examples
 * 
 * This file demonstrates how to use the markdown components in your application.
 * The styling is inspired by Vercel, OpenAI, and Claude best practices.
 */

// Example 1: Simple markdown display
export function SimpleMarkdownExample() {
  const content = `# Hello World

This is a **simple** markdown example with *italic* text and \`inline code\`.

## Features
- Beautiful typography
- Responsive design
- Dark mode support`;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Simple Markdown Display</CardTitle>
      </CardHeader>
      <CardContent>
        <MarkdownRenderer content={content} />
      </CardContent>
    </Card>
  );
}

// Example 2: Interactive markdown editor
export function InteractiveMarkdownExample() {
  const [content, setContent] = useState(`# Welcome to Markdown Editor

Start typing your markdown content here...

## Features
- **Bold text**
- *Italic text*
- \`Inline code\`
- [Links](https://example.com)

### Code Block
\`\`\`typescript
const example = "Hello World";
console.log(example);
\`\`\``);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Interactive Markdown Editor</CardTitle>
      </CardHeader>
      <CardContent>
        <MarkdownEditor
          value={content}
          onChange={setContent}
          placeholder="Start writing your markdown..."
          showPreview={true}
          showToolbar={true}
          maxLength={2000}
        />
      </CardContent>
    </Card>
  );
}

// Example 3: Read-only markdown display
export function ReadOnlyMarkdownExample() {
  const content = `# Documentation

This is a read-only markdown display component.

## Usage

\`\`\`tsx
import { MarkdownDisplay } from "@/components/ui/markdown-editor";

<MarkdownDisplay content={markdownContent} />
\`\`\`

## Styling

The markdown content is automatically styled with:
- Clean typography
- Responsive design
- Dark mode support
- Code syntax highlighting`;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Read-Only Markdown Display</CardTitle>
      </CardHeader>
      <CardContent>
        <MarkdownDisplay content={content} />
      </CardContent>
    </Card>
  );
}

// Example 4: Custom styled markdown
export function CustomStyledMarkdownExample() {
  const content = `# Custom Styled Markdown

This markdown content has custom styling applied.

> This is a blockquote with custom styling.

| Feature | Status |
|---------|--------|
| Typography | ✅ |
| Responsive | ✅ |
| Dark Mode | ✅ |`;

  return (
    <div className="markdown-content bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-blue-950/20 dark:to-indigo-950/20 p-6 rounded-lg border border-blue-200 dark:border-blue-800">
      <MarkdownRenderer content={content} />
    </div>
  );
}
