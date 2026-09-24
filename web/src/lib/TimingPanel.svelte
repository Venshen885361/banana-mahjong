<script lang="ts">
  import { net } from './net.svelte'

  interface Props {
    onclose: () => void
  }
  let { onclose }: Props = $props()

  const cfg = $derived(net.room!.config)
  let act = $state(net.room?.config.actSeconds ?? 30)
  let claim = $state(net.room?.config.claimSeconds ?? 10)
  let untimed = $state(net.room?.config.untimed ?? false)
  let emotesEnabled = $state(net.room?.config.emotesEnabled ?? true)

  function apply() {
    net.setTiming({
      actSeconds: act,
      claimSeconds: claim,
      untimed,
      emotesEnabled,
    })
    onclose()
  }

  const PRESETS = [
    { label: '快打', act: 10, claim: 5 },
    { label: '標準', act: 30, claim: 10 },
    { label: '悠閒', act: 60, claim: 20 },
  ]
</script>

<div class="fixed inset-0 bg-black/60 grid place-items-center z-50 p-4" onclick={onclose} role="none">
  <div class="card w-full max-w-sm grid gap-4 bg-felt-deep" onclick={(e) => e.stopPropagation()} role="none">
    <h2 class="font-bold text-lg">房間設定</h2>

    <div class="flex gap-2">
      {#each PRESETS as p (p.label)}
        <button
          class="btn-ghost flex-1 text-sm"
          onclick={() => {
            act = p.act
            claim = p.claim
            untimed = false
          }}
        >
          {p.label}
        </button>
      {/each}
    </div>

    <label class="grid gap-1 text-sm">
      <span class="flex justify-between">
        <span class="op-80">出牌時間</span>
        <span class="tabular-nums text-banana">{act} 秒</span>
      </span>
      <input type="range" min="5" max="300" step="5" bind:value={act} disabled={untimed} />
    </label>

    <label class="grid gap-1 text-sm">
      <span class="flex justify-between">
        <span class="op-80">吃碰槓 / 榮和回應時間</span>
        <span class="tabular-nums text-banana">{claim} 秒</span>
      </span>
      <input type="range" min="3" max="120" step="1" bind:value={claim} disabled={untimed} />
    </label>

    <label class="flex items-center gap-2 text-sm">
      <input type="checkbox" bind:checked={untimed} />
      不限時（關掉所有逾時自動打牌）
    </label>

    <label class="flex items-center gap-2 text-sm">
      <input type="checkbox" bind:checked={emotesEnabled} />
      允許表情
    </label>

    <p class="text-xs op-50">改動會在下一個決策點生效，不會打斷現在這一手。</p>

    <div class="flex gap-2">
      <button class="btn-primary flex-1" onclick={apply}>套用</button>
      <button class="btn-ghost" onclick={onclose}>取消</button>
    </div>
    <p class="text-xs op-40">目前：{cfg.untimed ? '不限時' : `${cfg.actSeconds}s / ${cfg.claimSeconds}s`}</p>
  </div>
</div>

<style>
  input[type='range'] {
    accent-color: #f2c744;
    width: 100%;
  }
</style>
