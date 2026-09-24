<script lang="ts">
  import { net } from './net.svelte'

  let name = $state(net.name || '玩家')
  let joinId = $state('')
  let creating = $state(false)
  let rooms = $state<Array<{ id: string; name: string; seats: number; maxPlayers: number; started: boolean; mode: string }>>([])
  let form = $state({
    name: '我的房間',
    mode: 'hanchan',
    singleTable: 'a',
    maxPlayers: 4,
    minHan: 1,
    tsumoMode: 'menzen_tsumo',
    doraWrap: true,
    actSeconds: 30,
    claimSeconds: 10,
    untimed: false,
    emotesEnabled: true,
  })

  async function refresh() {
    try {
      rooms = await (await fetch('/api/rooms')).json()
    } catch {
      /* server 未啟動 */
    }
  }
  $effect(() => {
    refresh()
    const id = setInterval(refresh, 4000)
    return () => clearInterval(id)
  })

  async function create() {
    creating = true
    try {
      const r = await fetch('/api/rooms', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(form),
      })
      const { id } = await r.json()
      net.connect(id, name)
    } finally {
      creating = false
    }
  }
</script>

<div class="min-h-full grid place-items-center p-4">
  <div class="w-full max-w-5xl grid gap-5 lg:grid-cols-[1.1fr_1fr]">
    <header class="lg:col-span-2 text-center py-6">
      <h1 class="text-4xl font-black tracking-tight">
        <span class="text-banana">BANANA</span> 英文字母麻將
      </h1>
      <p class="op-70 mt-2 text-sm">A–Z 共 144 張・順子＝連續字母・規則比照日麻・2–6 人連線對戰</p>
    </header>

    <section class="card grid gap-3">
      <h2 class="font-bold text-lg">建立房間</h2>
      <label class="grid gap-1 text-sm">
        <span class="op-70">你的暱稱</span>
        <input class="bg-black/40 rounded px-3 py-2 border border-white/10" bind:value={name} maxlength="16" />
      </label>
      <label class="grid gap-1 text-sm">
        <span class="op-70">房間名稱</span>
        <input class="bg-black/40 rounded px-3 py-2 border border-white/10" bind:value={form.name} maxlength="32" />
      </label>
      <div class="grid grid-cols-2 gap-3">
        <label class="grid gap-1 text-sm">
          <span class="op-70">賽制</span>
          <select class="bg-black/40 rounded px-3 py-2 border border-white/10" bind:value={form.mode}>
            <option value="hanchan">半莊戰</option>
            <option value="tonpuu">東風戰</option>
            <option value="single">一局戰</option>
          </select>
        </label>
        <label class="grid gap-1 text-sm">
          <span class="op-70">人數上限</span>
          <select class="bg-black/40 rounded px-3 py-2 border border-white/10" bind:value={form.maxPlayers}>
            {#each [2, 3, 4, 5, 6] as n}<option value={n}>{n} 人</option>{/each}
          </select>
        </label>
      </div>
      {#if form.mode === 'single'}
        <label class="grid gap-1 text-sm">
          <span class="op-70">一局戰計分法</span>
          <select class="bg-black/40 rounded px-3 py-2 border border-white/10" bind:value={form.singleTable}>
            <option value="a">方法一（與日麻較相近）</option>
            <option value="b">方法二（六番以上分段細化）</option>
          </select>
        </label>
      {/if}
      <div class="grid grid-cols-2 gap-3">
        <label class="grid gap-1 text-sm">
          <span class="op-70">自摸役</span>
          <select class="bg-black/40 rounded px-3 py-2 border border-white/10" bind:value={form.tsumoMode}>
            <option value="menzen_tsumo">門前清自摸和（1番）</option>
            <option value="tsumo">自摸（2番，副露減一）</option>
          </select>
        </label>
        <label class="grid gap-1 text-sm">
          <span class="op-70">番縛</span>
          <select class="bg-black/40 rounded px-3 py-2 border border-white/10" bind:value={form.minHan}>
            {#each [1, 2, 3] as n}<option value={n}>{n} 番縛</option>{/each}
          </select>
        </label>
      </div>
      <div class="grid grid-cols-2 gap-3">
        <label class="grid gap-1 text-sm">
          <span class="flex justify-between">
            <span class="op-70">出牌時間</span>
            <span class="tabular-nums text-banana">{form.untimed ? '—' : form.actSeconds + ' 秒'}</span>
          </span>
          <input type="range" min="5" max="300" step="5" bind:value={form.actSeconds} disabled={form.untimed} />
        </label>
        <label class="grid gap-1 text-sm">
          <span class="flex justify-between">
            <span class="op-70">鳴牌回應</span>
            <span class="tabular-nums text-banana">{form.untimed ? '—' : form.claimSeconds + ' 秒'}</span>
          </span>
          <input type="range" min="3" max="120" step="1" bind:value={form.claimSeconds} disabled={form.untimed} />
        </label>
      </div>

      <label class="flex items-center gap-2 text-sm op-80">
        <input type="checkbox" bind:checked={form.untimed} />
        不限時（關掉逾時自動打牌）
      </label>
      <label class="flex items-center gap-2 text-sm op-80">
        <input type="checkbox" bind:checked={form.emotesEnabled} />
        允許表情
      </label>
      <label class="flex items-center gap-2 text-sm op-80">
        <input type="checkbox" bind:checked={form.doraWrap} />
        Z 的寶牌指示環繞回 A（規則書未定義）
      </label>
      <button class="btn-primary" onclick={create} disabled={creating}>建立並進入</button>
    </section>

    <section class="card grid gap-3 content-start">
      <h2 class="font-bold text-lg">加入房間</h2>
      <div class="flex gap-2">
        <input
          class="bg-black/40 rounded px-3 py-2 border border-white/10 flex-1 font-mono uppercase"
          placeholder="房號"
          bind:value={joinId}
          maxlength="8"
        />
        <button class="btn-primary" onclick={() => net.connect(joinId, name)} disabled={!joinId}>進入</button>
      </div>

      <div class="grid gap-2 max-h-72 overflow-auto">
        {#each rooms as r (r.id)}
          <button
            class="flex items-center justify-between gap-3 rounded-lg bg-white/5 hover:bg-white/10 px-3 py-2 text-left"
            onclick={() => net.connect(r.id, name)}
          >
            <div>
              <div class="font-semibold">{r.name}</div>
              <div class="text-xs op-60 font-mono">{r.id} · {modeLabel(r.mode)}</div>
            </div>
            <div class="text-sm op-80">
              {r.seats}/{r.maxPlayers}
              {#if r.started}<span class="text-banana ml-1">進行中</span>{/if}
            </div>
          </button>
        {:else}
          <p class="op-50 text-sm py-6 text-center">目前沒有房間</p>
        {/each}
      </div>
      {#if net.error}<p class="text-red-400 text-sm">{net.error}</p>{/if}
    </section>
  </div>
</div>

<style>
  input[type='range'] {
    accent-color: #f2c744;
    width: 100%;
  }
</style>

<script lang="ts" module>
  export function modeLabel(m: string) {
    return { hanchan: '半莊戰', tonpuu: '東風戰', single: '一局戰' }[m] ?? m
  }
</script>
