<script lang="ts">
  interface Props {
    tile?: number
    size?: 'xs' | 'sm' | 'md'
    back?: boolean
    dora?: boolean
    rotated?: boolean
    called?: boolean
    dim?: boolean
    drawn?: boolean
    clickable?: boolean
    onclick?: () => void
    title?: string
  }

  let {
    tile = 0,
    size = 'md',
    back = false,
    dora = false,
    rotated = false,
    called = false,
    dim = false,
    drawn = false,
    clickable = false,
    onclick,
    title,
  }: Props = $props()

  const letter = $derived(String.fromCharCode(65 + tile))
</script>

{#if clickable}
  <button
    class="tile pop {size !== 'md' ? size : ''}"
    class:back
    class:dora
    class:rotated
    class:called
    class:dim
    class:drawn
    class:clickable
    {title}
    {onclick}
  >
    {back ? '' : letter}
  </button>
{:else}
  <div
    class="tile {size !== 'md' ? size : ''}"
    class:back
    class:dora
    class:rotated
    class:called
    class:dim
    class:drawn
    {title}
  >
    {back ? '' : letter}
  </div>
{/if}

<style>
  button.tile {
    padding: 0;
    cursor: pointer;
    font-family: inherit;
  }
</style>
