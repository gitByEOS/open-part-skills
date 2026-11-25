import assert from 'node:assert/strict';
import { test } from 'node:test';
import { renderNotes } from './render.mjs';

test('每个日期生成卡片、刻度和对应的展开控件', () => {
  const dates = ['2000-01-02', '2000-01-01'];
  const source = ['# 测试笔记', ...dates.map(date => `## **时间** : ${date}\n\n示例正文`)].join('\n\n');
  const html = renderNotes(source);
  const cards = [...html.matchAll(/<article id="note-([\d-]+)"/g)].map(match => match[1]);
  const links = [...html.matchAll(/href="#note-([\d-]+)" aria-label="\1"/g)].map(match => match[1]);
  const previews = [...html.matchAll(/class="note-preview" id="body-([\d-]+)"/g)].map(match => match[1]);
  const controls = [...html.matchAll(/aria-controls="body-([\d-]+)"/g)].map(match => match[1]);

  assert.deepEqual(cards, dates);
  assert.deepEqual(links, dates);
  assert.deepEqual(previews, dates);
  assert.deepEqual(controls, dates);
  assert.match(html, /<script type="module" src="notes\.js"><\/script>/);
});

test('刻度预览取首行正文，跳过小记标签并保留行内纯文本', () => {
  const html = renderNotes(`# 修炼笔记

## **时间** : 2026-11-25

**小记**：
- [Hy-MT3](https://example.com) 支持 \`离线\` 与 "本地" & 翻译
- 第二行不进入刻度预览
`);
  assert.match(html, /href="#note-2026-11-25" aria-label="2026-11-25" aria-description="Hy-MT3 支持 离线 与 &quot;本地&quot; &amp; 翻译"/);
});

test('代码块中的日期不分卡，原始 HTML 不执行', () => {
  const html = renderNotes(`# 修炼笔记

## **时间** : 2026-11-25

\`\`\`md
## **时间** : 2026-11-24
\`\`\`

<img src="test.png">
`);
  assert.equal((html.match(/<article id=/g) ?? []).length, 1);
  assert.match(html, /&lt;img src=/);
  assert.doesNotMatch(html, /<img\b/);
});

test('重复日期会中止构建，不生成重复定位点', () => {
  assert.throws(() => renderNotes('# 修炼笔记\n\n## **时间** : 2026-11-25\n一\n\n## **时间** : 2026-11-25\n二'), /日期重复/);
});
