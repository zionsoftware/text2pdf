# text2pdf

RHEL 9 上で、日本語を含むテキストファイルを A4 の PDF に変換するコマンドラインツールです。本文・ヘッダー・フッターは IPA ゴシックで描画し、フォントを PDF に埋め込みます。

## できること

- 1up（A4 縦、1 段）と 2up（A4 横、左右 2 段）
- ヘッダー（ファイル名、変換日時、ユーザー名）とフッター（絶対パス、ページ番号）
- フォントサイズの指定（large / medium / small）
- 段幅を超える行の自動折り返し
- 入力文字コードの指定（`euc_jis_2004` / `euc_jp` / `utf-8`）
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

既定の文字コードは `euc_jis_2004` です。丸数字（①②③）など、Python の `euc_jp` では読めない JIS X 0213 の文字を扱えます。

`--encoding` で次のいずれかを指定できます。ハイフン表記（`euc-jp`、`euc-jis-2004`、`utf8`）も受け付けます。

| 指定 | 内容 |
| --- | --- |
| `euc_jis_2004` | 既定。EUC-JIS-2004 |
| `euc_jp` | EUC-JP（JIS X 0208） |
| `utf-8` | UTF-8 |

文字コードの自動判定は行いません。デコードに失敗すると、ファイル名、バイト位置、行番号、理由を表示して終了コード 1 で止まります。未対応の文字コード名は終了コード 2 です。

```bash
./text2pdf input.txt output.pdf --encoding euc_jis_2004
./text2pdf input.txt output.pdf --encoding utf-8
./text2pdf input.txt output.pdf --encoding euc-jp
```

## TAB

TAB 文字は PDF に描きません。IPA ゴシックの ASCII 空白の幅を 1 桁とし、現在の描画位置から次のタブストップまで進めます。全角文字は ASCII 2 桁分の幅として数えるため、日本語と英数字が混在しても桁が揃います。

既定の TAB 幅は 8 桁です。`--tab-size` で変更できます。

```bash
./text2pdf input.txt output.pdf --tab-size 4
```

## 使い方

```bash
# 既定: 2up、medium（10pt）、EUC-JIS-2004、TAB 幅 8
./text2pdf input.txt output.pdf

# 出力ファイルを省略すると、入力と同じ名前の .pdf を作ります
./text2pdf input.txt

# 1up（A4 縦、1 段）
./text2pdf input.txt output.pdf --layout 1up

# 2up（A4 横、左右 2 段）
./text2pdf input.txt output.pdf --layout 2up

# フォントサイズ（large=11pt、medium=10pt、small=8pt）
./text2pdf input.txt output.pdf --font-size small
```

サンプル:

```bash
./text2pdf samples/english_sample.txt samples/generated/english_2up.pdf
./text2pdf samples/english_sample.txt samples/generated/english_1up.pdf --layout 1up
./text2pdf samples/program_sample.py samples/generated/program_2up.pdf --encoding utf-8
./text2pdf samples/mixed_euc_jis_2004.txt samples/generated/mixed_2up.pdf
./text2pdf samples/mixed_euc_jis_2004.txt samples/generated/mixed_1up.pdf --layout 1up
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
