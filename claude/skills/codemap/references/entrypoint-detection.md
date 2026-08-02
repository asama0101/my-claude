# エントリポイント検出（言語別の規約）

SKILL.md の「3. フローを特定する」から参照する。対象コードベースの言語を先に判定し（拡張子・
プロジェクトのビルド設定ファイルで分かる）、該当する言語の項目を `grep -rn` 等で機械的に洗い出す。
複数言語が混在するリポジトリ（例: フロントエンド+バックエンド）では、両方の項目を確認する。

## Python

- `if __name__ == "__main__"` / `def main(` を `grep -rn` で検索
- `pyproject.toml`/`setup.py`/`setup.cfg` の `console_scripts`・`[project.scripts]`
- ライブラリなら公開 API（`__init__.py` の `__all__`、ドキュメント記載の関数）

## JavaScript / TypeScript（Node.js）

- `package.json` の `bin` フィールド（CLI エントリ）・`scripts` フィールド（`npm run <name>` で
  起動するコマンド）・`main`/`exports` フィールド（ライブラリの公開エントリ）
- フレームワーク固有の規約（例: Next.js の `pages/`/`app/` 配下、Express の `app.listen(...)` を
  呼ぶファイル）
- ライブラリなら `index.ts`/`index.js` の re-export、または `package.json` の `types`/`exports`
  が指す公開 API

## Go

- `func main()` を持つ `package main` のファイルを `grep -rln 'func main'` で検索
- `go.mod` があるディレクトリ配下で、`package main` を宣言しているサブディレクトリ（各々が
  独立したビルド対象＝1バイナリ）
- ライブラリなら公開関数（大文字開始のエクスポートされた関数・型）

## Rust

- `fn main()` を持つファイル（`src/main.rs` が既定、`src/bin/*.rs` は追加バイナリ）
- `Cargo.toml` の `[[bin]]` セクション（バイナリ名とパスの明示指定）
- ライブラリ（`src/lib.rs`）なら `pub fn`/`pub struct` 等の公開 API

## Java / Kotlin

- `public static void main(String[] args)`（Java）/ `fun main(...)`（Kotlin）を持つクラス
- `pom.xml`（Maven）の `mainClass` 指定、`build.gradle`（Gradle）の `mainClassName`/
  `application { mainClass }` 指定
- ライブラリなら公開 API（`public` クラス・メソッド）

## C# / .NET

- `static void Main(string[] args)` を持つクラス
- `.csproj` の `<OutputType>Exe</OutputType>` を持つプロジェクト
- ASP.NET 等のフレームワークでは `Program.cs`/`Startup.cs`

## 言語共通の探索先

- README・運用手順書（docs/ 配下）に書かれた起動コマンド（`npm run`・`python -m`・
  `./bin/xxx` 等の実行例）
- cron・systemd のユニット定義・タスクスケジューラ設定に書かれた起動コマンド
- コンテナ定義（`Dockerfile` の `CMD`/`ENTRYPOINT`、`docker-compose.yml` の `command`）
- CI/CD 定義（GitHub Actions 等）に書かれた実行コマンド（デプロイ対象の実体を示すことがある）

見つけたエントリポイント候補は、SKILL.md の指示通り「フロー候補一覧」としてユーザーに提示し、
どれをページ化するか確認を取ってから次に進む（この文書は候補の洗い出し方法の正典であり、
確認プロセス自体は SKILL.md 側の役割）。
