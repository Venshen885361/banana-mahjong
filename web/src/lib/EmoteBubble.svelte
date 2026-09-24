<script lang="ts">
  import type { EmoteDef } from './types'

  interface Props {
    emote: EmoteDef
    /** 每次發送都換一個 key，讓動畫重播 */
    key?: number
    size?: 'sm' | 'md'
  }
  let { emote, key = 0, size = 'md' }: Props = $props()
</script>

{#key key}
  <div class="bubble {size}" title={emote.label}>
    {#if emote.kind === 'image'}
      <img src={emote.url} alt={emote.label} />
    {:else}
      <span class="txt">{emote.text}</span>
    {/if}
  </div>
{/key}

<style>
  .bubble {
    position: absolute;
    top: -0.6rem;
    right: -0.4rem;
    z-index: 20;
    display: grid;
    place-items: center;
    padding: 0.3rem 0.5rem;
    border-radius: 0.9rem;
    background: rgb(255 255 255 / 0.95);
    color: #12261c;
    box-shadow: 0 6px 18px rgb(0 0 0 / 0.5);
    pointer-events: none;
    animation:
      emote-in 0.22s cubic-bezier(0.34, 1.56, 0.64, 1),
      emote-out 0.4s ease-in 3.1s forwards;
  }

  .bubble::after {
    content: '';
    position: absolute;
    bottom: -0.35rem;
    right: 1rem;
    width: 0.7rem;
    height: 0.7rem;
    background: inherit;
    transform: rotate(45deg);
    border-radius: 0 0 0.15rem 0;
  }

  .bubble img {
    width: 3rem;
    height: 3rem;
    object-fit: contain;
    display: block;
  }

  .bubble.sm img {
    width: 2rem;
    height: 2rem;
  }

  .txt {
    font-size: 1.5rem;
    font-weight: 800;
    line-height: 1.1;
    white-space: nowrap;
  }

  .bubble.sm .txt {
    font-size: 1.05rem;
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
