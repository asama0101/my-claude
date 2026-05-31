---
name: runbook-check
description: 任意レイアウトのExcel作業手順書（.xlsx / .xlsm）を、関数チェック・パラメータ値検証・投入Config解決を行ったうえで複数サブエージェントで多角的にレビューし、結果をHTMLレポートで出力する。手順書のフォーマットは固定でない前提で、構造（どこがパラメータか・どれがコマンドか）はサブエージェントが解釈する。ユーザーがExcelの作業手順書・メンテナンス手順・構成変更手順のレビュー、チェック、確認、関数チェック、パラメータ確認を求めたとき、あるいは手順書の.xlsxを提示して「見て」「問題ないか」「Configどうなる」と聞いたときは、明示的に「レビュー」と言われていなくても必ずこのスキルを使う。ルーター・スイッチ・帯域制御装置・FW など物理/論理ネットワーク機器が対象。
---

# ネットワーク作業手順書レビュー（Excel・任意レイアウト対応）

Excel作業手順書をレビューする。**手順書のフォーマットは固定でない**前提で設計している。役割分担が肝：

- **スクリプトは「構造を知らなくても取れる事実」だけを出す。** 関数の解決値・エラー・参照関係の抽出（`extract_facts.py`）と、渡された値の機械検証（`validate_values.py`）。レイアウトを一切仮定しない。
- **構造の解釈（どこがパラメータか・どれが投入コマンドか）はサブエージェントが行う。** バラバラなレイアウトを読み解くのはLLMの仕事。

レビューの本質は一貫して **「手順書だけを見て深夜のメンテ枠で作業する初見に近いオペレータが、迷わず・安全に・異常時に立ち戻れるか」**。Excel手順書では関数が壊れていれば当日コマンドが生成されないため、事実抽出を最初の前処理に置く。

## 依存・前提

- **`openpyxl`（必須）**: 事実抽出に使う。未導入なら `pip install openpyxl`。**venv はスキル直下に置くのを推奨**（`python3 -m venv {skillパス}/.venv && {skillパス}/.venv/bin/pip install openpyxl`）。以降スクリプトは `{skillパス}/.venv/bin/python3` で実行する。`extract_facts.py` は未導入時に同じ案内を出して停止する。
- **LibreOffice（任意・再計算用）**: 関数の解決値は通常 Excel/LibreOffice が保存したキャッシュ値から読めるため**不要**。キャッシュが無いファイル（openpyxl で生成した手順書等）だけ再計算が要る。その場合 `extract_facts.py` が `libreoffice`/`soffice` を自動検出して再計算する（**元ファイルは変更せずコピー上で実施**）。見つからなければキャッシュ値で続行し、解決値が欠けていれば警告を出す（導入: `apt install libreoffice-calc` 等、または Excel で開いて再保存）。
- **`python3`**: スクリプトは標準ライブラリ＋openpyxl のみ。`validate_values.py` / `render_report.py` は追加依存なし・オフライン動作。

## サブエージェント方針

このスキルは**サブエージェントで実行する**。オーケストレータ（このスキルを起動した本体）は調整に徹し、重い解釈・レビューは専任サブエージェントに委譲する：
- **構造解釈エージェント**（Phase 2）：`facts.json` から構造を解釈し `interpreted.json` を作る（1体）。
- **レビューエージェント**（Phase 4）：4視点を**並行**起動（safety / recoverability / operability / security_ops）。
- **HTML突合クロスレビュアー**（Phase 6.5）：生成した HTML が元データと食い違っていないかを敵対的に突合する（1体）。

機械処理（`extract_facts.py` / `validate_values.py` / `compare_backup.py` / `render_report.py`）はオーケストレータがスクリプトとして実行する。サブエージェント（Task）が使えない環境では、各エージェントの役割をオーケストレータが順番に自分で演じる（フォールバック）。

## 構成

```
runbook-check/
├── SKILL.md
├── agents/                       # サブエージェント定義（--reference オプションとの混同を避けた名称）
│   ├── reviewers.md              # 構造解釈エージェント＋4レビュー視点の定義
│   ├── review-dimensions.md      # 14観点の判断基準
│   └── cross-reviewer.md         # HTML成果物の突合クロスレビュー（Phase 6.5）
├── examples/                     # バンドルのサンプル（sample_runbook.xlsx / sample-facts.json / sample-report.html）
└── scripts/
    ├── list_workbooks.py         # 【候補列挙】ディレクトリ走査→Excel候補をJSON（Phase 0の選択用）
    ├── extract_facts.py          # 【事実抽出】全セル・関数・解決値・エラー・参照 → facts.json（レイアウト非依存）
    ├── validate_values.py        # 【値検証】特定済みパラメータの形式/範囲/許容値 → 構造非依存
    ├── compare_backup.py         # 【現行Config照合】投入Config × 作成時バックアップ → backup_compare.json（任意）
    ├── render_report.py          # findings.json → レビューHTMLレポート（表示専従・オフライン動作）
    └── render_topology.py        # topology.json → 構成図HTML（SVG図＋機器ごとカード縦積み・JS描画・物理＋論理1枚・追加色分け）
```

### 実行時に生成される作業ディレクトリ（`review-work/`）

レビュー1回ごとに作業ディレクトリ `review-work/` を作り、各Phaseの成果物を置く。どのファイルがどのPhaseの産物かは次のとおり：

```
review-work/
├── facts.json              # Phase 1: 事実抽出（全セル・関数・解決値・エラー・参照・ref_issues）
├── interpreted.json        # Phase 2: 構造解釈（parameters / config_preview / シート役割）
├── interpreted-params.json # Phase 2: 上記 parameters 配列のみ（値検証への入力）
├── topology.json           # Phase 2: 構成図用の構造化モデル（devices/interfaces/facilities/phys_links/bgp/static_routes。devices[].sections で項目拡張可）
├── validation.json         # Phase 3: パラメータ値検証（results / findings）
├── backup_compare.json     # Phase 3.5: 現行Config照合（バックアップ指定時のみ。summary / details / findings）
├── safety.json             # Phase 4: 安全性レビュアーの指摘
├── recoverability.json     # Phase 4: 回復性レビュアーの指摘
├── operability.json        # Phase 4: オペレータ視点レビュアーの指摘
├── security_ops.json       # Phase 4: セキュリティ・運用体制レビュアーの指摘
├── findings.json           # Phase 5: 統合結果（HTML描画の入力。スキーマは後述）
├── report.html             # Phase 6: 最終レポート（成果物）
├── topology.html           # Phase 6: 構成図（インタラクティブ単体HTML・別ファイル）
├── topology.flows.json     # Phase 6: 構成図の描画データ（topology.html が参照。サイドカー）
└── cross_review.json       # Phase 6.5: HTML突合クロスレビューの結果（不一致リスト）
```

最終成果物は `report.html`（レビュー結果）と `topology.html`（構成図）。中間JSONは監査・再生成のために残す（`report.html` は `findings.json` から、`topology.html` は `topology.json` から再生成できる）。

## 実行フロー

### Phase 0: 発動時ヒアリング
レビューを始める前に、不足情報を**オーケストレータがユーザーに確認する**。会話やファイル添付で既に判明している項目は聞き返さない。可能なら選択肢を提示し、まとめて一度に尋ねる（往復を増やさない）。

**(0-1) 対象ファイルの選択（ディレクトリ参照→選択→自由入力）**
対象 .xlsx が添付や明示で確定していない場合：
1. 走査ディレクトリを決める（既定: カレント。不明なら「どのフォルダの手順書か」を尋ねる。※claude.ai のアップロード運用時は `/mnt/user-data/uploads`）。
2. 候補を列挙する：
   ```bash
   python3 {skillパス}/scripts/list_workbooks.py {ディレクトリ} [--recursive]
   ```
   出力は更新日時の新しい順の候補配列（ファイル名・更新日時・シート構成つき）。
3. 候補を**選択肢としてユーザーに提示**する（ファイル名＋更新日時＋シート名を添える）。**末尾に必ず「一覧にない（パスを自由入力）」の選択肢を付ける。**
4. ユーザーが候補を選べばそれを対象にする。「一覧にない」を選んだ場合は**フルパスを自由入力してもらう**。候補が0件のときも同様に自由入力を求める。
5. 選ばれたパスがExcel（.xlsx/.xlsm）でなければ、本スキルはExcel専用と伝える。

**(0-2) 精度が上がる確認**（不明なら既定で進める）：
- **対象機器のベンダー/機種・OSバージョン**（例: Junos / IOS-XE / 帯域制御装置の機種）。構文の妥当性判断・危険操作の解釈に使う。不明なら「構文は要確認扱い」で進める。
- **設計値の正解ソース（インプット情報のファイル）の有無**（IPAM・IP一覧・設計書・期待値表など。CSV/JSON/テキスト）。あれば Phase 3 で `validate_values.py --reference` に渡し、各パラメータを**設計値と照合**する（検証根拠に明記）。**未提供の場合、記入済みパラメータは「設計値未照合＝NG」**になる（形式は別途検証）。パスを聞き取って後続に引き継ぐ。
- **今回の想定版数**（改版履歴チェックの突合用。例: v1.2）。
- **レビューの重点**（特になし / 切り戻し重視 / セキュリティ重視 等）。重点があれば該当視点を厚めにする。
- **作成時バックアップ（現行Config）の有無**（任意・テキスト/.conf のパス。`show configuration` / `running-config` 等）。あれば Phase 3.5 で投入Configと照合し、削除対象の実在・IP/VLAN-IDの重複競合・既存IFの所属VLAN変更（端末断の恐れ）・整合度を機械チェックできる。無ければ照合はスキップする（degrade gracefully）。
- **出力先とブラウザ表示**（既定: `review-work/report.html`、可能なら自動で開く）。

確認後 `review-work/` を作成し、得た情報（対象パス・ベンダー・正解ソース・想定版数・重点・**バックアップのパス**）を後続フェーズ／各サブエージェントのプロンプトに引き継ぐ。

### Phase 1: 事実抽出（機械処理・構造解釈なし）
```bash
python3 {skillパス}/scripts/extract_facts.py {手順書パス} -o review-work/facts.json
```
`facts.json` の内容（レイアウトを仮定しない事実のみ）：
- `sheets[].cells[]`: 全非空セル（`addr` / `value`(解決値) / `formula` / `refs`(参照先) / `error`）
- `formula_cells[]`: 全関数セルと解決値・エラー有無・参照先。各関数は `ref_details`（参照先ごとの解決値・空か・宛先が使用範囲に存在するか）、`empty_refs`、`dangling_refs` を持つ。
- `referenced_cells[]`: いずれかの関数から参照されている全セル（`シート!セル`の一覧）。未参照の記入済みパラメータ検出に使う。
- `errors[]`: #REF! 等のエラー一覧（**関数エラーはここで確定**。構造に依存しない）
- `ref_issues[]`: 参照先が**空**または**宛先なし（使用範囲外/シート不在）**の関数一覧。エラー値にならずともコマンドが欠損・崩壊して生成される（構造に依存しない事実）。

### Phase 2: 構造解釈（構造解釈サブエージェント）
**構造解釈エージェントを1体起動**し、`facts.json` から**この手順書の構造を解釈**させる。固定フォーマットを仮定せず内容から判断する。**手順書はSTEPごとにシートが分かれるケースが多い**点、**コマンドが別シート（パラメータや前STEP）を関数参照するケースが多い**点、そして**作業対象は1台ではなく複数台の機器が登場するのが基本**である点を踏まえる。Phase 0で得たベンダー/想定版数も渡す。エージェントの作業：
1. **対象機器の特定（複数台前提）**: 手順書に登場する**機器を漏れなく洗い出す**（ホスト名・管理IP・役割）。シートやSTEPが機器ごとに分かれている、ホスト名列がある、コマンドの投入先が複数、等から判断する。以降のパラメータ・コマンド・構成図は**どの機器のものか**を意識して紐づける。
2. **パラメータの特定**: 「名前と値の対」になっているセル群を見つける。手がかりは、(a) 関数セルの `refs` が集中して指す先（＝可変値の供給元。別シートを指すことが多い）、(b) 値の隣に名前ラベルがある配置、(c) 型や許容範囲を示す列があればそれも拾う。各パラメータを `{name, value, cell, type?, constraint?}` にまとめる。
3. **投入コマンドの特定**: 関数で生成された文字列のうち**実機の設定コマンドのみ**を順に拾い、`{step, action, location, command, parameterized, refs, device?}` にまとめ、**シート単位**で `config_preview` を構成する。`refs` はそのまま持たせ、対象機器が分かれば `device` を付ける。**commit/save/write・show による確認・接続/ログイン手順・地の文は「設定」ではないので config_preview に含めない**（これらは手順としてレビュー対象だが投入Configには載せない）。
4. **シートの役割を認識**: STEP手順シート、パラメータシート、改版履歴シート（改版履歴/変更履歴/版数/Revision 等）、構成図など。
5. **構成図用の構造化モデル `topology.json` を組み立てる**: 手順書・インプット（＋あれば現行Config）から、ネットワークを**構造化JSON**にまとめる。これを専用HTML（`topology.html`）が参照して物理＋論理を1枚に描く。抽出する要素と形式（各要素に **`status: "existing" | "added"`**。`added` = **投入Config（config_preview の set/追加）が新設する要素**）：
   ```
   topology = {
     "title": "...",
     "devices":       [{"id","hostname","as","status","sections?":[...]}],     // ホスト名・AS番号（＋拡張セクション）
     "interfaces":    [{"id","device","name","description","ip","vlan","status"}], // IF・description・IP・VLAN
     "facilities":    [{"id","type":"fdf"|"tie","label","status"}],            // FDF=光配線盤 / TIE=局間タイ回線
     "phys_links":    [{"a_device","a_if","b_device","b_if","via":[facility_id...],"label","status"}], // 物理経路（機器―IF―FDF―TIE―FDF―IF―機器）
     "bgp":           [{"device","local_ip","neighbor_ip","peer_as","local_as","status"}],// BGPネイバー
     "static_routes": [{"device","prefix","next_hop","status"}]               // スタティックルート
   }
   ```
   - **物理（機器・IF・FDF・TIE）と論理（IP・AS・BGP・static・description）を同じモデルに入れる**（描画側で1枚に重畳する）。
   - **対応づけ規則（重要）**: **IPアドレスは IF に帰属させる**（`interfaces[].ip` に入れ、機器に直付けしない）。**BGPは IPで対応づける**: `bgp[].local_ip` に自側IFのIP、`neighbor_ip` に対向IFのIP を入れる（描画側が `neighbor_ip` を対向の `interfaces[].ip` と突合し、エッジを当該IFにアンカーする）。
   - **追加判定**: 投入Config が新設する IF/IP/VLAN/BGPネイバー/static/物理経路に `status:"added"`、手順書・現行Configに既存のものは `status:"existing"`。
   - FDF/TIE は手順書/インプットに記載があれば拾う。**無ければ省略**（無理に作らない）。手順書外の情報が要る部分は描かず `open_questions` に「全体構成は別途構成管理を参照」と残す。
   - **拡張パラメータは `devices[].sections` に入れる（重要・型を増やさない）**: 構成図HTMLは機器ごとにカードを縦に並べ、その機器の IF / BGP / static を表示する。**IF・BGP・static 以外のパラメータ群（OSPF・VRRP/HSRP・ACL/フィルタ・NAT・QoS・VLAN定義・SNMP 等、機器ごとに「名前付きの表」になるもの）は、新しいトップレベルキーを足さず `devices[].sections` に汎用形式で入れる**。これで描画側を変えずに項目を増やせる：
     ```
     sections = [{
       "category": "OSPF",                       // カード内の小見出し
       "columns":  ["area","network","cost"],    // 表のヘッダ
       "rows":     [{"cells":["0","10.0.0.0/24","10"],"status":"added","node":"if-id?","flow":"flow-id?"}]
     }]
     ```
     `cells` は `columns` と同数。`status`（existing/added）で行を色分け。図と連動させたい行は `node`（対応IFのid）や `flow`（対応フローid）を付ける（不要なら省略＝表のみ）。型付きの `interfaces/bgp/static_routes` は描画（IP帰属・対向アンカー・物理経路）を駆動するので**従来どおりトップレベルに置く**。迷ったら「図にエッジとして描きたい＝型付き／表に並べたいだけ＝sections」で振り分ける。
   - 結果を `review-work/topology.json` に保存する。
6. 解釈結果を `review-work/interpreted.json`（`devices` / `parameters` / `config_preview` / 各シートの役割メモ）に、`parameters` 配列のみを `review-work/interpreted-params.json` に保存する（構成図は `topology.json` 側）。

迷う構造（パラメータ表が複数ある、コマンドが複数シートに散る等）は無理に断定せず、判断を `open_questions` に残す。

### Phase 3: パラメータ値検証（機械処理）
Phase 2で特定した `parameters` を値検証ヘルパーに渡す：
```bash
python3 {skillパス}/scripts/validate_values.py review-work/interpreted-params.json -o review-work/validation.json [--reference {インプット情報のパス}]
# --reference に IP一覧/設計値ファイルを渡すと各値を設計値と照合。未指定だと設計値未照合=NG（形式は検証）。
# interpreted-params.json は interpreted.json の parameters 配列のみを書き出したもの
```
`validation.json` の `findings` と `results`（各値の ok/issue、および **`basis`＝何を参照して判定したか**: `形式(型)` / `許容範囲(…・シート宣言)` / `クロスチェック(IP×マスク)` / **`インプット照合: {ファイル名}:{行N}「…」と一致`（OK時は参照ファイル名と行を明記）または `照合元なし/不一致`**）を得る。
**検証の核は「インプット情報（IP一覧/設計値）との照合」**: `--reference` 提供時は各値を設計値と突合し、**一致→OK／不一致→NG（important）**。**`--reference` 未提供 or 該当なし→NG**（`basis` に「照合元なし」、未提供時は per-param NG＋サマリ finding 1件に集約）。形式・許容範囲・IP×マスクも併せて検証する（壊れた値は常に検出）。設計値そのものの妥当性（実機/IPAM との整合）は reference の正しさに依存するため、不明点は `open_questions` に残す。

### Phase 3.5: 現行Config照合（機械処理・バックアップ指定時のみ）
Phase 0 で**作成時バックアップ（現行Config）**のパスが得られた場合のみ実行する。無ければスキップ（後続は影響なし）。
```bash
python3 {skillパス}/scripts/compare_backup.py --backup {現行Configパス} --config review-work/interpreted.json -o review-work/backup_compare.json
# --config は interpreted.json（config_preview を持つ）/ コマンド文字列のJSON配列 / 1行1コマンドのテキスト のいずれでも可
```
スクリプトは「現行Configと突き合わせれば機械的に分かる事実」を出す（意味的判断はレビュアーが上乗せ）：
- **削除対象の実在**: `delete`/`no` の対象が現行に無ければ無効削除/対象誤り（important）。
- **識別子の重複/競合**: 投入する IP・`vlan-id` が現行に既出（重複・別VLAN名との競合の疑い、important）。
- **既存IFの所属VLAN変更**: 投入対象IFが現行で別VLANに収容済み＝アクセスVLAN変更なら**配下端末の通信断**（important）。
- **新規対象IF**: 投入対象IFが現行に無い（新規 or 綴り違い、recommended）。
- **整合度**: 投入Configと現行の用語・採番の一致度（低ければ別機器Config参照の疑い、recommended）。

`backup_compare.json` の `findings` は Phase 5 で統合し、`summary`/`details` はレビュアー（観点14）へ渡す。
**4体のレビューエージェントを同一ターンで並行起動**する（safety / recoverability / operability / security_ops）。各エージェントに渡すもの：手順書本体・`facts.json`・`interpreted.json`・`validation.json`、**（バックアップ指定時）`backup_compare.json` と現行Configのパス**、および**Phase 0で得た情報**（ベンダー/機種、設計値の正解ソース有無、想定版数、重点）。これにより解決後Config・特定済みパラメータ・値検証結果・現行Config照合結果に加え、機種前提や重点を踏まえてレビューできる。雛形と視点定義は `agents/reviewers.md`。バックアップがある場合、**safety レビュアーが観点14（現行Config整合）**を担当し、`backup_compare.json` の機械指摘に意味的解釈（設計意図との整合・端末断の有無）を上乗せする。Phase 0で重点指定があれば該当視点の指摘を厚くする。サブエージェントが使えない環境では4視点を順番にオーケストレータが演じる。

### Phase 5: 統合
1. **関数チェックを findings 化**（`dimension`「関数チェック」、`reviewers`「formula_check」）：
   - `facts.json` の `errors[]` → 関数エラー（#REF!等）。blocker。
   - `facts.json` の `ref_issues[]` → **参照先が空**（`empty_refs`）はコマンド欠損で important、**宛先なし**（`dangling_refs`：使用範囲外/シート不在の参照）はコマンド崩壊で blocker寄りの important。
   - `formula_cells[].ref_details` を見て**誤参照の疑い**を判断する：コマンド生成関数が、値ではなく**名前/ラベル列**を参照している（解決値がヘッダ語や項目名）、明らかに別項目を指している、等。構造解釈に基づく判断なので、確証が持てなければ「要確認」として important〜recommended、または `open_questions` に。
   - パラメータを参照しないハードコード（`refs` が空のコマンド生成セル）→ recommended。
2. `validation.json` の `findings` を取り込む。**`backup_compare.json` があればその `findings`（dimension「14. 現行Config整合（バックアップ照合）」）も取り込み、findings.json に `backup_compared: true` を立てる**（HTMLのチェック観点に観点14が出る）。
3. 4視点の指摘をマージ。**同一箇所×同種**は1件に統合し `reviewers` に全視点を列挙、重大度は最大を採用。`id` を F1.. で振り直す。
4. **各指摘に所属シートを付ける。** `location` が `シート!セル` 形式ならHTML側が自動でシート振り分けするが、`全体` 等で曖昧な指摘や横断的な指摘には明示的に `sheet` を付ける（横断指摘は `sheet:"全体・横断"`）。改版履歴の指摘は `sheet:"改版履歴"`（実シート名）に。
5. `interpreted.json` の `parameters`・`config_preview` を findings.json に持ち込む（`parameters` の各要素に validation.json の ok/issue を `valid`/`note`、**`basis`（検証根拠）**として付与）。`config_preview` の各行は `refs` を保持。構成図は findings.json に持ち込まず別ファイル化するため、`topology.json` を生成していれば findings.json に **`topology_html: "topology.html"`** を立てる（レポートが構成図HTMLへリンクする）。
6. `sheets_order` に `facts.json` の `sheet_names` を入れる（HTMLのシート表示順がブックの並びに揃う）。
7. **参考情報を算出**：
   - `unused_params`：`parameters` のうち `filled` かつ `cell` が `facts.json` の `referenced_cells` に**含まれない**もの（記入済みだがどの関数からも参照されていない＝参照漏れ/不要記入の兆候）。
   - 「作業の投入Config」は `config_preview` からHTML側が自動生成するため、ここでの算出は不要。
8. **承認者向け情報を作成**：
   - `work_types`：この作業のタイプを下記の語彙から該当するものを選ぶ（複数可）。コマンド・パラメータの内容から判断する。該当が無ければ近い語を補ってよい。
     `物理接続` / `物理切断・撤去` / `バージョンアップ` / `切り離し` / `トラヒック迂回` / `切り替え` / `トラヒック流し` / `設定変更` / `増設` / `試験・疎通確認` / `パラメータ変更`
     （判断例: deactivate/disable interface→切り離し、request system software add→バージョンアップ、経路変更→トラヒック迂回/切り替え、再有効化→トラヒック流し、ケーブル/IF新設→物理接続）
   - `approver_summary`：**作業承認者が技術詳細を読まずに承認判断できる**平易な説明。`what`(何をする) / `purpose`(目的・背景) / `targets`(対象機器・範囲。**複数台なら全機器を列挙**) / `impact`(影響・断時間・対象通信) / `rollback`(切り戻し可否) を埋める。専門用語は避け、影響と可否が一読で分かるように。
9. `verdict` と `overall` を決める（Blockerが1件でもあれば「実施非推奨」または「修正後可」）。`good_points`・`open_questions` を集約。

結果を `review-work/findings.json` に下記スキーマで書き出す。

### Phase 6: HTML生成と提示
```bash
python3 {skillパス}/scripts/render_report.py   review-work/findings.json -o review-work/report.html
# topology.json を生成していれば、構成図HTML（別ファイル）も生成する
python3 {skillパス}/scripts/render_topology.py review-work/topology.json -o review-work/topology.html
```
`render_report.py`: 重大度順ソート・色分け・パラメータ検証表・印刷対応に加え、**冒頭に「確認が必要な事項（作業前サマリ）」**、作業承認者向け説明の直下に **「チェック観点」パネル**（観点14はバックアップ照合時のみ）、参考情報に **「作業の投入Config」（実機の設定コマンドのみ）・構成図(topology.html)へのリンク・未参照パラメータ** を自動描画する。
`render_topology.py`: `topology.json` から描画データへ変換し、**インタラクティブな単体HTML＋JS**（`topology.flows.json` も併出力。HTMLは fetch→失敗時は埋め込みJSONにフォールバックし `file://` でも動く）を生成する。上段に物理（機器・IF・FDF・TIE）＋論理（IP・AS・BGP・static）を1枚に重ねたSVG図、**下段に機器ごとのカードを縦積み**で並べ、各カードにその機器の IF / BGP / static ／ `devices[].sections` の拡張項目を表示する（表の行クリックで図へ移動、フロー選択で表もマーク連動）。**フロー（物理経路・eBGP往復・static）選択で5層フォーカス**、**作業で追加となる要素（status:"added"）を緑・太線**で強調する（IPはIFに帰属、BGPは neighbor_ip→対向IFにアンカー）。
HTMLは手書きしない。

### Phase 6.5: HTML突合クロスレビュー（成果物提示の最終関門）
生成した `report.html` / `topology.html` を**元データと突合する専任サブエージェント（cross-reviewer）を1体起動**する。レビュー内容の良し悪しではなく、**「描画が元データと食い違っていないか」だけ**を敵対的に突合する（欠落・件数不一致・status:added の取り違え・リンク切れ・転記ミス・投入Config行の混入/欠落・BGPアンカー誤り）。topology.html はJSが実行時にDOM生成するため、突合対象は埋め込み `<script id="workflow-data">` の JSON（`tables`/`flows`/`nodes`）と `topology.flows.json`。指示と項目は `agents/cross-reviewer.md`。
結果は `review-work/cross_review.json`。**blocker/important の不一致が残ったまま成果物を提示しない**——`findings.json`/`topology.json` を修正、または `render_report.py`/`render_topology.py` を再実行して潰してから提示する。サブエージェントが使えない環境ではオーケストレータが同じ突合を自分で行う。

最終提示: `report.html` と `topology.html` のパスを伝え、開ける環境なら開く。チャットには総評・件数・Blocker/重要・関数エラー有無を要約し、詳細はHTMLに委ねる。

## findings.json スキーマ

```json
{
  "target": "手順書名（ファイル名）",
  "verdict": "実施可 | 修正後可 | 実施非推奨",
  "overall": "総評（2〜3文）",
  "work_types": ["設定変更","切り替え","トラヒック迂回"],
  "approver_summary": {"what","purpose","targets","impact","rollback"},
  "sheets_order": ["改版履歴","パラメータ","STEP1","STEP2"],
  "backup_compared": true,
  "findings": [
    {"id":"F1","severity":"blocker|important|recommended|minor",
     "sheet":"STEP2",
     "dimension":"関数チェック | 11. 関数・パラメータ整合 | 13. 改版履歴 | 4. 切り戻し | 14. 現行Config整合（バックアップ照合） ...",
     "location":"STEP2!C4","problem":"当日に何が起きうるか","suggestion":"理由付きの改善案",
     "reviewers":["formula_check","value_check","safety","backup_check"]}
  ],
  "parameters":     [{"name","cell","value","filled","type","constraint","valid","note","basis"}],
  "config_preview": [{"sheet","lines":[{"step","action","location","command","parameterized","refs","device"}]}],
  "unused_params":  [{"name","cell","value"}],
  "topology_html": "topology.html",
  "good_points": ["..."],
  "open_questions": ["..."]
}
```
`severity` は英語キー固定。`sheet` 省略時は `location` の `!` 前から推定、それも無ければ「全体・横断」に分類。`work_types`/`approver_summary`/`sheets_order`/`backup_compared`/`parameters`/`config_preview`/`refs`/`unused_params`/`topology_html` はいずれも省略可。HTMLでは**冒頭に `open_questions`（確認が必要な事項＝作業前サマリ）**、続いて `work_types`（作業タイプのチップ）・`approver_summary`（作業承認者向け説明）、その直下に **「チェック観点」パネル**（`findings` の `dimension` から確認観点と指摘件数を自動集計。`backup_compared` が真なら観点14も表示）、`config_preview` から「作業の投入Config」（**実機の設定コマンドのみ**を表示。commit/save・show・接続/ログイン手順・地の文は自動除外）、`unused_params` から「参照されていない記入済みパラメータ」、`topology_html` があれば**構成図（`topology.html`）へのリンク**を描画する。構成図そのものは `topology.json` を `render_topology.py` で別HTML化する（物理＋論理を1枚・追加要素を色分け）。

## 出力時の注意
- 引用は短く。シート!セルや手順番号で指す。
- 改善案は理由付きで。手順書は作成者の労作であり、レビューは品質を上げる協働作業。
- ベンダー構文の正否・自社固有ルール（命名規則・承認フロー・メンテ枠運用）・設計上の正解値は断定せず `open_questions` に回す。
- 構造解釈に自信が持てない部分は推測で断定せず、`open_questions` に「この表をパラメータと解釈したが要確認」等を残す。
