import MarkdownIt from 'markdown-it';

const markdown = new MarkdownIt({ html: false });
const renderLink = markdown.renderer.rules.link_open ??
  ((tokens, index, options, env, renderer) => renderer.renderToken(tokens, index, options));
markdown.renderer.rules.link_open = (tokens, index, options, env, renderer) => {
  const token = tokens[index];
  if (/^https?:\/\//i.test(token.attrGet('href'))) {
    token.attrSet('target', '_blank');
    token.attrSet('rel', 'noopener noreferrer');
  }
  return renderLink(tokens, index, options, env, renderer);
};

function readNotes(source, env) {
  const tokens = markdown.parse(source, env);
  if (tokens[0]?.tag !== 'h1' || !tokens[1].content) {
    throw new Error('笔记需以一级标题开头');
  }

  const entries = new Map();
  let body;
  for (let index = 3; index < tokens.length; index += 1) {
    const token = tokens[index];
    if (token.type === 'heading_open' && token.tag === 'h2' && token.level === 0) {
      const date = /^\*\*时间\*\*\s*:\s*(\d{4}-\d{2}-\d{2})$/.exec(tokens[index + 1].content)?.[1];
      if (!date) throw new Error(`小记日期格式不正确：${tokens[index + 1].content}`);
      if (entries.has(date)) throw new Error(`小记日期重复：${date}`);
      body = [];
      entries.set(date, body);
      index += 2;
      continue;
    }
    if (!body) throw new Error('小记正文需位于日期标题下');
    body.push(token);
  }
  if (!entries.size) throw new Error('笔记至少需要一篇小记');
  return { title: markdown.utils.escapeHtml(tokens[1].content), entries };
}

function firstSummaryLine(tokens) {
  for (const { type, children } of tokens) {
    if (type !== 'inline') continue;
    const lines = children.map(token => {
      if (token.type === 'text' || token.type === 'code_inline') return token.content;
      return token.type.endsWith('break') ? '\n' : '';
    }).join('').split('\n');
    const line = lines.map(text => text.trim()).find(text => text && !/^小记\s*[:：]?$/.test(text));
    if (line) return markdown.utils.escapeHtml(line);
  }
  return '';
}

export function renderNotes(source) {
  const env = {};
  const { title, entries } = readNotes(source, env);
  const cards = [];
  const index = [];
  for (const [date, tokens] of entries) {
    const body = markdown.renderer.render(tokens, markdown.options, env);
    cards.push(`    <article id="note-${date}" aria-labelledby="date-${date}">
      <div class="note-preview" id="body-${date}">
        <div class="note-content">
          <h2 id="date-${date}"><time datetime="${date}">${date}</time></h2>
          <div class="note-body">${body}</div>
        </div>
      </div>
      <button class="note-toggle" type="button" aria-controls="body-${date}" aria-expanded="false" aria-label="展开小记：${date}" hidden></button>
    </article>`);
    const summary = firstSummaryLine(tokens);
    const description = summary ? ` aria-description="${summary}"` : '';
    index.push(`      <li><a href="#note-${date}" aria-label="${date}"${description}></a></li>`);
  }
  return `<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#0e0e11">
  <title>${title} · EOS.</title>
  <link rel="stylesheet" href="notes.css">
  <script type="module" src="notes.js"></script>
</head>
<body>
  <div class="notes">
    <header class="notes-title"><h1>${title}</h1></header>
    <nav class="note-scale" aria-label="按日期浏览" style="--tick-count: ${entries.size}">
      <ol>
${index.join('\n')}
      </ol>
      <div class="scale-tooltip" aria-hidden="true" hidden>
        <div class="scale-date"></div>
        <div class="scale-summary" hidden></div>
      </div>
    </nav>
    <main>
${cards.join('\n')}
    </main>
  </div>
</body>
</html>
`;
}
