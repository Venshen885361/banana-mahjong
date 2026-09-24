<script lang="ts">
  import Tile from './Tile.svelte'
  import EmoteBubble from './EmoteBubble.svelte'
  import { net } from './net.svelte'
  import type { PlayerView } from './types'

  interface Props {
    p: PlayerView
    isDealer: boolean
    isTurn: boolean
    dora: number[]
  }
  let { p, isDealer, isTurn, dora }: Props = $props()

  const live = $derived(net.liveEmotes[p.seat])
  const muted = $derived(net.mutedSeats.includes(p.seat))
</script>

<div
  class="relative rounded-xl border p-2 grid gap-2 transition
         {isTurn ? 'border-banana/70 bg-banana/5' : 'border-white/10 bg-black/20'}"
>
  {#if live}
    <EmoteBubble emote={live.emote} key={live.key} size="sm" />
  {/if}

  <div class="flex items-center gap-2 text-sm">
    {#if isDealer}<span class="px-1.5 rounded bg-red-600 text-white text-xs font-bold">莊</span>{/if}
    <span class="font-semibold truncate">{p.name}</span>
    {#if p.isBot}<span class="text-xs op-50">BOT</span>{/if}
    {#if p.riichi}<span class="text-xs text-banana font-bold">立直</span>{/if}
    <span class="ml-auto tabular-nums op-80">{p.points.toLocaleString()}</span>
    <button
      class="text-xs op-40 hover:op-90 transition leading-none"
      title={muted ? '取消靜音這位玩家的表情' : '靜音這位玩家的表情'}
      aria-label={muted ? '取消靜音' : '靜音'}
      onclick={() => net.toggleMute(p.seat)}
    >
      {muted ? '🔇' : '🔔'}
    </button>
  </div>

  <div class="flex gap-0.5 flex-wrap items-end">
    {#each Array(p.handCount) as _, i (i)}
      <Tile size="xs" back />
    {/each}
    {#each p.melds as m, mi (mi)}
      <span class="inline-flex gap-0.5 ml-1.5">
        {#each m.tiles as t, ti (ti)}
          <Tile
            size="xs"
            tile={t}
            back={m.type === 'ankan' && (ti === 0 || ti === 3)}
            called={m.type !== 'ankan' && ti === 0}
          />
        {/each}
      </span>
    {/each}
  </div>

  <div class="flex flex-wrap gap-0.5 min-h-6 rounded bg-black/25 p-1">
    {#each p.river as d, i (i)}
      <Tile size="xs" tile={d.tile} dim={d.claimed} dora={dora.includes(d.tile)} rotated={d.riichi} />
    {/each}
  </div>
</div>
