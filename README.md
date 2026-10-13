# text2pdf

RHEL 9 上で、日本語を含むテキストファイルを A4 の PDF に変換するコマンドラインツールです。本文・ヘッダー・フッターは IPA ゴシックで描画し、フォントを PDF に埋め込みます。

## できること

- 1up（A4 縦、1 段）と 2up（A4 横、左右 2 段）
- ヘッダー（ファイル名、変換日時、ユーザー名）とフッター（絶対パス、ページ番号）
- フォントサイズの指定（large / medium / small、または 6〜16pt）
- 段幅を超える行の自動折り返し
- 入力文字コードの自動判別（`euc_jis_2004` / `utf-8` / `cp932`）と明示指定
- フォントの描画幅に基づく TAB 展開

## セットアップ（RHEL 9）

システムの Python は 3.9 です。仮想環境を作って依存パッケージを入れます。

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

テストを実行する場合は、開発用の依存関係も入れます。

```bash
pip install -r requirements-dev.txt
```

## IPA ゴシック

このリポジトリにはフォントファイルを含めていません。IPA フォントは [IPA Font License](https://moji.or.jp/ipafont/license/) で配布されています。入手先は [IPA フォントのダウンロードページ](https://moji.or.jp/ipafont/ipafontdownload/) です。

`ipag.ttf` を次の場所に置いてください。これが `--font-path` を省略したときの既定パスです。

```bash
mkdir -p ~/.local/share/fonts
cp ipag.ttf ~/.local/share/fonts/ipag.ttf
fc-cache -f
```

別の TrueType フォントを使うときは `--font-path` でファイルを指定します。ファイルが無い場合はエラーになり、終了コードは 1 です。

```bash
./text2pdf input.txt output.pdf --font-path /path/to/font.ttf
```

## 文字コード

`--encoding` の既定は `auto` です。入力ファイルは一度だけバイナリで読み、次の順で判別します。外部の文字コード判定ライブラリは使いません。

1. 先頭が UTF-8 BOM（EF BB BF）なら UTF-8 として扱います。BOM は本文に含めません。BOM のうしろが UTF-8 として不正なら、別の文字コードへ切り替えずエラーにします。
2. ASCII だけのデータ（空ファイルを含む）は UTF-8 にします。
3. それ以外は `euc_jis_2004`、`utf-8`、`cp932` の順に、ファイル全体を厳密にデコードできるか調べます。`errors="replace"` や `errors="ignore"` は使いません。

採用する文字コードは次の規則です。優先順位は `euc_jis_2004`、`utf-8`、`cp932` です。EUC 系の業務テキストを主な対象にしているためです。

- 成功した文字コードが 1 つなら、それを使います。
- 複数成功し、デコード後の文字列が同じなら、優先順位の高いものを使います。警告は出しません。
- 複数成功し、デコード後の文字列が異なるなら、優先順位の高いものを使い、標準エラーへ警告を出します。変換は続行し、終了コードは 0 のままです。
- すべて失敗したら終了コード 1 で止まります。

通常の EUC-JP は Python の `euc_jis_2004` で読めるため、auto の候補に `euc_jp` は入れていません。`--encoding euc_jp` を明示したときは、これまでどおり EUC-JP として厳密にデコードします。

自動判別は完全ではありません。デコードに成功しても、その文字コードが正しいとは限りません。UTF-8 や CP932 のファイルが `euc_jis_2004` として読めてしまい、別の文字列になることがあります。たとえば CP932 の「髙」（バイト列 EE E0）は `euc_jis_2004` でもデコードでき、優先順位により「釵」になります。EUC-JP の「あいう」は CP932 の半角カナとしても解釈できるため、警告を出したうえで `euc_jis_2004` を採用します。文字コードが分かっているときは `--encoding` で指定してください。

auto で採用した文字コードは標準出力に表示します。

```text
Detected encoding: euc_jis_2004
Successfully created report.pdf
```

結果が分かれるときは、たとえば次の警告を標準エラーに出します。

```text
Warning: Ambiguous encoding detected.
Selected: euc_jis_2004
Other possible encodings: utf-8, cp932
Use --encoding to specify the correct encoding.
```

明示できる名前は次のとおりです。ハイフンやアンダースコアの表記（`euc-jp`、`euc-jis-2004`、`utf8`、`cp_932`）も受け付けます。`shift_jis` は受け付けません。Windows の拡張文字を明示するときは `cp932` を使います。

| 指定 | 内容 |
| --- | --- |
| `auto` | 既定。上記の自動判別 |
| `euc_jis_2004` | EUC-JIS-2004。丸数字（①②③）など JIS X 0213 の文字を扱える |
| `euc_jp` | EUC-JP（JIS X 0208）。明示したときだけ使う |
| `utf-8` | UTF-8 |
| `cp932` | Windows Shift_JIS（CP932） |

手動で指定したときは自動判別を行わず、その文字コードで厳密にデコードします。失敗すると、ファイル名、バイト位置、行番号、理由を表示して終了コード 1 で止まります。未対応の文字コード名は終了コード 2 です。

```bash
./text2pdf input.txt --encoding auto
./text2pdf input.txt --encoding euc_jp
./text2pdf input.txt --encoding euc_jis_2004
./text2pdf input.txt --encoding utf-8
./text2pdf input.txt --encoding cp932
```

## PDF の出力先

出力ファイル名を省略すると、入力ファイルと同じディレクトリに、拡張子を `.pdf` へ変えたファイルを作ります。拡張子がないファイルには `.pdf` を足します。

```bash
./text2pdf /home/user/docs/report.txt
# /home/user/docs/report.pdf

./text2pdf ./samples/example.dat
# ./samples/example.pdf
```

出力ファイルを指定したときは、そのパスを優先します。

```bash
./text2pdf /home/user/docs/report.txt ./report.pdf
```

入力と出力が同じパスになるときは、入力を壊さないようにエラーにして終了コード 1 で止まります。別ファイルの既存 PDF は上書きします。変換に失敗したときは一時ファイルだけを捨て、既存の PDF は残します。成功したときは、作った PDF のパスを表示します。

## TAB

TAB 文字は PDF に描きません。IPA ゴシックの ASCII 空白の幅を 1 桁とし、現在の描画位置から次のタブストップまで進めます。全角文字は ASCII 2 桁分の幅として数えるため、日本語と英数字が混在しても桁が揃います。

既定の TAB 幅は 8 桁です。`--tab-size` で変更できます。

```bash
./text2pdf input.txt output.pdf --tab-size 4
```

## 使い方

```bash
# 既定: 2up、medium（10pt）、文字コード自動判別、TAB 幅 8
./text2pdf input.txt

# 1up（A4 縦、1 段）
./text2pdf input.txt --layout 1up

# 2up（A4 横、左右 2 段）
./text2pdf input.txt output.pdf --layout 2up

# フォントサイズ。large=11pt、medium=10pt、small=8pt。
# 6 から 16 の整数は本文だけに効く。ヘッダーとフッターのサイズは変わらない。
./text2pdf input.txt --font-size small
./text2pdf input.txt --font-size 6
./text2pdf input.txt --font-size 9
./text2pdf input.txt --font-size 12
./text2pdf input.txt --font-size 16
```

サンプル:

```bash
./text2pdf samples/english_sample.txt samples/generated/english_2up.pdf
./text2pdf samples/english_sample.txt samples/generated/english_1up.pdf --layout 1up
./text2pdf samples/program_sample.py samples/generated/program_2up.pdf
./text2pdf samples/mixed_euc_jis_2004.txt samples/generated/mixed_2up.pdf
./text2pdf samples/mixed_euc_jis_2004.txt samples/generated/mixed_1up.pdf --layout 1up
./text2pdf samples/english_sample.txt samples/generated/english_12pt.pdf --font-size 12
```

`samples/mixed_euc_jis_2004.txt` は EUC-JIS-2004 で、日本語、英数字、全角英数字、丸数字、TAB を含みます。

入力ファイルが無い、フォントが無い、出力先に書けない、文字コードが不正、のいずれも終了コードは 0 以外です。PDF は一時ファイルへ書き、成功したときだけ出力先へ置き換えます。

## テスト

```bash
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest
```

## 要件

- Python 3.9（RHEL 9 のシステム Python）
- reportlab
- IPA ゴシック（`~/.local/share/fonts/ipag.ttf`）
