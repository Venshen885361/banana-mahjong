<script lang="ts">
  import { net } from './net.svelte'
  import { modeLabel } from './Lobby.svelte'

  const room = $derived(net.room!)
  const canStart = $derived(room.seats.length >= 2)
</script>

<div class="min-h-full grid place-items-center p-4">
  <div class="card w-full max-w-xl grid gap-4">
    <div class="flex items-baseline justify-between">
      <h1 class="text-2xl font-black">{room.name}</h1>
      <code class="text-banana text-xl tracking-widest">{room.id}</code>
    </div>
    <p class="text-sm op-70">
      {modeLabel(room.config.mode)} · 上限 {room.config.maxPlayers} 人 · {room.config.minHan} 番縛 ·
      起始 {room.config.startPoints}
    </p>

    <ul class="grid gap-2">
      {#each room.seats as s (s.index)}
        <li class="flex items-center gap-3 bg-white/5 rounded-lg px-3 py-2">
          <span class="w-6 h-6 grid place-items-center rounded bg-white/10 text-xs font-bold">
            {s.index + 1}
          </span>
          <span class="font-semibold">{s.name}</span>
          {#if s.index === room.hostSeat}<span class="text-xs text-banana">房主</span>{/if}
          {#if s.isBot}<span class="text-xs op-60">BOT</span>{/if}
          {#if !s.isBot}
            <span class="text-xs {s.connected ? 'text-emerald-400' : 'text-red-400'}">
              {s.connected ? '已連線' : '斷線'}
            </span>
          {/if}
          {#if net.isHost && s.index !== net.seat}
            <button class="ml-auto btn-ghost text-xs py-1" onclick={() => net.send({ t: 'removeSeat', seat: s.index })}>
              移除
            </button>
          {/if}
        </li>
      {/each}
      {#each Array(Math.max(0, room.config.maxPlayers - room.seats.length)) as _, i (i)}
        <li class="rounded-lg border border-dashed border-white/15 px-3 py-2 text-sm op-40">等待玩家…</li>
      {/each}
    </ul>

    <div class="flex gap-2">
      {#if net.isHost}
        <button
          class="btn-ghost"
          onclick={() => net.send({ t: 'addBot' })}
          disabled={room.seats.length >= room.config.maxPlayers}>加入 Bot</button
        >
        <button class="btn-primary flex-1" onclick={() => net.send({ t: 'start' })} disabled={!canStart}>
          開始遊戲
        </button>
      {:else}
        <p class="op-70 text-sm py-2">等待房主開始…</p>
      {/if}
      <button class="btn-ghost" onclick={() => net.leave()}>離開</button>
    </div>

    <p class="text-xs op-50">
      把房號 <code class="text-banana">{room.id}</code> 或這個網址給同區網的朋友，他們用瀏覽器就能進來。
    </p>
    {#if net.error}<p class="text-red-400 text-sm">{net.error}</p>{/if}
  </div>
</div>
