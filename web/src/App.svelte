<script lang="ts">
  import { net } from './lib/net.svelte'
  import Lobby from './lib/Lobby.svelte'
  import WaitingRoom from './lib/WaitingRoom.svelte'
  import Table from './lib/Table.svelte'

  // 網址帶 #ROOMID 可直接進房，方便丟給區網的朋友
  $effect(() => {
    const hash = location.hash.replace('#', '').toUpperCase()
    if (hash && !net.roomId) net.connect(hash, net.name || '玩家')
  })

  $effect(() => {
    location.hash = net.roomId ? net.roomId : ''
  })
</script>

{#if !net.room}
  <Lobby />
{:else if !net.room.started || !net.game}
  <WaitingRoom />
{:else}
  <Table />
{/if}

{#if net.status === 'closed' && net.roomId}
  <div class="fixed bottom-3 left-1/2 -translate-x-1/2 bg-red-600 text-white px-4 py-2 rounded-lg text-sm">
    連線中斷，重新連線中…
  </div>
{/if}
