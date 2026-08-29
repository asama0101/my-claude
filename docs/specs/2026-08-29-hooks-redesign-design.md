# hooks 再設計 設計書

- 作成日: 2026-08-29
- 対象: `~/.claude/hooks/` 配下の PreToolUse フック群（`bash-guard.sh` / `workspace-guard.sh` / `main-branch-guard.sh` / `venv-guard.sh`）

## 背景

既存4フックは個別の追加改修（main-branch-guard.shへのバイパス機構追加等）を重ねてきた結果、責務境界が読み解きにくくなっていた。具体的には以下の粗があった。

- `bash-guard.sh` と `workspace-guard.sh` が `normalize()`（難読化正規化）を意図的に重複して持つ
- `workspace-guard.sh` 内でゾーン範囲が非対称（Write系は`/tmp/claude-*/`限定、rm系は`/tmp/*`全体許可）
- `workspace-guard.sh` と `main-branch-guard.sh` が「`$CLAUDE_HOME`自己防御なし」という穴を共有
- `venv-guard.sh` にテストが無い

これを機に、hooksを削除し1から再設計する。

## 要件

1. main/masterブランチ上でのファイル操作を禁止する。ただしブランチを作成できない環境（`.git`書込み権限なし）では警告のみで許容する
2. システムを破壊する行為・システムパッケージのアップデート/インストールを禁止する
3. Pythonライブラリインストール時はvenvを強制し、グローバルインストールは例外なく禁止する
4. hooksでなくsettings.jsonのpermissions機構で代替できる部分があれば、そちらへ移す
5. 既存4フックは削除し、1から作り直す

## settings.json permissionsへの移管検討（要件4の結論）

Claude Code公式ドキュメント（`code.claude.com/docs/en/permissions`）を調査した結果、4フックが行う判定はいずれも「実行時の動的状態取得」（プロセス環境・gitブランチ・ファイルシステム実解決）を必要とし、permissionsの静的パターンマッチ（Bashはコマンド文字列へのglob一致、Read/Editはgitignore形式のパスパターン）だけでは代替できないと判明した。

| 対象 | 判定 | 理由 |
|---|---|---|
| venv強制 | 不可能 | `VIRTUAL_ENV`等の実行時環境状態を参照する仕組みがpermissionsに無い |
| システム破壊コマンド判定 | 部分的 | コマンド丸ごとdenyは可能。だが引数内容（`dd`の`of=/dev/*`等）を条件にした精密な分岐は不可（公式docも「fragile」と明記） |
| ブランチ分岐 | 不可能 | gitを実行して動的状態（現在ブランチ名）を取得する仕組みが無い |
| ゾーン判定（realpath解決） | 部分的 | Write/Edit系は`additionalDirectories`機構でかなり近似可能。だがBashコマンド内の任意パス引数のrealpath解決は不可 |

**結論**: 4フックとも全面的なsettings.json移管は不可能。全てhooksのまま実装する。

## 新構成: 4フック（責務軸を直交させる）

| フック | 責務軸 | 位置づけ |
|---|---|---|
| `workspace-guard.sh` | 場所（どこを触るか） | 既存から大幅縮小 |
| `branch-guard.sh` | Gitブランチ状態 | 旧`main-branch-guard.sh`をフロー刷新して置換 |
| `system-guard.sh` | コマンドの絶対破壊性（場所を問わない） | 旧`bash-guard.sh`を拡張して置換 |
| `venv-guard.sh` | Python環境 | 実装は現状維持、テストを新設 |

### workspace-guard.sh（縮小）

- 対象: `Write` / `Edit` / `MultiEdit` / `NotebookEdit` の書込み先チェックのみ
- 許可ゾーン: プロジェクト配下／`$CLAUDE_HOME`配下／`/tmp/claude-*/`配下（既存の`is_allowed()`ロジックを踏襲）
- **Bash側のゾーン判定（`rm`/`git rm`/`find -delete`/`rsync --delete`/`chmod 000`・`chmod -R 777`/`git clean -fd`/機密ファイル読取の7カテゴリ）は全廃**
  - 廃止に伴うリスク: Bash経由でのプロジェクト外操作のうち、以下が無制限になる: (a) 任意ファイルの削除(`rm`等) (b) 機密ファイルの読取(`cat`/`less`/`head`等での`.env`/`.ssh`鍵/認証情報の閲覧) (c) 任意ファイルへの書込み(リダイレクト/`cp`/`tee`/`mv`/`curl -o`、`~/.bashrc`等のシェル設定ファイル改変を含む)。`chmod 000`/`chmod -R 777 /`・`git clean -fd`(パス無し)は場所非依存の絶対破壊としてsystem-guard.shへ復元済み(2026-08-29最終レビュー対応)
  - 代替の決定的防御は無い（後述の「検討して却下した代替案」参照）。**このリスクを承知の上で許容する、というユーザー判断による決定**
- 副次効果: Bashコマンド文字列を扱わなくなるため、難読化正規化(`normalize()`)が不要になり実装が大幅に単純化する
- 既知の限界（新設計にも残る、Critical ではない）:
  - `$CLAUDE_HOME`や`PROJECT_DIR`自体がシンボリックリンク経由で構成されている場合、論理パスと`realpath -m`の物理パス解決が食い違い、正当な書込みが誤ブロックされうる（fail-closed方向。このリポジトリの`~/.claude`はコピー同期方式のため非該当）
  - jqが存在してもINPUTが不正JSONの場合は`TOOL`が空文字になり素通しでexit 0になる（ヘッダコメントの「jq不在時fail-close」という保証はjq自体の不在のみをカバーしており、実装との整合性がやや取れていない。単独ロジックとして残す際はコメントを実装に合わせて補正する）

### branch-guard.sh（旧main-branch-guard.sh、フロー刷新）

状態ごとの挙動を以下の決定表で定義する。

| # | 状態 | 判定方法 | 挙動 |
|---|---|---|---|
| 1 | gitコマンド自体が無い | `command -v git`失敗 | 何もしない（fail-open。変更操作自体が実行不能なため実害限定） |
| 2 | gitはあるがこのディレクトリはリポジトリでない | `git rev-parse --is-inside-work-tree`失敗 | 無条件許可 |
| 3 | detached HEAD | `symbolic-ref -q HEAD`失敗 | 無条件許可（どのブランチにも属さないコミットになるだけで、mainブランチの内容を直接書き換えるわけではないため実害は限定的） |
| 4 | main/master・かつ`.git`へ書込み権限あり | `is_protected` && `.git`書込み可能 | ブロック（`git checkout -b`を促す） |
| 5 | main/master・かつ`.git`へ書込み権限なし | `is_protected` && `.git`書込み不可能 | 警告のみで許容（**自動検知**。`.git`ディレクトリへの書込み権限テストで判定し、ユーザー操作は不要） |
| 6 | main/master以外の通常ブランチ | `!is_protected` | 無条件許可 |

- **前回実装した`CLAUDE_MAIN_BRANCH_GUARD_BYPASS`環境変数によるバイパス機構は廃止する**。理由: セキュリティレビューで指摘されたCRITICAL（設定ファイル/シェルRC経由の間接的自己バイパス経路）の温床になっていた。自動検知に置き換えることでこの経路自体が構造的に無くなる
- 権限不足による警告許容が発火した場合は、既存同様`$CLAUDE_HOME`配下の監査ログへ記録する（実装詳細は実装計画フェーズで決定）
- 既存の`warn_if_stale()`（ローカルbranchがorigin/branchより遅れている場合の警告）、`bash_targets_outside_project()`（Bashコマンドの全対象パスがプロジェクト外かつ`$CLAUDE_HOME`外の場合のみブランチ保護を免除）は踏襲する

### system-guard.sh（旧bash-guard.sh、拡張）

- 既存カテゴリを維持: ディスク・デバイス破壊／パーミッション破壊／プロセス・システム停止／危険なリモート実行（`curl|bash`等）／システムファイル破壊／DB破壊／グローバルパッケージ導入・削除／ファイル内容消去／スケジューラ破壊
- **新規追加**: システムパッケージマネージャのupdate/upgrade（`apt update`/`apt upgrade`/`apt dist-upgrade`、`brew upgrade`、`yum update`、`dnf upgrade`等）を無条件ブロック対象に追加
  - 対象パッケージマネージャの具体的な列挙・正規表現パターンは実装計画フェーズで確定する

### venv-guard.sh（現状維持）

- 判定ロジック（`VIRTUAL_ENV`環境変数ベースの文字列一致）は変更しない
- 「例外は認めない」の方針: 誤検知が起きても機械的に常時ブロックする。検知精度を上げるための追加実装コストは払わない（判定ロジックの厳密化は見送り）
- 新設: テストファイルを新設する（現状テスト無し）

## 検討して却下した代替案

- **workspace-guard.shのBash側ゾーン判定（rm等のプロジェクト外宛先チェック）を`system-guard.sh`側に統合する案**: 却下。「場所（ゾーン）」と「コマンドの絶対破壊性」という異なる軸を1つのフックに混在させることになり、責務分離の原則に反するため、統合せず単純に廃止する方を選んだ
- **Bashサンドボックス（bubblewrap/socat導入 + `sandbox.enabled: true`）でBash側ゾーン判定を代替する案**: 却下。今回のスコープ（hooks再設計）を超えた別途の環境構築作業になるため、今回は見送り
- **branch-guardのバイパスに環境変数と自動検知を併用する案**: 却下。環境変数を残す限りCRITICALリスクが残るため、自動検知のみに一本化

## 移行方針

- 既存4スクリプト（`bash-guard.sh` / `workspace-guard.sh` / `main-branch-guard.sh` / `venv-guard.sh`）と対応テスト（`bash-guard.test.sh` / `workspace-guard.test.sh` / `main-branch-guard.test.sh`）は削除し、新4スクリプト（`workspace-guard.sh` / `branch-guard.sh` / `system-guard.sh` / `venv-guard.sh`）と対応テスト（`venv-guard.test.sh`を新設含む）に置き換える
- `~/.claude/settings.json`の`hooks`配列・`~/.claude/rules/hooks.md`（正典ドキュメント）も新構成に合わせて更新する
- 実装は`~/.claude/`側で行い、完了後`sync-config`スキルで本リポジトリ（`linux/claude/`）へ反映する

## テスト方針

- 各フックにシェルスクリプトテスト（既存の`*.test.sh`形式を踏襲）を用意する
- `branch-guard.sh`は決定表の6状態すべてを網羅する
- `venv-guard.sh`は新設（VIRTUAL_ENV有無×pip install/uninstall/uv add等の組み合わせを網羅）
