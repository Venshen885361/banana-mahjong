import { defineConfig, presetUno } from 'unocss'

export default defineConfig({
  presets: [presetUno()],
  theme: {
    colors: {
      felt: { DEFAULT: '#12261c', deep: '#0b1a13', line: '#1d3d2c' },
      tile: { face: '#f7f3e8', edge: '#d6cdb6', ink: '#1b1b1b' },
      banana: { DEFAULT: '#f2c744', deep: '#c99a10' },
    },
  },
  shortcuts: {
    btn: 'px-3 py-2 rounded-lg font-semibold transition select-none disabled:op-40 disabled:cursor-not-allowed',
    'btn-primary': 'btn bg-banana text-black hover:bg-banana-deep',
    'btn-ghost': 'btn bg-white/10 text-white hover:bg-white/20',
    card: 'rounded-xl bg-black/30 border border-white/10 p-4',
  },
})
