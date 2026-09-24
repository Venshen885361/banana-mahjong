<script lang="ts">
  import { net } from './net.svelte'
  import Tile from './Tile.svelte'
  import { doraTiles } from './rules'
  import type { HandResult, PlayerView, WinnerView } from './types'

  interface Props {
    result: HandResult
    players: PlayerView[]
    isHost: boolean
    gameOver: boolean
  }
  let { result, players, isHost, gameOver }: Props = $props()

  // 單人和牌與多家榮和統一成一個陣列
  const winners = $derived<WinnerView[]>(
    result.winners ??
      (result.winner != null
        ? [
            {
              winner: result.winner,
              yaku: result.yaku ?? [],
              yakuman: result.yakuman ?? [],
              han: result.han ?? 0,
              multiplier: result.multiplier ?? 0,
              points: result.points ?? 0,
              hand: result.hand ?? [],
              melds: result.melds ?? [],
            },
          ]
        : []),
  )
  const dora = $derived(doraTiles(result.dora ?? [], net.room?.config.doraWrap ?? true))
  const ura = $derived(doraTiles(result.ura ?? [], net.room?.config.doraWrap ?? true))

  function scoreLabel(w: WinnerView) {
    if (w.multiplier) {
      const names = { 1: '役滿', 2: '兩倍役滿', 3: '三倍役滿', 4: '四倍役滿' }
      return names[w.multiplier as 1 | 2 | 3 | 4] ?? `${w.multiplier} 倍役滿`
    }
    if (w.han >= 26) return '兩倍累計役滿'
    if (w.han >= 13) return '累計役滿'
    return `${w.han} 番`
  }

  const standings = $derived([...players].sort((a, b) => b.points - a.points))
</script>

<div class="fixed inset-0 bg-black/70 backdrop-blur grid place-items-center p-4 z-50 overflow-auto">
  <div class="card max-w-2xl w-full grid gap-4 bg-felt-deep">
    {#if result.type === 'draw'}
      <h2 class="text-2xl font-black">流局</h2>
      <p class="op-80 text-sm">
        聽牌：{result.tenpai?.length ? result.tenpai.map((s) => players[s].name).join('、') : '無人聽牌'}
      </p>
    {:else}
      {#each winners as w (w.winner)}
        <section class="grid gap-3 border-b border-white/10 pb-4 last:border-0 last:pb-0">
          <div class="flex items-baseline gap-2">
            <h2 class="text-2xl font-black">
              {players[w.winner].name}
              <span class="text-banana">{result.tsumo ? '自摸' : '榮和'}</span>
            </h2>
            <span class="ml-auto text-xl font-black tabular-nums text-banana">
              {scoreLabel(w)} · {w.points.toLocaleString()} 點
            </span>
          </div>

          <div class="flex flex-wrap items-end gap-0.5">
            {#each [...w.hand].sort((a, b) => a - b) as t, i (`${t}-${i}`)}
              <Tile size="sm" tile={t} dora={dora.includes(t) || ura.includes(t)} />
            {/each}
            {#each w.melds as m, mi (mi)}
              <span class="inline-flex gap-0.5 ml-2">
                {#each m.tiles as t, ti (ti)}
                  <Tile
                    size="sm"
                    tile={t}
                    back={m.type === 'ankan' && (ti === 0 || ti === 3)}
                    called={m.type !== 'ankan' && ti === 0}
                    dora={dora.includes(t) || ura.includes(t)}
                  />
                {/each}
              </span>
            {/each}
          </div>

          <ul class="grid grid-cols-2 sm:grid-cols-3 gap-x-4 gap-y-1 text-sm">
            {#each w.yakuman as y (y.name)}
              <li class="flex justify-between text-banana font-bold">
                <span>{y.name}</span><span>×{y.mult}</span>
              </li>
            {/each}
            {#each w.yaku as y (y.name)}
              <li class="flex justify-between">
                <span class="op-85">{y.name}</span><span class="op-60 tabular-nums">{y.han} 番</span>
              </li>
            {/each}
          </ul>
        </section>
      {/each}

      <div class="flex gap-4 text-xs op-70">
        <span class="flex items-center gap-1">
          寶牌 {#each result.dora ?? [] as d (d)}<Tile size="xs" tile={d} dora />{/each}
        </span>
        {#if (result.ura ?? []).length}
          <span class="flex items-center gap-1">
            裡寶 {#each result.ura ?? [] as d (d)}<Tile size="xs" tile={d} dora />{/each}
          </span>
        {/if}
      </div>
    {/if}

    <table class="w-full text-sm">
      <tbody>
        {#each players as p (p.seat)}
          <tr class="border-t border-white/10">
            <td class="py-1">{p.name}</td>
            <td class="py-1 text-right tabular-nums">{p.points.toLocaleString()}</td>
            <td
              class="py-1 text-right tabular-nums w-20 {(result.delta[p.seat] ?? 0) >= 0
                ? 'text-emerald-400'
                : 'text-red-400'}"
            >
              {(result.delta[p.seat] ?? 0) >= 0 ? '+' : ''}{(result.delta[p.seat] ?? 0).toLocaleString()}
            </td>
          </tr>
        {/each}
      </tbody>
    </table>

    {#if gameOver}
      <div class="grid gap-2">
        <h3 class="font-bold">最終順位</h3>
        <ol class="grid gap-1 text-sm">
          {#each standings as p, i (p.seat)}
            <li class="flex justify-between bg-white/5 rounded px-3 py-1">
              <span>{i + 1}. {p.name}</span>
              <span class="tabular-nums">{p.points.toLocaleString()}</span>
            </li>
          {/each}
        </ol>
        <button class="btn-primary" onclick={() => net.leave()}>回大廳</button>
      </div>
    {:else if isHost}
      <button class="btn-primary" onclick={() => net.send({ t: 'nextHand' })}>下一局</button>
    {:else}
      <p class="op-60 text-sm text-center">等待下一局…</p>
    {/if}
  </div>
</div>
