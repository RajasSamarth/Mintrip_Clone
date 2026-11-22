"use client";

import React, { useMemo } from "react";

interface MarkdownRendererProps {
  content: string;
  className?: string;
}

export function MarkdownRenderer({ content, className = "" }: MarkdownRendererProps) {
  const blocks = useMemo(() => parseMarkdownToBlocks(content), [content]);

  return (
    <div className={`space-y-2.5 text-sm leading-relaxed ${className}`}>
      {blocks.map((block, idx) => {
        switch (block.type) {
          case "header": {
            if (block.level === 1) {
              return (
                <h2 key={idx} className="text-lg font-bold text-ink mt-3 mb-1.5 tracking-tight">
                  <InlineText text={block.text} />
                </h2>
              );
            }
            if (block.level === 2) {
              return (
                <h3 key={idx} className="text-base font-bold text-ink mt-3 mb-1 tracking-tight">
                  <InlineText text={block.text} />
                </h3>
              );
            }
            return (
              <h4 key={idx} className="text-sm font-bold text-ink mt-2.5 mb-1 flex items-center gap-1.5">
                <InlineText text={block.text} />
              </h4>
            );
          }
          case "table": {
            return (
              <div key={idx} className="my-3 overflow-x-auto rounded-2xl border border-line/80 shadow-2xs bg-white">
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="bg-cream/80 border-b border-line/80">
                      {block.headers.map((h, i) => (
                        <th
                          key={i}
                          className="px-3.5 py-2.5 font-bold text-ink/90 text-[11px] uppercase tracking-wider whitespace-nowrap"
                        >
                          <InlineText text={h} />
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line/40">
                    {block.rows.map((row, rIdx) => (
                      <tr
                        key={rIdx}
                        className={`transition-colors hover:bg-cream/40 ${
                          rIdx % 2 === 1 ? "bg-cream/15" : ""
                        }`}
                      >
                        {row.map((cell, cIdx) => (
                          <td
                            key={cIdx}
                            className="px-3.5 py-2 text-ink/85 whitespace-nowrap"
                          >
                            <InlineText text={cell} />
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            );
          }
          case "bullet_list": {
            return (
              <ul key={idx} className="space-y-1.5 my-2 pl-1">
                {block.items.map((item, i) => (
                  <li key={i} className="flex items-start gap-2 text-xs leading-normal text-ink/90">
                    <span className="size-1.5 rounded-full bg-olive mt-1.5 shrink-0" />
                    <span>
                      <InlineText text={item} />
                    </span>
                  </li>
                ))}
              </ul>
            );
          }
          case "numbered_list": {
            return (
              <ol key={idx} className="space-y-1.5 my-2 pl-1">
                {block.items.map((item, i) => (
                  <li key={i} className="flex items-start gap-2 text-xs leading-normal text-ink/90">
                    <span className="font-bold text-olive text-[11px] shrink-0 mt-0.5">
                      {item.number}.
                    </span>
                    <span>
                      <InlineText text={item.text} />
                    </span>
                  </li>
                ))}
              </ol>
            );
          }
          case "blockquote": {
            return (
              <blockquote
                key={idx}
                className="border-l-3 border-olive/80 bg-olive/5 px-3 py-2 rounded-r-lg my-2 text-xs italic text-ink/80"
              >
                <InlineText text={block.text} />
              </blockquote>
            );
          }
          case "paragraph":
          default: {
            if (!block.text.trim()) return null;
            return (
              <p key={idx} className="text-xs sm:text-[13px] text-ink/90 leading-relaxed">
                <InlineText text={block.text} />
              </p>
            );
          }
        }
      })}
    </div>
  );
}

function InlineText({ text }: { text: string }) {
  if (!text) return null;

  // Split tokens by bold (**...**), link ([...](...)), code (`...`), and plain text
  const parts: React.ReactNode[] = [];
  // Regex to match **bold**, [link](url), `code`
  const pattern = /(\*\*[^*]+\*\*|\[[^\]]+\]\([^)]+\)|`[^`]+`)/g;
  const segments = text.split(pattern);

  segments.forEach((seg, idx) => {
    if (!seg) return;

    if (seg.startsWith("**") && seg.endsWith("**") && seg.length > 4) {
      const inner = seg.slice(2, -2);
      parts.push(
        <strong key={idx} className="font-bold text-ink">
          {inner}
        </strong>
      );
    } else if (seg.startsWith("[") && seg.includes("](") && seg.endsWith(")")) {
      const match = seg.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
      if (match) {
        parts.push(
          <a
            key={idx}
            href={match[2]}
            target="_blank"
            rel="noopener noreferrer"
            className="text-olive underline font-semibold hover:text-ink transition-colors"
          >
            {match[1]}
          </a>
        );
      } else {
        parts.push(seg);
      }
    } else if (seg.startsWith("`") && seg.endsWith("`") && seg.length > 2) {
      parts.push(
        <code key={idx} className="bg-cream px-1.5 py-0.5 rounded text-[11px] font-mono text-ink">
          {seg.slice(1, -1)}
        </code>
      );
    } else {
      parts.push(seg);
    }
  });

  return <>{parts}</>;
}

type Block =
  | { type: "header"; level: number; text: string }
  | { type: "table"; headers: string[]; rows: string[][] }
  | { type: "bullet_list"; items: string[] }
  | { type: "numbered_list"; items: Array<{ number: number; text: string }> }
  | { type: "blockquote"; text: string }
  | { type: "paragraph"; text: string };

function parseMarkdownToBlocks(text: string): Block[] {
  if (!text) return [];
  const lines = text.split("\n");
  const blocks: Block[] = [];
  let i = 0;

  while (i < lines.length) {
    const rawLine = lines[i];
    const line = rawLine.trim();

    if (!line) {
      i++;
      continue;
    }

    // 1. Headers: #, ##, ###
    if (line.startsWith("#")) {
      const match = line.match(/^(#{1,6})\s+(.*)$/);
      if (match) {
        blocks.push({
          type: "header",
          level: match[1].length,
          text: match[2].trim(),
        });
        i++;
        continue;
      }
    }

    // 2. Blockquote: >
    if (line.startsWith(">")) {
      blocks.push({
        type: "blockquote",
        text: line.replace(/^>\s*/, ""),
      });
      i++;
      continue;
    }

    // 3. Tables: lines starting and ending with |
    if (line.startsWith("|") && line.endsWith("|")) {
      const tableLines: string[] = [];
      while (i < lines.length && lines[i].trim().startsWith("|") && lines[i].trim().endsWith("|")) {
        tableLines.push(lines[i].trim());
        i++;
      }

      if (tableLines.length >= 2) {
        const parseRow = (rowStr: string) =>
          rowStr
            .slice(1, -1)
            .split("|")
            .map((cell) => cell.trim());

        const headers = parseRow(tableLines[0]);
        // line 1 is separator |---|---|
        const dataRows = tableLines
          .slice(1)
          .filter((l) => !l.replace(/[|\s-:]/g, "").length === false || !/^\|[:\s|-]+\|$/.test(l))
          .map(parseRow);

        blocks.push({
          type: "table",
          headers,
          rows: dataRows,
        });
        continue;
      }
    }

    // 4. Bullet lists: lines starting with "- " or "* "
    if (line.startsWith("- ") || line.startsWith("* ")) {
      const items: string[] = [];
      while (i < lines.length && (lines[i].trim().startsWith("- ") || lines[i].trim().startsWith("* "))) {
        items.push(lines[i].trim().slice(2).trim());
        i++;
      }
      blocks.push({
        type: "bullet_list",
        items,
      });
      continue;
    }

    // 5. Numbered lists: lines starting with "1. ", "2. ", etc.
    const numMatch = line.match(/^(\d+)\.\s+(.*)$/);
    if (numMatch) {
      const items: Array<{ number: number; text: string }> = [];
      while (i < lines.length) {
        const curLine = lines[i].trim();
        const m = curLine.match(/^(\d+)\.\s+(.*)$/);
        if (m) {
          items.push({ number: parseInt(m[1], 10), text: m[2].trim() });
          i++;
        } else {
          break;
        }
      }
      blocks.push({
        type: "numbered_list",
        items,
      });
      continue;
    }

    // 6. Regular paragraph
    blocks.push({
      type: "paragraph",
      text: line,
    });
    i++;
  }

  return blocks;
}
