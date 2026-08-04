/**
 * 示例轻量模块：习惯打卡。
 *
 * 这个文件展示自定义模块的完整契约：
 *   1. 导出 mount(root, ctx)，小窝会把一块空的面板和能力包交给你；
 *   2. 用 ctx.store 落地数据，不需要自己写后端；
 *   3. 返回 { unmount, update } 让小窝在切页和停用时能正确回收。
 *
 * 样式全部复用小窝的共享变量与组件类（.card、.button、--ink 等），
 * 这样纸庭、玻璃小屋、夜间工作室三套官方外观都能自动套用。
 */

const STORE_KEY = "checkins";

function today() {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${now.getFullYear()}-${month}-${day}`;
}

function recentDays(count = 14) {
  const days = [];
  for (let offset = count - 1; offset >= 0; offset -= 1) {
    const date = new Date();
    date.setDate(date.getDate() - offset);
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    days.push(`${date.getFullYear()}-${month}-${day}`);
  }
  return days;
}

export async function mount(root, ctx) {
  let checkins = (await ctx.store.get(STORE_KEY, [])) || [];

  function streak() {
    const marked = new Set(checkins);
    let count = 0;
    const cursor = new Date();
    while (marked.has(cursor.toISOString().slice(0, 10))) {
      count += 1;
      cursor.setDate(cursor.getDate() - 1);
    }
    return count;
  }

  function render() {
    const marked = new Set(checkins);
    const done = marked.has(today());
    root.innerHTML = `
      <header class="topbar">
        <div class="page-title"><p>示例模块</p><h1>习惯打卡</h1></div>
        <div class="actions">
          <button class="button ${done ? "" : "primary"}" data-toggle type="button">
            ${done ? "取消今天的打卡" : "打卡今天"}
          </button>
        </div>
      </header>
      <section class="card">
        <div class="card-head"><h2>最近两周</h2><span class="muted">连续 ${streak()} 天</span></div>
        <div class="card-body">
          <div class="chips small">
            ${recentDays()
              .map(
                (date) =>
                  `<span class="chip ${marked.has(date) ? "danger-chip" : ""}" title="${ctx.escapeHtml(date)}">${ctx.escapeHtml(date.slice(5))}</span>`
              )
              .join("")}
          </div>
          <p class="muted">数据保存在 modules/habit-board/data/store/，通过小窝的通用存储接口读写。</p>
        </div>
      </section>
    `;
    root.querySelector("[data-toggle]")?.addEventListener("click", toggleToday);
  }

  async function toggleToday() {
    const date = today();
    checkins = checkins.includes(date) ? checkins.filter((item) => item !== date) : [...checkins, date];
    try {
      await ctx.store.set(STORE_KEY, checkins);
      ctx.notify(checkins.includes(date) ? "今天已打卡" : "已取消今天的打卡");
    } catch (err) {
      ctx.reportError(`保存失败：${err.message}`);
    }
    render();
  }

  render();

  return {
    async update() {
      checkins = (await ctx.store.get(STORE_KEY, [])) || [];
      render();
    },
    unmount() {
      root.innerHTML = "";
    },
  };
}
