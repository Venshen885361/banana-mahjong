# 🍌 Banana 英文字母麻將

以 [OHOHOHHOHOHO/banana-majong](https://github.com/OHOHOHHOHOHO/banana-majong) 的規則為基準重寫的 **Python 規則引擎 + WebSocket 伺服器 + Svelte 5 前端**，支援 **2–6 人區網連線對戰**，規則書上的**全部役種**都已實作並算分。

原 repo 只有 `main.cpp`（牌山 / 洗牌 / 發牌 / 寶牌 + 一個和牌判定），`chii / pon / kan / reach` 都還是空函式；規則本體來自 repo 內的 `Banana英文字母麻將規則.docx`。

---

## 遊戲規則摘要

| 項目 | 內容 |
|---|---|
| 牌 | A–Z 共 26 種、**144 張**（張數 = repo 的 `card_amount`，如 E 有 18 張、J/K/Q/X/Z 各 2 張） |
| 順子 | **連續三個字母**（`ABC` … `XYZ`，不環繞） |
| 手牌 | 13 張 + 摸牌，4 面子 + 1 雀頭 |
| 特殊型 | 七對子、**一條龍**（連續 14 張各一） |
| 王牌 | 14 張 = 4 嶺上 + 5 寶牌指示 + 5 裡寶指示；槓一次多翻一張，最多 5 張 |
| 流程 | 吃碰槓、立直、振聽、搶槓、嶺上、海底/河底，**比照日麻** |
| 計分 | **不計符**，分 半莊/東風（上閒下莊表）與 一局戰（方法一/二） |
| 起始點 | 35000（建議），番縛 1 番 |

---

## 快速開始（本機開發）

需要 [Bun](https://bun.sh) 與 Python ≥ 3.11（用 [uv](https://docs.astral.sh/uv/) 最快）。

```bash
# 後端
cd server
uv sync                       # 或：pip install -e ".[dev]"
uv run uvicorn banana.app:app --reload --port 8000

# 前端（另開一個 terminal）
cd web
bun install
bun run dev                   # http://localhost:5173，已 proxy /api 與 /ws 到 :8000
```

打開 `http://localhost:5173`，建立房間 → 加 Bot 或把房號給朋友 → 開始。

## 區網對戰（單一 server，其他人用瀏覽器連）

```bash
cd web && bun run build                 # 產出 web/dist
cd ../server && uv run banana-server     # 預設 0.0.0.0:8000，會直接吐出 web/dist
```

同區網的人開 `http://<你的內網 IP>:8000` 就能進來。網址後面加 `#房號` 可直接進房，例如 `http://192.168.1.20:8000/#A1B2C3`。

> `vite dev` 已設 `host: true`，開發階段也能讓區網其他裝置連 `http://<你的 IP>:5173`。

## Docker

```bash
docker compose up --build     # http://localhost:8000
```

---

## 專案結構

```
server/
  banana/
    tiles.py   牌的常數、張數、解析/格式化
    meld.py    副露（吃碰槓）與拆解後的 Block
    hand.py    和牌拆解、聽牌/待張、向聽數（記憶化 DP）
    yaku.py    全役種判定（1/2/3/6番、役滿、兩倍、三倍）
    score.py   計分表與付點分攤
    game.py    對局狀態機（摸打、鳴牌優先權、立直、振聽、連莊）
    bot.py     向聽貪心 AI + 自我對局用的 autoplay()
    room.py    房間、bot 補位、逾時自動 pass、斷線重連
    app.py     FastAPI + WebSocket + 靜態檔
  tests/       54 個測試，覆蓋規則書上每個役種的牌型舉例
web/
  src/lib/
    net.svelte.ts  WebSocket 連線 + 全域狀態（runes）
    Lobby / WaitingRoom / Table / Opponent / Result / Tile
```

## 已實作役種

| 番 | 役種 |
|---|---|
| 1 | 立直、一發、門前清自摸和、搶槓、嶺上開花、槓振、燕返、海底摸月、河底撈魚、十二落抬、平和、一盃口、尾順、尾刻、寶牌、裡寶牌 |
| 2 | 兩立直、自摸、七對子、斷母音、對對和、三暗刻、三連刻 |
| 3 | 二盃口、一氣通貫、三同順、三槓子、二同槓 |
| 6 | 母一色、四連刻、全帶 AZ |
| 役滿 | 天和、地和、人和、累計役滿、石上三年、寶一色、三同槓、四暗刻、四槓子、四同順、九蓮寶燈、六六大順 |
| 兩倍 | 兩倍累計役滿、四暗刻單騎、純正九蓮寶燈、一條龍 |
| 三倍 | Rush E |

副露減一番、役種衝突（三連刻⇄三同順擇優、四暗刻單騎不計四暗刻、純正九蓮不計九蓮…）都已處理。
引擎會**列舉所有和牌拆解與和了牌歸屬，取分數最高者**，所以 `FGH FGH FGH` 這種同時能讀成 `FFF GGG HHH` 的牌型會自動選對你有利的那一邊。

## 規則書未定義、由設定決定的部分

規則書沒寫到的幾項，我用日麻慣例當預設值，都放在 `ScoreConfig` / 房間設定裡可調：

| 項目 | 預設 | 位置 |
|---|---|---|
| Z 的寶牌指示牌「下一張」 | 環繞回 A | `dora_wrap`（建房時可關） |
| 立直棒 | 1000 點，和牌者全拿 | `riichi_stick` |
| 本場加點 | **0**（規則書沒提本場） | `honba_bonus` |
| 流局聽牌罰符 | 總額 3000 依聽牌人數分攤 | `noten_penalty` |
| 多家榮和 | 全部成立，依打者下家順序結算 | `Game._multi_ron` |
| 連莊 | 莊家和牌或流局聽牌 | `renchan_on_dealer_tenpai` |

## 測試

```bash
cd server
uv run pytest -q              # 54 passed
uv run ruff check .
```

`tests/test_yaku.py` 直接拿規則書的牌型舉例當 fixture；`tests/test_game.py` 會讓 bot 在 2/3/4/5/6 人下跑完整場，檢查**點數總和守恆**與流程不會卡死。

## 接下來可以做

- 頭跳制（現在是多家榮和全成立）
- 前端加上牌河的巡目對齊、立直棒動畫
- bot 的守備（現在只有「立直家的現物優先」這種很粗的安全度）
- 觀戰模式與牌譜回放（`Game.events` 已經是完整事件流，直接存下來就能重播）
