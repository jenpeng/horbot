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
});
