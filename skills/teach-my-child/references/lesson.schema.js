/* 课数据骨架。完整可跑示例见同目录 area.lesson.js */
const LESSON = {
  title: '页面标题',
  lead: '一段导语',
  footnote: '页脚，可空',
  questions: [
    {
      tag: '小标签，可空',
      tagExt: false,
      stem: '题干',
      conds: ['条件'],
      tip: '提示，可空',
      thumb: '<svg></svg>',
      style: '',
      speed: 1100,
      build(viz) {
        viz.innerHTML = '一张完整底图';
        return {
          reset() {
            /* conceal 尚未发生的痕迹，点回到原位 */
          }
        };
      },
      steps: [
        {
          change: '这一步图上什么变了',
          diff: [['状态量', '旧值', '新值']],
          why: '为什么这样变',
          formula: '一条公式',
          run(viz) {
            reveal($('#aux', viz));
          }
        }
      ]
    }
  ],
  points: [
    { theorem: '原理或定理（蓝色）', read: '结合题目的解读（灰色，两题同一句）' }
  ]
};
