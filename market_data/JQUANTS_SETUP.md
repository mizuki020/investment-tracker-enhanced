# J-Quants API V2 日足取得アダプター（開発版）

## 対象と制約

- 対象：東証上場株の日足OHLCV。初期銘柄は9983。
- 公式仕様： https://jpx-jquants.com/ja/spec/eq-bars-daily
- API：`GET https://api.jquants.com/v2/equities/bars/daily`
- 認証：環境変数 `JQUANTS_API_KEY` を `x-api-key` ヘッダーに付ける。キーをGitHubやチャットに貼らない。
- 本実装は**未接続**。実APIキーによるライブ疎通はまだ実施していない。
- J-Quants Freeの株価は約12週間遅延。無料プランでは当日判断不可。
- 取得したデータの第三者配布・継続提供には利用規約上の制約がある。

## 実行方法

J-Quantsの管理画面でAPIキーを発行した後、**手元の安全な実行環境**で環境変数を設定します。

```bash
# APIキーの実値をソースコードや履歴に記録しない
export JQUANTS_API_KEY='（ここで取得したキーを安全に設定）'
python -m market_data.jquants_v2 \
  --code 9983 \
  --from-date 2026-01-01 \
  --to-date 2026-10-30 \
  --as-of 2026-10-30 \
  --snapshot ./private-data/9983-20261030-raw.json \
  --analysis-output ./private-data/9983-20261030-analysis.json
```

`private-data/` はGitの追跡対象に追加しないこと。
取得結果には元データの再配布制限があるため、外部公開しない。

## 動作

1. コード・取得期間・基準日を検証し、未来日のデータを要求しない。
2. API V2からページネーションで取得し、429/5xxの一時的失敗に限定して再試行。
3. 取得銘柄・重複日・数値の整合性を検証。無約定等のnull四本値は推定せず除外。
4. 調整前のOHLCVを日付順に並べる。
5. APIレスポンス由来の値とメタデータをJSONスナップショットに保存（既存ファイル上書き禁止）。
6. 既存の移動平均線・RSI・MACD・ボリンジャーバンド計算に接続。
7. 発注APIには接続しない。

## 残課題

- 実APIへの接続確認（ユーザーがキーを設定した環境で実施）
- 欠損値・株式分割等の長期的な整合性検証
- 出来高と調整済み価格の整合、テクニカル指標の外部値照合
- 過去の情報公開時刻を含む、厳密なpoint-in-time検証
- 取得データの保管・暗号化・削除ポリシー
- 現行のFreeプランでは短期トレード向けの鮮度を満たさないため、リアルタイム性が必要な場合は別データ経路を検討

## オフライン試験

```bash
python -m unittest discover -s tests -p 'test_jquants_v2.py' -v
python -m unittest discover -s tests -p 'test_market_data_indicators.py' -v
```
