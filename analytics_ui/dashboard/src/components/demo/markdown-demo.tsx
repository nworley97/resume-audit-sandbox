"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { MarkdownEditor, MarkdownDisplay, MarkdownEditorSplit } from "@/components/ui/markdown-editor";
import { MarkdownRenderer } from "@/components/ui/markdown-renderer";

const sampleMarkdown = `# Welcome to Markdown Styling

This is a **comprehensive markdown styling system** inspired by the best practices from *Vercel*, *OpenAI*, and *Claude*.

## Features

### Typography
- Clean heading hierarchy
- Beautiful paragraph spacing
- Responsive design

### Code Examples

Here's some inline \`code\` and a code block:

\`\`\`typescript
interface MarkdownProps {
  content: string;
  className?: string;
}

export function MarkdownRenderer({ content, className }: MarkdownProps) {
  return (
    <div className={cn("markdown-content", className)}>
      <div dangerouslySetInnerHTML={{ __html: content }} />
    </div>
  );
}
\`\`\`

### Lists

#### Unordered List
- First item
- Second item
  - Nested item
  - Another nested item
- Third item

#### Ordered List
1. First step
2. Second step
3. Third step

### Links and References

Check out [Vercel](https://vercel.com) for amazing deployment experiences, or explore [OpenAI](https://openai.com) for AI capabilities.

### Blockquotes

> This is a blockquote inspired by Claude's design. It provides a clean way to highlight important information or quotes.

### Tables

| Feature | Vercel | OpenAI | Claude |
|---------|--------|--------|--------|
| Design System | ✅ | ✅ | ✅ |
| Typography | ✅ | ✅ | ✅ |
| Dark Mode | ✅ | ✅ | ✅ |
| Responsive | ✅ | ✅ | ✅ |

### Task Lists

- [x] Implement markdown styling
- [x] Add responsive design
- [x] Support dark mode
- [ ] Add syntax highlighting
- [ ] Implement search functionality

### Horizontal Rules

---

### Images

![Sample Image](https://via.placeholder.com/400x200/0ea5e9/ffffff?text=Beautiful+Markdown)

*Caption: This is how images look in our markdown system*

### Keyboard Shortcuts

Press \`Ctrl+B\` for **bold**, \`Ctrl+I\` for *italic*, and \`Ctrl+K\` for [links](https://example.com).

### Details and Summary

<details>
<summary>Click to expand</summary>

This is collapsible content that can be used to hide additional information while keeping the main content clean and readable.

</details>

---

## Conclusion

This markdown styling system provides a beautiful, consistent, and professional appearance that matches the quality of top-tier startups like Vercel, OpenAI, and Claude.`;

export function MarkdownDemo() {
  const [editorValue, setEditorValue] = useState(sampleMarkdown);
  const [splitValue, setSplitValue] = useState(sampleMarkdown);

  return (
    <div className="space-y-8 p-6">
      <div className="space-y-2">
        <h1 className="text-3xl font-bold text-foreground">Markdown Styling Demo</h1>
        <p className="text-muted-foreground">
          Beautiful markdown rendering inspired by Vercel, OpenAI, and Claude
        </p>
      </div>

      <div className="space-y-6">
        <div className="grid gap-6 md:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>Markdown Preview</CardTitle>
            </CardHeader>
            <CardContent>
              <MarkdownRenderer content={sampleMarkdown} />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Markdown Editor</CardTitle>
            </CardHeader>
            <CardContent>
              <MarkdownEditor
                value={editorValue}
                onChange={setEditorValue}
                placeholder="Start writing in markdown..."
                showPreview={true}
                showToolbar={true}
                maxLength={5000}
              />
            </CardContent>
          </Card>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Split View Editor</CardTitle>
          </CardHeader>
          <CardContent>
            <MarkdownEditorSplit
              value={splitValue}
              onChange={setSplitValue}
            />
          </CardContent>
        </Card>

        <div className="grid gap-6 md:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>Markdown Display</CardTitle>
            </CardHeader>
            <CardContent>
              <MarkdownDisplay content="# Simple Display\nThis is a **simple** markdown display component." />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Features</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex flex-wrap gap-2">
                <Badge variant="outline">Typography</Badge>
                <Badge variant="outline">Code Highlighting</Badge>
                <Badge variant="outline">Tables</Badge>
                <Badge variant="outline">Lists</Badge>
                <Badge variant="outline">Links</Badge>
                <Badge variant="outline">Images</Badge>
                <Badge variant="outline">Responsive</Badge>
                <Badge variant="outline">Dark Mode</Badge>
              </div>
              
              <div className="space-y-2">
                <h4 className="font-medium">Keyboard Shortcuts</h4>
                <div className="text-sm text-muted-foreground space-y-1">
                  <div>• <kbd>Ctrl+B</kbd> Bold</div>
                  <div>• <kbd>Ctrl+I</kbd> Italic</div>
                  <div>• <kbd>Ctrl+K</kbd> Link</div>
                  <div>• <kbd>Ctrl+`</kbd> Code</div>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
