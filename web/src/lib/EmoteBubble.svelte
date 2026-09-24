<script lang="ts">
  import type { EmoteDef } from './types'

  interface Props {
    emote: EmoteDef
    /** 每次發送都換一個 key，讓動畫重播 */
    key?: number
    size?: 'sm' | 'md'
  }
  let { emote, key = 0, size = 'md' }: Props = $props()

  // 長文字要縮小，不然會撐破氣泡
  const long = $derived(emote.kind === 'text' && (emote.text?.length ?? 0) > 2)
</script>

{#key key}
  <!-- anchor 負責定位，bubble 負責動畫，兩者分開才不會 transform 打架 -->
  <div class="anchor {size}">
    <div class="bubble" class:long title={emote.label}>
      {#if emote.kind === 'image'}
        <img src={emote.url} alt={emote.label} />
      {:else}
        <span class="txt">{emote.text}</span>
      {/if}
    </div>
  </div>
{/key}

<style>
  .anchor {
    position: absolute;
    top: -1.5rem;
    left: 50%;
    transform: translateX(-50%);
    z-index: 30;
    pointer-events: none;
  }

  .anchor.sm {
    top: -1.2rem;
  }

  .bubble {
    position: relative;
    display: grid;
    place-items: center;
    padding: 0.5rem 0.8rem;
    border-radius: 1.2rem;
    background: rgb(255 255 255 / 0.96);
    color: #12261c;
    box-shadow: 0 8px 22px rgb(0 0 0 / 0.55);
    animation:
      emote-in 0.22s cubic-bezier(0.34, 1.56, 0.64, 1),
      emote-out 0.4s ease-in 3.1s forwards;
  }

  .bubble::after {
    content: '';
    position: absolute;
    bottom: -0.32rem;
    left: 50%;
    margin-left: -0.35rem;
    width: 0.7rem;
    height: 0.7rem;
    background: inherit;
    transform: rotate(45deg);
    border-radius: 0 0 0.15rem 0;
  }

  .bubble img {
    width: 5rem;
    height: 5rem;
    object-fit: contain;
    display: block;
  }

  .anchor.sm .bubble img {
    width: 3.5rem;
    height: 3.5rem;
  }

  .txt {
    font-size: 2.4rem;
    font-weight: 800;
    line-height: 1.1;
    white-space: nowrap;
  }

  .bubble.long .txt {
    font-size: 1.6rem;
  }

  .anchor.sm .txt {
    font-size: 1.75rem;
  }

  .anchor.sm .bubble.long .txt {
    font-size: 1.15rem;
  }

  @keyframes emote-in {
    from {
      opacity: 0;
      transform: translateY(0.5rem) scale(0.7);
    }
  }

  @keyframes emote-out {
    to {
      opacity: 0;
      transform: translateY(-0.6rem) scale(0.9);
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .bubble {
      animation: none;
    }
  }
</style>
