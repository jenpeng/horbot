import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import MarkdownRenderer from './MarkdownRenderer';

describe('MarkdownRenderer', () => {
  it('renders standalone pollinations links as images', () => {
    const { container } = render(
      <MarkdownRenderer content={'1. https://image.pollinations.ai/prompt/pony?seed=1'} />
    );

    const image = container.querySelector('img');
    expect(image).not.toBeNull();
    expect(image).toHaveAttribute('src', 'https://image.pollinations.ai/prompt/pony?seed=1');
  });

  it('keeps regular non-image links as anchors', () => {
    render(
      <MarkdownRenderer content={'https://example.com/docs'} />
    );

    const link = screen.getByRole('link');
    expect(link).toHaveAttribute('href', 'https://example.com/docs');
    expect(screen.queryByRole('img')).not.toBeInTheDocument();
  });

  it('does not preserve parent pre-wrap whitespace inside rendered markdown', () => {
    const { container } = render(
      <div className="whitespace-pre-wrap">
        <MarkdownRenderer content={'第一段\\n\\n## 标题\\n\\n第二段'} />
      </div>
    );

    const markdownRoot = container.querySelector('.markdown-content');
    expect(markdownRoot).toHaveClass('whitespace-normal');
    expect(markdownRoot).toHaveClass('leading-[1.42]');
  });
});
