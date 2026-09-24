<script lang="ts">
  import { net } from './net.svelte'

  let open = $state(false)
  let cooling = $state(false)

  const catalog = $derived(net.emoteCatalog)
  const enabled = $derived(net.room?.config.emotesEnabled !== false)

  function pick(id: string) {
    if (cooling) return
    net.sendEmote(id)
    cooling = true
    setTimeout(() => (cooling = false), 2000) // 對齊 server 的冷卻
    open = false
  }

  // 點外面關掉
  $effect(() => {
    if (!open) return
    const close = (e: MouseEvent) => {
      if (!(e.target as HTMLElement).closest('[data-emote-root]')) open = false
    }
    document.addEventListener('click', close)
    return () => document.removeEventListener('click', close)
  })
</script>

{#if enabled && catalog.length}
  <div class="relative" data-emote-root>
    <button
      class="btn-ghost text-lg leading-none px-3"
      class:op-40={cooling}
      title="表情"
      aria-label="表情"
      onclick={(e) => {
        e.stopPropagation()
        open = !open
      }}
    >
      🙂
    </button>

    {#if open}
      <div
        class="absolute bottom-full mb-2 left-0 z-40 w-[min(22rem,80vw)] max-h-64 overflow-auto
               rounded-xl border border-white/15 bg-felt-deep/95 backdrop-blur p-2
               grid grid-cols-5 sm:grid-cols-6 gap-1.5 shadow-2xl"
      >
        {#each catalog as e (e.id)}
          <button
            class="aspect-square grid place-items-center rounded-lg bg-white/5 hover:bg-white/15
                   transition p-1"
            title={e.label}
            onclick={() => pick(e.id)}
          >
            {#if e.kind === 'image'}
              <img src={e.url} alt={e.label} class="w-full h-full object-contain" />
            {:else}
              <span class="text-xl leading-none">{e.text}</span>
            {/if}
          </button>
        {/each}
      </div>
    {/if}
  </div>
{/if}
