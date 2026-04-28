import { describe, expect, it } from 'vitest';
import { parseRenderableArtifacts } from './renderableArtifacts';

describe('parseRenderableArtifacts', () => {
  it('extracts horbot-renderable fenced blocks and hides raw json from display content', () => {
    const parsed = parseRenderableArtifacts(`摘要说明

\`\`\`horbot-renderable
{"title":"销售看板","template":"dashboard","items":[{"label":"收入","value":"128万"}]}
\`\`\`
`);

    expect(parsed.content).toBe('摘要说明');
    expect(parsed.artifacts).toHaveLength(1);
    expect(parsed.artifacts[0].title).toBe('销售看板');
  });

  it('extracts renderable metadata without changing visible content', () => {
    const parsed = parseRenderableArtifacts('请点击渲染查看。', {
      renderable: {
        title: '地图故事',
        template: 'map-story',
        points: [{ label: '上海', lat: 31, lng: 121 }],
      },
    });

    expect(parsed.content).toBe('请点击渲染查看。');
    expect(parsed.artifacts).toHaveLength(1);
    expect(parsed.artifacts[0].template).toBe('map-story');
  });

  it('keeps invalid renderable blocks visible instead of creating a broken render card', () => {
    const content = `错误示例

\`\`\`horbot-renderable
{"title":"销售看板","template":{"type":"html-dashboard"},"items":[{"label":"收入","value":"128万"}]}
\`\`\`
`;

    const parsed = parseRenderableArtifacts(content);

    expect(parsed.artifacts).toHaveLength(0);
    expect(parsed.content).toContain('```horbot-renderable');
    expect(parsed.content).toContain('"type":"html-dashboard"');
  });

  it('rejects unsupported template strings before hitting the render API', () => {
    const parsed = parseRenderableArtifacts(`摘要说明

\`\`\`horbot-renderable
{"title":"销售看板","template":"raw-html","items":[{"label":"收入","value":"128万"}]}
\`\`\`
`);

    expect(parsed.artifacts).toHaveLength(0);
    expect(parsed.content).toContain('"template":"raw-html"');
  });
});
