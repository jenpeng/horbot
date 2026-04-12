import React, { useState, useEffect, useRef, useCallback, memo, useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import hljs from 'highlight.js/lib/core';
import bash from 'highlight.js/lib/languages/bash';
import javascript from 'highlight.js/lib/languages/javascript';
import json from 'highlight.js/lib/languages/json';
import markdown from 'highlight.js/lib/languages/markdown';
import python from 'highlight.js/lib/languages/python';
import sql from 'highlight.js/lib/languages/sql';
import typescript from 'highlight.js/lib/languages/typescript';
import xml from 'highlight.js/lib/languages/xml';
import yaml from 'highlight.js/lib/languages/yaml';
import 'highlight.js/styles/github.css';

interface MarkdownRendererProps {
  content: string;
  className?: string;
  theme?: 'dark' | 'light';
}

interface CodeBlockProps {
  language: string;
  children: string;
}

const REGISTERED_LANGUAGES = [
  ['bash', bash],
  ['javascript', javascript],
  ['json', json],
  ['markdown', markdown],
  ['python', python],
  ['sql', sql],
  ['typescript', typescript],
  ['xml', xml],
  ['yaml', yaml],
] as const;

REGISTERED_LANGUAGES.forEach(([name, definition]) => {
  if (!hljs.getLanguage(name)) {
    hljs.registerLanguage(name, definition);
  }
});

const LANGUAGE_ALIASES: Record<string, string> = {
  sh: 'bash',
  shell: 'bash',
  zsh: 'bash',
  js: 'javascript',
  jsx: 'javascript',
  ts: 'typescript',
  tsx: 'typescript',
  yml: 'yaml',
  html: 'xml',
  svg: 'xml',
  md: 'markdown',
  text: 'plaintext',
  plain: 'plaintext',
};

const normalizeLanguage = (language: string): string => {
  const normalized = language.trim().toLowerCase();
  if (!normalized) {
    return '';
  }
  return LANGUAGE_ALIASES[normalized] || normalized;
};

const CodeBlock: React.FC<CodeBlockProps> = memo(({ language, children }) => {
  const [copied, setCopied] = useState(false);
  const codeRef = useRef<HTMLElement>(null);
  const normalizedLanguage = normalizeLanguage(language);
  const highlightedLanguage = hljs.getLanguage(normalizedLanguage) ? normalizedLanguage : '';

  useEffect(() => {
    if (codeRef.current) {
      hljs.highlightElement(codeRef.current);
    }
  }, [children, highlightedLanguage]);

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(children);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  }, [children]);

  const displayLanguage = highlightedLanguage || normalizedLanguage || 'plaintext';

  return (
    <div className="group relative my-1.5 overflow-hidden rounded-lg border border-surface-200 bg-surface-50">
      <div className="flex items-center justify-between border-b border-surface-200 bg-surface-100 px-2.5 py-1.5">
        <div className="flex items-center gap-2">
          <span className="text-xs text-surface-500 font-mono uppercase tracking-wide">
            {displayLanguage}
          </span>
        </div>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1.5 rounded bg-surface-200 px-2 py-1 text-[11px] text-surface-600 transition-all duration-200 hover:bg-surface-300 hover:text-surface-900"
          title={copied ? 'Copied' : 'Copy code'}
        >
          {copied ? (
            <>
              <svg className="w-3.5 h-3.5 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
              <span className="text-green-600">Copied</span>
            </>
          ) : (
            <>
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
              </svg>
              <span>Copy</span>
            </>
          )}
        </button>
      </div>
      <pre className="!m-0 overflow-x-auto bg-surface-50 !p-2.5">
        <code
          ref={codeRef}
          className={`${highlightedLanguage ? `language-${highlightedLanguage}` : ''} !bg-transparent !p-0 font-mono text-[12px] leading-[1.45] text-surface-900`}
        >
          {children}
        </code>
      </pre>
    </div>
  );
});

CodeBlock.displayName = 'CodeBlock';

const MarkdownRenderer: React.FC<MarkdownRendererProps> = memo(({ content, className = '', theme = 'dark' }) => {
  const remarkPlugins = useMemo(() => [remarkGfm], []);
  const normalizedContent = useMemo(
    () => content
      .replace(/[ \t]+\n/g, '\n')
      .replace(/\n{3,}/g, '\n\n')
      .trim(),
    [content],
  );

  const isDark = theme === 'dark';

  const styles = {
    h1: isDark ? 'text-lg font-bold text-surface-100 mb-1.5 mt-3 pb-1 border-b border-surface-700' : 'text-lg font-bold text-surface-900 mb-1.5 mt-3 pb-1 border-b border-surface-200',
    h2: isDark ? 'text-base font-semibold text-surface-100 mb-1.5 mt-2.5' : 'text-base font-semibold text-surface-800 mb-1.5 mt-2.5',
    h3: isDark ? 'text-sm font-semibold text-surface-100 mb-1 mt-2' : 'text-sm font-semibold text-surface-800 mb-1 mt-2',
    h4: isDark ? 'text-sm font-semibold text-surface-200 mb-1 mt-1.5' : 'text-sm font-semibold text-surface-700 mb-1 mt-1.5',
    p: isDark ? 'text-surface-300 leading-[1.55] mb-1.5 break-words' : 'text-surface-700 leading-[1.55] mb-1.5 break-words',
    a: isDark ? 'text-primary-400 hover:text-primary-300 hover:underline transition-colors' : 'text-primary-600 hover:text-primary-700 hover:underline transition-colors',
    strong: isDark ? 'text-surface-100 font-semibold' : 'text-surface-900 font-semibold',
    em: isDark ? 'text-surface-300 italic' : 'text-surface-600 italic',
    ul: isDark ? 'text-surface-300 my-1.5 ml-4 list-disc list-outside space-y-0.5' : 'text-surface-700 my-1.5 ml-4 list-disc list-outside space-y-0.5',
    ol: isDark ? 'text-surface-300 my-1.5 ml-4 list-decimal list-outside space-y-0.5' : 'text-surface-700 my-1.5 ml-4 list-decimal list-outside space-y-0.5',
    li: 'my-0.5 pl-0.5',
    blockquote: isDark ? 'border-l-4 border-primary-500 bg-surface-800/50 py-1.5 px-3 my-1.5 rounded-r text-surface-300' : 'border-l-4 border-primary-500 bg-surface-100 py-1.5 px-3 my-1.5 rounded-r text-surface-600',
    hr: isDark ? 'border-surface-700 my-3' : 'border-surface-200 my-3',
    inlineCode: isDark ? 'bg-surface-800 text-primary-300 px-1.5 py-0.5 rounded text-[12px] font-mono border border-surface-700' : 'bg-surface-100 text-primary-700 px-1.5 py-0.5 rounded text-[12px] font-mono border border-surface-200',
  };

  return (
    <div className={`markdown-content max-w-none break-words text-[13px] ${className}`}>
      <ReactMarkdown
        remarkPlugins={remarkPlugins}
        components={{
          h1: ({ children }) => (
            <h1 className={styles.h1}>
              {children}
            </h1>
          ),
          h2: ({ children }) => (
            <h2 className={styles.h2}>
              {children}
            </h2>
          ),
          h3: ({ children }) => (
            <h3 className={styles.h3}>
              {children}
            </h3>
          ),
          h4: ({ children }) => (
            <h4 className={styles.h4}>
              {children}
            </h4>
          ),
          p: ({ children }) => (
            <p className={styles.p}>
              {children}
            </p>
          ),
          a: ({ children, href }) => (
            <a 
              href={href}
              className={styles.a}
              target="_blank"
              rel="noopener noreferrer"
            >
              {children}
            </a>
          ),
          strong: ({ children }) => (
            <strong className={styles.strong}>
              {children}
            </strong>
          ),
          em: ({ children }) => (
            <em className={styles.em}>
              {children}
            </em>
          ),
          ul: ({ children }) => (
            <ul className={styles.ul}>
              {children}
            </ul>
          ),
          ol: ({ children }) => (
            <ol className={styles.ol}>
              {children}
            </ol>
          ),
          li: ({ children }) => (
            <li className={styles.li}>
              {children}
            </li>
          ),
          blockquote: ({ children }) => (
            <blockquote className={styles.blockquote}>
              {children}
            </blockquote>
          ),
          hr: () => (
            <hr className={styles.hr} />
          ),
          img: ({ src, alt }) => (
            <img 
              src={src} 
              alt={alt} 
              className="my-2 max-w-full rounded-lg"
            />
          ),
          code({ className: codeClassName, children, ...props }) {
            const match = /language-(\w+)/.exec(codeClassName || '');
            const language = match ? match[1] : '';
            const codeString = String(children).replace(/\n$/, '');
            
            const isInline = !match && !String(children).includes('\n');
            
            if (isInline) {
              return (
                <code
                  className={styles.inlineCode}
                  {...props}
                >
                  {children}
                </code>
              );
            }
            
            return (
              <CodeBlock language={language}>
                {codeString}
              </CodeBlock>
            );
          },
          pre({ children }) {
            return <>{children}</>;
          },
          table({ children }) {
            return (
              <div className="overflow-x-auto my-2">
                <table className="w-full table-fixed overflow-hidden rounded-lg border border-surface-400 border-separate border-spacing-0 bg-surface-50">
                  {children}
                </table>
              </div>
            );
          },
          thead({ children }) {
            return (
              <thead className="bg-surface-100">
                {children}
              </thead>
            );
          },
          tbody({ children }) {
            return (
              <tbody className="bg-surface-50">
                {children}
              </tbody>
            );
          },
          tr({ children }) {
            return (
              <tr className="border-b border-surface-300 last:border-b-0 hover:bg-surface-100 transition-colors">
                {children}
              </tr>
            );
          },
          th({ children }) {
            return (
              <th className="min-w-[100px] border-r border-b border-surface-400 bg-surface-100 px-3 py-2 text-left font-semibold text-surface-900 last:border-r-0">
                {children}
              </th>
            );
          },
          td({ children }) {
            return (
              <td className="min-w-[100px] border-r border-b border-surface-300 px-3 py-2 align-top text-surface-800 last:border-r-0">
                {children}
              </td>
            );
          },
        }}
      >
        {normalizedContent}
      </ReactMarkdown>
    </div>
  );
});

MarkdownRenderer.displayName = 'MarkdownRenderer';

export default MarkdownRenderer;
