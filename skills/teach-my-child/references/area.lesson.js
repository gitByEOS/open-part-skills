/* 示例课：平行四边形任意点与梯形两翼。打包用 scripts/build.py */
/* 衔接只用 reveal / conceal / moveTo，必要时一次 nudge */

function park(node, sel, viz){
  node.style.transform = '';
  node.style.transition = '';
  $(sel, viz).append(node);
  conceal(node);
}

function playNudge(node){
  if(!node) return;
  const cls = (node.getAttribute('class') || '').replace(/\bnudge\b/g, '').trim();
  node.setAttribute('class', cls);
  void node.getBoundingClientRect();
  node.setAttribute('class', (cls + ' nudge').trim());
}

function dropNudge(node){
  if(!node) return;
  node.setAttribute('class', (node.getAttribute('class') || '').replace(/\bnudge\b/g, '').trim());
}

function paraScene(viz){
  viz.innerHTML = `
    <div class="scene">
      <svg viewBox="0 0 320 188" aria-hidden="true">
        <polygon points="80,36 270,36 230,160 40,160" fill="#eef2ff" stroke="#334155" stroke-width="2"/>
        <polygon id="tri-blue" class="fade" points="175,36 230,160 40,160" fill="#2563eb" fill-opacity=".42"/>
        <polygon id="tri-ghost" class="fade" points="115,36 230,160 40,160" fill="#2563eb" fill-opacity=".12" stroke="#2563eb" stroke-width="1.4" stroke-dasharray="5 4"/>
        <line id="line-pd" class="fade" x1="175" y1="36" x2="40" y2="160" stroke="#4f46e5" stroke-width="1.8"/>
        <line id="line-pc" class="fade" x1="175" y1="36" x2="230" y2="160" stroke="#4f46e5" stroke-width="1.8"/>
        <line id="h-line" class="fade" x1="175" y1="36" x2="175" y2="160" stroke="#d97706" stroke-width="1.6" stroke-dasharray="4 3"/>
        <text id="h-lab" class="fade" x="186" y="104" font-size="13" font-weight="800" fill="#d97706">h</text>
        <g id="g-p2" class="fade">
          <circle cx="115" cy="36" r="4.5" fill="#94a3b8"/>
          <text x="115" y="24" text-anchor="middle" font-size="11" font-weight="800" fill="#94a3b8">P′</text>
        </g>
        <g id="g-p" class="fade">
          <g id="p-nudge">
            <circle cx="175" cy="36" r="5" fill="#4f46e5"/>
            <text x="175" y="24" text-anchor="middle" font-size="12" font-weight="800" fill="#4f46e5">P</text>
          </g>
        </g>
        <circle cx="80" cy="36" r="3.2" fill="#1e293b"/>
        <circle cx="270" cy="36" r="3.2" fill="#1e293b"/>
        <circle cx="230" cy="160" r="3.2" fill="#1e293b"/>
        <circle cx="40" cy="160" r="3.2" fill="#1e293b"/>
        <text x="72" y="28" text-anchor="middle" font-size="12" font-weight="800" fill="#1e293b">A</text>
        <text x="278" y="28" text-anchor="middle" font-size="12" font-weight="800" fill="#1e293b">B</text>
        <text x="242" y="176" text-anchor="middle" font-size="12" font-weight="800" fill="#1e293b">C</text>
        <text x="28" y="176" text-anchor="middle" font-size="12" font-weight="800" fill="#1e293b">D</text>
        <text id="lab-s" class="fade" x="155" y="88" text-anchor="middle" font-size="13" font-weight="800" fill="#4338ca">20</text>
        <text id="lab-10" class="fade" x="148" y="132" text-anchor="middle" font-size="16" font-weight="800" fill="#1e3a8a">10</text>
      </svg>
      <div class="bins">
        <div class="bin"><div class="bin-h">平行四边形</div><div class="row" id="para"></div></div>
        <div class="bin"><div class="bin-h">蓝三角 PCD</div><div class="row" id="tri"></div></div>
      </div>
    </div>`;
  const chip20 = el('span', 'p n20', '20'); chip20.id = 'c20';
  const chip10 = el('span', 'p n10', '10'); chip10.id = 'c10';
  const reset = ()=>{
    $$('.fade', viz).forEach(conceal);
    dropNudge($('#p-nudge', viz));
    park(chip20, '#para', viz);
    park(chip10, '#para', viz);
  };
  return {reset};
}

function trapScene(viz){
  viz.innerHTML = `
    <div class="scene">
      <svg viewBox="0 0 320 188" aria-hidden="true">
        <polygon points="70,160 100,40 220,40 250,160" fill="#f8fafc" stroke="#334155" stroke-width="2"/>
        <polygon id="fill-abc" class="fade" points="70,160 100,40 220,40" fill="#60a5fa" fill-opacity=".42"/>
        <polygon id="fill-dbc" class="fade" points="250,160 100,40 220,40" fill="#c4b5fd" fill-opacity=".40"/>
        <polygon id="fill-obc" class="fade" points="160,88 100,40 220,40" fill="#f59e0b" fill-opacity=".55"/>
        <polygon id="fill-aob" class="fade" points="70,160 160,88 100,40" fill="#10b981" fill-opacity=".50"/>
        <polygon id="fill-doc" class="fade" points="250,160 160,88 220,40" fill="#10b981" fill-opacity=".50"/>
        <line id="diag-ac" class="fade" x1="70" y1="160" x2="220" y2="40" stroke="#4f46e5" stroke-width="1.7"/>
        <line id="diag-bd" class="fade" x1="100" y1="40" x2="250" y2="160" stroke="#4f46e5" stroke-width="1.7"/>
        <g id="g-o" class="fade">
          <circle cx="160" cy="88" r="4.5" fill="#7c3aed"/>
          <text x="172" y="86" font-size="12" font-weight="800" fill="#7c3aed">O</text>
        </g>
        <g id="g-h" class="fade">
          <line x1="70" y1="160" x2="70" y2="40" stroke="#d97706" stroke-width="1.4" stroke-dasharray="4 3"/>
          <line x1="250" y1="160" x2="250" y2="40" stroke="#d97706" stroke-width="1.4" stroke-dasharray="4 3"/>
          <line x1="58" y1="40" x2="262" y2="40" stroke="#d97706" stroke-width="1.2" stroke-dasharray="3 3"/>
          <text x="56" y="104" font-size="11" font-weight="800" fill="#d97706">h</text>
          <text x="258" y="104" text-anchor="start" font-size="11" font-weight="800" fill="#d97706">h</text>
        </g>
        <g id="g-par" class="fade">
          <path d="M148,34 h24 M148,46 h24" stroke="#059669" stroke-width="2" fill="none"/>
          <path d="M148,154 h24 M148,166 h24" stroke="#059669" stroke-width="2" fill="none"/>
        </g>
        <circle cx="70" cy="160" r="3.2" fill="#1e293b"/>
        <circle cx="100" cy="40" r="3.2" fill="#1e293b"/>
        <circle cx="220" cy="40" r="3.2" fill="#1e293b"/>
        <circle cx="250" cy="160" r="3.2" fill="#1e293b"/>
        <text x="62" y="176" text-anchor="middle" font-size="12" font-weight="800" fill="#1e293b">A</text>
        <text x="100" y="28" text-anchor="middle" font-size="12" font-weight="800" fill="#1e293b">B</text>
        <text x="220" y="28" text-anchor="middle" font-size="12" font-weight="800" fill="#1e293b">C</text>
        <text x="258" y="176" text-anchor="middle" font-size="12" font-weight="800" fill="#1e293b">D</text>
        <text id="lab-abc" class="fade" x="128" y="92" text-anchor="middle" font-size="12" font-weight="800" fill="#1e40af">15</text>
        <text id="lab-obc" class="fade" x="160" y="58" text-anchor="middle" font-size="12" font-weight="800" fill="#92400e">6</text>
        <text id="lab-aob" class="fade" x="104" y="108" text-anchor="middle" font-size="13" font-weight="800" fill="#065f46">9</text>
        <text id="lab-doc" class="fade" x="216" y="108" text-anchor="middle" font-size="13" font-weight="800" fill="#065f46">9</text>
        <text id="lab-dbc" class="fade" x="196" y="92" text-anchor="middle" font-size="12" font-weight="800" fill="#5b21b6">15</text>
      </svg>
      <div class="bins">
        <div class="bin"><div class="bin-h">△ABC</div><div class="row" id="abc"></div></div>
        <div class="bin"><div class="bin-h">公共 △OBC</div><div class="row" id="obc"></div></div>
        <div class="bin"><div class="bin-h">△DBC</div><div class="row" id="dbc"></div></div>
        <div class="bin"><div class="bin-h">左翼 △AOB</div><div class="row" id="wingL"></div></div>
        <div class="bin"><div class="bin-h">右翼 △DOC</div><div class="row" id="wingR"></div></div>
      </div>
    </div>`;
  const chip15 = el('span', 'p n15', '15'); chip15.id = 'c15';
  const chip15b = el('span', 'p n15', '15'); chip15b.id = 'c15b';
  const chip6 = el('span', 'p n6', '6'); chip6.id = 'c6';
  const chip9L = el('span', 'p n9', '9'); chip9L.id = 'c9L';
  const chip9R = el('span', 'p n9', '9'); chip9R.id = 'c9R';
  const reset = ()=>{
    $$('.fade', viz).forEach(conceal);
    park(chip15, '#abc', viz);
    park(chip15b, '#abc', viz);
    park(chip6, '#obc', viz);
    park(chip9L, '#wingL', viz);
    park(chip9R, '#wingR', viz);
  };
  return {reset};
}

const AREA_CSS = `
  .scene{width:100%}
  .scene svg{width:100%;height:auto;display:block}
  .bins{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}
  .bin{flex:1 1 88px;min-width:84px;background:#fff;border:1px dashed #cbd5e1;border-radius:10px;padding:6px 7px}
  .bin-h{font-size:10px;font-weight:800;color:#94a3b8;margin-bottom:4px;letter-spacing:.3px}
  .row{display:flex;flex-wrap:wrap;gap:4px;min-height:26px}
  .p{min-width:28px;height:22px;padding:0 7px;border-radius:6px;font-size:12px;font-weight:800;
     display:flex;align-items:center;justify-content:center;will-change:transform}
  .p.n20{background:#c7d2fe;color:#3730a3}
  .p.n15{background:#bfdbfe;color:#1e40af}
  .p.n10,.p.n9{background:#a7f3d0;color:#065f46}
  .p.n6{background:#fde68a;color:#92400e}
  .p.hide{min-width:0;width:0;height:0;padding:0;overflow:hidden}
  #viz .fade{opacity:0}
  #viz .fade.show{opacity:1}`;

const THUMB_PARA = `<svg viewBox="0 0 100 72">
  <polygon points="18,14 84,14 72,58 6,58" fill="#eef2ff" stroke="#64748b"/>
  <polygon points="48,14 72,58 6,58" fill="#2563eb" fill-opacity=".45"/>
  <circle cx="48" cy="14" r="3" fill="#4f46e5"/>
</svg>`;

const THUMB_TRAP = `<svg viewBox="0 0 100 72">
  <polygon points="14,58 30,14 70,14 86,58" fill="#f8fafc" stroke="#64748b"/>
  <polygon points="14,58 50,32 30,14" fill="#10b981" fill-opacity=".55"/>
  <polygon points="86,58 50,32 70,14" fill="#10b981" fill-opacity=".55"/>
  <polygon points="50,32 30,14 70,14" fill="#f59e0b" fill-opacity=".55"/>
  <line x1="14" y1="58" x2="70" y2="14" stroke="#6366f1" stroke-width="1"/>
  <line x1="30" y1="14" x2="86" y2="58" stroke="#6366f1" stroke-width="1"/>
</svg>`;

const LESSON = {
  title: '同底等高 · 任意点与两翼面积',
  lead: '平行四边形上边任意一点对着下底，面积为什么钉死？梯形左右两翼为什么一样大？同一句话：平行线之间高相等。',
  footnote: '判据：状态 → 一步操作 → 可打印的新面积。纯网页，离线可播。',

  questions: [
    {
      tag:'原题 · 任意点', tagExt:false,
      stem:'平行四边形 ABCD 的面积是 20。P 是上边 AB 上任意一点。连接 P 与下底 CD 的两端，求蓝色阴影三角形 PCD 的面积。',
      conds:['平行四边形 ABCD','面积 20','P 在 AB 上任意','所求：蓝三角 PCD'],
      tip:'P 没有固定位置。真正钉死面积的，是「上边平行下底」。',
      thumb: THUMB_PARA,
      style: AREA_CSS,
      speed:1100,
      build(viz){ return paraScene(viz); },
      steps:[
        {
          change:'底图是平行四边形 ABCD，整块面积 20。上边 AB，下底 CD。',
          diff:[['图形','—','平行四边形 ABCD'],['面积','—','20'],['上边 / 下底','—','AB ∥ CD']],
          why:'后面每一块面积都从这个 20 里拆。先把整块认清。',
          formula:'S_ABCD = 20',
          run(viz){
            reveal($('#lab-s', viz));
            reveal($('#c20', viz));
          }
        },
        {
          change:'P 落在上边 AB 上。连上 P 到下底两端 C、D。',
          diff:[['点 P','没有','AB 上任意一点'],['连线','没有','PC、PD'],['蓝三角','还没涂','即将出现 △PCD']],
          why:'题目要的就是 P、C、D 围成的这块。P 此刻在哪，还不进答案。',
          formula:'连 PC、PD',
          run(viz){
            reveal($('#g-p', viz));
            reveal($('#line-pd', viz));
            reveal($('#line-pc', viz));
          }
        },
        {
          change:'蓝色阴影就是 △PCD。底是下底 CD，顶点是 P。',
          diff:[['阴影','未涂','△PCD'],['底','—','CD'],['顶点','—','P']],
          why:'涂色是把要求和的那块圈出来。底已经和平行四边形共用。',
          formula:'所求 = S_△PCD',
          run(viz){ reveal($('#tri-blue', viz)); }
        },
        {
          change:'AB ∥ CD，P 在 AB 上，所以 P 到 CD 的高就是平行四边形的高 h。',
          diff:[['高 h','未标','平行四边形的高'],['P 的位置','好像影响高','高不变'],['底 CD','公共','公共']],
          why:'平行线之间距离处处相等。P 只要还在上边，高就钉死。',
          formula:'高(P→CD) = h',
          run(viz){
            reveal($('#h-line', viz));
            reveal($('#h-lab', viz));
          }
        },
        {
          change:'同底 CD、同高 h，三角形是平行四边形的一半：20 的一半是 10。',
          diff:[['平行四边形','底×高=20','20'],['蓝三角','½×底×高','10'],['倍数','—','一半']],
          why:'平行四边形面积是底乘高。同底同高的三角形永远是它的一半。',
          formula:'S_△PCD = ½ × 20 = 10',
          run(viz){
            conceal($('#c20', viz));
            const chip = $('#c10', viz);
            reveal(chip);
            moveTo(chip, $('#tri', viz));
            reveal($('#lab-10', viz));
          }
        },
        {
          change:'把 P 轻轻挪一下，高还是 h，蓝三角还是 10。任意一点都不改答案。',
          diff:[['P 的位置','一处','任意'],['高','h','h'],['蓝三角面积','10','10 ✔']],
          why:'题目写「任意一点」，不是漏了位置，是位置根本不进答案。',
          formula:'答案：10（与 P 无关）',
          run(viz){
            const chip = $('#c10', viz);
            reveal(chip);
            moveTo(chip, $('#tri', viz));
            reveal($('#lab-10', viz));
            reveal($('#g-p2', viz));
            reveal($('#tri-ghost', viz));
            playNudge($('#p-nudge', viz));
          }
        }
      ]
    },

    {
      tag:'变式 · 同一套知识点', tagExt:true,
      stem:'梯形 ABCD 中 AD∥BC，两条对角线交于 O。已知 △ABC 的面积是 15，公共 △OBC 的面积是 6，求左右两翼 △AOB 与 △DOC 的面积。',
      conds:['梯形 ABCD','AD ∥ BC','对角线交于 O','△ABC = 15','△OBC = 6'],
      tip:'两翼不要各自乱凑。A 和 D 在同一条平行线上，对着 BC 是同一招。',
      thumb: THUMB_TRAP,
      style: AREA_CSS,
      speed:1100,
      build(viz){ return trapScene(viz); },
      steps:[
        {
          change:'底图换成梯形 ABCD，两底 AD 与 BC 平行。',
          diff:[['图形','—','梯形 ABCD'],['平行','—','AD ∥ BC'],['两底','—','AD 与 BC']],
          why:'平行四边形换成梯形，留下最要紧的一句：两底平行。',
          formula:'AD ∥ BC',
          run(viz){ reveal($('#g-par', viz)); }
        },
        {
          change:'两条对角线 AC、BD 交于 O。后面每一块都围着这个交点。',
          diff:[['对角线','没有','AC、BD'],['交点','没有','O'],['公共块','还没标','即将出现 △OBC']],
          why:'O 是所有小三角形的公共顶点。交点钉住，才能拆块。',
          formula:'AC ∩ BD = O',
          run(viz){
            reveal($('#diag-ac', viz));
            reveal($('#diag-bd', viz));
            reveal($('#g-o', viz));
          }
        },
        {
          change:'已知 △ABC 面积 15，贴着 BC 的公共小块 △OBC 面积 6。',
          diff:[['△ABC','未知','15'],['△OBC','未知','6'],['关系','—','△OBC 在 △ABC 里面']],
          why:'△ABC 的底是 BC、顶点是 A。△OBC 是它内部贴着 BC 的小三角。',
          formula:'S_△ABC = 15，S_△OBC = 6',
          run(viz){
            reveal($('#fill-abc', viz));
            reveal($('#fill-obc', viz));
            reveal($('#lab-abc', viz));
            reveal($('#lab-obc', viz));
            reveal($('#c15', viz));
            reveal($('#c6', viz));
          }
        },
        {
          change:'左翼 △AOB 就是大块减去公共小块：15 − 6 = 9。',
          diff:[['△ABC','15','15'],['减去 △OBC','6','6'],['左翼 △AOB','未知','9']],
          why:'O 在 AC 上，△ABC 正好拆成 △AOB 和 △OBC，没有第三块。',
          formula:'15 − 6 = 9',
          run(viz){
            reveal($('#fill-aob', viz));
            reveal($('#lab-aob', viz));
            reveal($('#c9L', viz));
          }
        },
        {
          change:'A 和 D 都在 BC 的平行线上，对着同一底 BC 的高都是 h。所以 △DBC 也是 15。',
          diff:[['△ABC 的高','A 到 BC','h'],['△DBC 的高','D 到 BC','h'],['△DBC 面积','未知','15']],
          why:'这就是原题那一招：顶点在平行线上，高不变，面积不变。A 换成 D，底还是 BC。',
          formula:'S_△DBC = S_△ABC = 15',
          run(viz){
            reveal($('#fill-dbc', viz));
            reveal($('#g-h', viz));
            reveal($('#lab-dbc', viz));
            const extra = $('#c15b', viz);
            reveal(extra);
            moveTo(extra, $('#dbc', viz));
          }
        },
        {
          change:'右翼 △DOC：△DBC 减去公共 △OBC，15 − 6 = 9。两翼一样大。',
          diff:[['△DBC','15','15'],['减去 △OBC','6','6'],['右翼 △DOC','未知','9 ✔']],
          why:'公共块还是那块 △OBC。左翼右翼都是 15 减 6，所以都是 9。',
          formula:'15 − 6 = 9；△AOB = △DOC = 9',
          run(viz){
            reveal($('#fill-doc', viz));
            reveal($('#lab-doc', viz));
            reveal($('#c9R', viz));
          }
        }
      ]
    }
  ],

  points:[
    {
      theorem:'平行线之间高相等：顶点沿着平行线移动，面积不变。',
      read:'原题 <em>P</em> 在 <em>AB</em> 上任意滑；变式 <em>A</em> 与 <em>D</em> 都在 <em>BC</em> 的平行线 <em>AD</em> 上。'
    },
    {
      theorem:'同底同高的三角形面积相等；和平行四边形同底同高则是一半。',
      read:'原题 <em>△PCD</em> 是平行四边形的一半，得 <em>10</em>；变式 <em>△ABC</em> 与 <em>△DBC</em> 同底 <em>BC</em> 同高，都是 <em>15</em>。'
    },
    {
      theorem:'大块减去公共小块，得到侧翼面积。',
      read:'变式 <em>15 − 6</em> 得到左翼 <em>9</em>；同样 <em>15 − 6</em> 得到右翼 <em>9</em>。原题则是整块 <em>20</em> 减去另一半。'
    },
    {
      theorem:'梯形两底平行时，左右两翼面积相等。',
      read:'<em>△AOB</em> 与 <em>△DOC</em> 都是 <em>9</em>。和原题「任意点面积一样」是同一件事。'
    }
  ]
};
