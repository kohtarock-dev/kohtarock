# kohtarock — エリアトラウト仕入れウォッチャー

エリアトラウト用品(ロッド・ルアー等)のせどり用に、複数のネットショップ・フリマ/オークションから
新着・入荷情報を定期的に拾い、Web画面で一覧表示 & LINEに通知するアプリです。

- 常駐サーバー(FastAPI)+ Web UI
- ソースごとに巡回間隔を設定して定期ポーリング(APScheduler)
- キーワードでの絞り込み・除外
- 新着を検出したらLINE(Messaging API)にプッシュ通知
- ソースはプラグイン形式で追加可能

## 対応ソースタイプ

| type                | 説明                                                                 |
|---------------------|----------------------------------------------------------------------|
| `rakuten_api`        | 楽天市場 商品検索API(公式・要APIキー、無料)                          |
| `yahoo_shopping_api` | Yahoo!ショッピング 商品検索API(公式・要APIキー、無料)                |
| `rss`                | 汎用RSS/Atom購読(ショップの新着RSS、ヤフオク!検索結果RSS等)           |
| `html_polite`        | robots.txtを尊重する汎用HTMLポーリング(RSSが無いショップ/フリマ向け) |

## セットアップ

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# .env を編集してAPIキー・LINEの設定を入力

uvicorn app.main:app --host 0.0.0.0 --port 8000
```

ブラウザで http://localhost:8000 を開くと新着一覧が表示されます。「今すぐ巡回」ボタンで
全ソースを即座に1回巡回できます(バックグラウンド実行のため反映まで数十秒かかります)。

## APIキーの取得

- **楽天市場**: https://webservice.rakuten.co.jp/ でアプリID登録(無料) → `RAKUTEN_APP_ID`
- **Yahoo!ショッピング**: https://developer.yahoo.co.jp/ でアプリID登録(無料) → `YAHOO_APP_ID`

## LINE通知の設定

LINE Notifyは2025年3月末で新規発行・提供が終了したため、本アプリはLINE公式アカウント
(Messaging API)のbroadcast(友だち全員に配信)を使用します。個人利用ではこの公式
アカウントの友だちは基本的に自分だけなので、実質的に自分専用の通知として機能し、
面倒なユーザーID特定の作業が不要です。

1. https://developers.line.biz/console/ でプロバイダー・Messaging APIチャネルを作成
2. 「Messaging API設定」タブでチャネルアクセストークン(長期)を発行 → `LINE_CHANNEL_ACCESS_TOKEN`
3. 作成した公式アカウントのQRコードを自分のLINEで読み取り、友だち追加

未設定の場合、通知は送信されずWeb画面での確認のみになります。

## ソースの追加・編集方法

`config/sources.yaml` を編集し、アプリを再起動してください。

```yaml
default_keywords:      # 全ソース共通のデフォルト絞り込みキーワード(OR条件)
  - エリアトラウト
  - ロデオクラフト
  ...

default_exclude_keywords:  # このいずれかを含むタイトルは除外
  - 中古 ジャンク

sources:
  - name: 楽天市場
    type: rakuten_api
    enabled: true
    poll_interval_sec: 900   # 巡回間隔(秒)
    keywords: [...]          # 省略時は default_keywords を使用
    exclude_keywords: [...]  # 省略時は default_exclude_keywords を使用
```

### RSSソースの追加

多くの専門店サイトはお知らせ/新着ページにRSSを持っています。サイトのHTMLソースで
`<link rel="alternate" type="application/rss+xml" href="...">` を探すか、
`/rss`, `/feed` 等のURLを確認してください。見つかったら `type: rss` で `feed_url` を設定します。

ヤフオク!の検索結果ページにも `&rss=1` 等でRSS配信されている場合があります。
必ずブラウザで検索URLを開いてRSSリンクの有無を確認してから設定してください。

以下のエリアトラウト専門店は設定済みです(いずれもrobots.txtで許可された公式RSS/Atom):

- **トラウトアイランド**(`troutisland.shop-pro.jp/?mode=rss`)
- **越谷タックルアイランド・トラウト**(`area-island.com/?mode=rss`)
- **t-Route**(`t-route.net/collections/all.atom`、Shopify公式フィード)
- **プロショップトモ**(`proshoptomo.com/?mode=rss`)
- **プロショップリバーロード**(`riverroad1091.shop/?mode=rss`)

RSSが無いショップは `html_polite` で一覧ページを直接ポーリングしています:

- **マニアックス**(RSS/Atom配信なし。商品一覧ページをポーリング)
- **タックルラウンジ**(中古エリアトラウト専門の買取・販売店。WooCommerceの「新着」グリッドをポーリング)

なお **プロショップザーキー**(fishingshop-zarky.com)はCloudflareのボット認証(JSチャレンジ)が
robots.txtの取得段階からかかっており、自動巡回はサイト側の意図に反すると判断し対応していません。

これらの店のように扱う商品のほぼ全てが対象ジャンルの専門店では、
`match_all: true` を指定するとキーワード絞り込みをせず新着を全件拾えます
(`exclude_keywords` は引き続き適用されます)。

価格情報はRSS本文に「価格: 12345」のように明示的なラベルがある場合のみ抽出します
(送料表記などの無関係な金額を誤って価格として拾わないよう、あえて限定的にしています)。
ラベルが無いフィードでは価格は「価格不明」と表示されます。

### HTMLポーリングソースの追加(専門店・フリマ等)

RSSが無いサイトは `type: html_polite` で一覧ページをCSSセレクタで抽出します。

```yaml
- name: サンプル専門店
  type: html_polite
  enabled: true
  poll_interval_sec: 1800
  list_url: "https://shop.example.com/new-arrivals"
  item_selector: "ul.item-list li.item"   # 商品1件ごとの要素
  title_selector: ".item-title"
  price_selector: ".item-price"
  link_selector: "a"
  image_selector: "img"
```

起動時に対象ドメインの `robots.txt` を自動確認し、そのパスの取得が許可されていない場合は
自動的にスキップ(ログに警告)します。ただし robots.txt は最低限のガードに過ぎないため、
**有効化する前に必ず対象サイトの利用規約(ToS)を確認**してください。

## 法的・利用上の注意(重要)

- 本アプリは自分自身の仕入れ判断を助けるための「巡回の自動化ツール」であり、
  各サービスの利用規約に反する使い方(過度な高頻度アクセス、再配布目的の大量データ収集、
  自動購入・自動入札等)を想定していません。
- **メルカリ・ラクマ・PayPayフリマ等のフリマアプリは、一般提供されている公式検索APIが
  ありません。** これらをスクレイピングする場合は、必ず各サービスの利用規約を確認し、
  禁止されていないか・レート制限を守っているかを利用者自身の責任で判断してください。
  規約に抵触する恐れがある場合は `enabled: false` のままにし、該当サービスの公式アプリ/
  Webサイトを手動で確認することを推奨します。
- `config/sources.yaml` の `html_polite` タイプは既定でrobots.txtを確認しますが、
  robots.txtで許可されていることは利用規約上の許可を意味しません。
- 楽天市場・Yahoo!ショッピングは公式APIのみを使用しており、各社のAPI利用規約の範囲内で
  動作します(APIの利用条件・レート制限は各社の規約に従ってください)。
- 取得したデータの二次配布・商用転用は行わないでください(本アプリは個人の仕入れ判断
  補助のみを目的としています)。

## テスト

```bash
pytest tests/
```

## ディレクトリ構成

```
app/
  main.py          # FastAPI エントリポイント・Web UI
  scheduler.py     # 定期巡回・新着判定・通知トリガー
  db.py            # DBモデル(Item)
  config.py        # 設定読み込み
  sources/         # ソース実装(楽天/Yahoo!/RSS/HTMLポーリング)
  notify/line.py   # LINE Messaging API通知
  templates/       # Jinja2テンプレート
  static/          # CSS
config/
  sources.yaml     # ソース一覧・キーワード設定
tests/             # pytest
```
