# Holy Grail first pullback 品質監査

- 実験ID / 担当 / 次担当: `holy_grail_first_pullback_20260913` / quant_auditor / 研究責任者。
- 状態: `AUDITED_REJECTED_TRAINING_ONLY`。凍結モデルの学習不採用を報告する範囲で引渡し可。独立検証担当の最終報告との統合は責任者が行う。
- 監査日: 2026-09-13 JST。
- 入力: 同実験の hypothesis.md、protocol.json、data_inventory.md、scripts/research_holy_grail_first_pullback.py、tests/test_holy_grail_first_pullback.py、依存集計関数、agent_runs/holy_grail_first_pullback_20260913/completed、同agent_runs直下research_handoff.md。
- 変更したファイル: この audit.md のみ。戦略・仕様・結果・原履歴を変更していない。
- 実注文: なし。

## 引渡し判定

実装と保存結果から、不採用結論を妨げる重大な不整合は発見していない。採用候補はH1/H4の2件とも両コストで事前基準不通過、selectedは空。validation/final_confirmationへの移行およびPine移植は不要であり、実施しない判断がcharterの工程に適合する。

今回の否定範囲は11通貨の2010–2018年に対する、RR1・ADX episode・3観測足の注文期限・保守的OHLC約定を固定した機械化モデル。書籍の裁量手法全体の無効性を意味しない。研究合格、PINE_CREATED、TV_VERIFIED、実運用承認のいずれにも該当しない。

## 所見

|ID|重大度|根拠・影響・扱い|
|---|---|---|
|A01|Low|research_handoff.md:8の完成時刻「2026-09-13T08:49:43 UTC」はタイムゾーン誤記。results.jsonの実値は `2026-09-12T23:49:43.390419+00:00`、JSTでは9/13 08:49:43。数値結果への影響なし。引渡しではJSONを正とする。|
|A02|Low|hypothesis.md:15にはATR14をindex13で初期化する説明があるが、今回のindicatorsは独立ATRを生成・使用しない。ADXのTR/DMは同段落後半どおりindex14、ADXはindex27で初期化する。売買・SL・コストにATR参照はなく数値影響なし。凍結文書は維持し、本注記を補足として扱う。|
|A03|Medium / disclosed limitation|H1/H4の足内順序を原M1/tickで解決せず、entry-barを含めSL先とする。保存16,644明細中both_stop_firstは386件（二コスト重複を含む）。仕様どおりで先読みは見つからないが、実約定順序や精密な原手法成績を主張できない。|
|A04|Medium / disclosed limitation|11通貨のBid根拠は疎なtickサンプル、時刻帯・実spread/slippage/swap・口座換算は未検証。不完全な観測足を補間せず採用し、価格接触は観測OHLCで判定する。これらは仕様・データ台帳に開示済み。不採用報告は可能だが実運用収益の承認は不可。|
|A05|Low / evidence limitation|初回研究実走の終了コードは取得されていないことがhandoffに明記されている。保存resultsと末尾完成時刻は確認できたが、監査者自身が初回exit0を観測したとは報告しない。独立検証担当の再走終了コードと分けて記録する。|

## 仕様・コード対応

- 原典コア: [著者公開AIQ August 1997, p.2](https://lindaraschke.net/wp-content/uploads/2026/01/august1997.pdf)と[Active Trader March 2004, pp.78–79](https://lindaraschke.net/wp-content/uploads/2026/03/raschke_pt2_0304.pdf)を事前監査で直接確認。ADX14>30、EMA20、初回押し目、逆指値・構造SLの着想に根拠がある。完全な第10章本文の照合は未実施。
- 原典との差: hypothesisは30上抜けepisode、25未満/DI優位喪失reset、方向判定、3足期限、因果的押し目極値、RR1全決済、保有費用を運用上の解釈と明示する。裁量的利確・追随・再エントリーを完全再現したとする誤認はない。
- 初回限定: generate_setupsはarm足を除外し、最初のtouchで資格を消費する。終値側・away条件不通過、保有/注文中の見送り、未約定でも後続touchに置き換えない。resetなしのADX再上抜けはepisodeを置き換えない。repeat比較も共通away条件を使う。
- 因果性: 指標は先頭からの再帰、anchorは直前までの極値、SL範囲はtouch足まで。pivot・上位足は使用しない。signal確定はbucket nominal end、注文は次の観測足から有効。全明細でarm<signal<entry<=exitを確認。
- 例外経路: opening SL超過による注文取消、entry gapの始値約定、実entryからのRR1再計算、逆行stop gap、利益側TP gap上限、entry-barを含むSL先、3観測足失効、close resetによる当足約定の遡及取消禁止、境界決済を確認。period_boundaryは保存結果で0件。
- 不使用期間: 今回の学習入力は2009-10-01以上2019-01-01未満、売買評価は2010–2018。コードは選抜なしで後続phaseを拒否する。過去の他研究による後半期間の閲覧を仕様に明記し、真の未使用OOSとは呼んでいない。
- 凍結: 保存8ファイルSHA256を現在ファイルから再計算し全一致。completed/protocol.jsonと現行protocolのJSON内容一致、results.jsonとtraining_results.jsonの一致を確認。記録上の凍結時刻は `2026-09-12T23:49:28.182774+00:00` で選抜・完成時刻より前。署名付き外部時刻証明ではなくローカル記録による確認である。

## 実行確認した範囲

監査者はPowerShellからread-onlyの `python -` により、JSON/hash/NumPyによる独立構造照合を実行し終了コード0を確認した。戦略再実行や成果物上書きはしていない。

- 8個の凍結hash、protocolコピー、results/training_resultsの一致。
- 88売買JSON / 16,644明細（二コスト合計）の件数・net R合計を再計算。
- 全明細のarm/signal/entry/exit順序、signal利用可能時刻、注文3観測足以内、anchor/押し目区間、RR1、gross-fee-carry=net、2019年未満の評価終端。
- first候補の各通貨・各費用で同一armの約定最大1件。
- 4条件×2費用の合算件数・損益を11通貨から再集計し保存8合算に一致。
- completed内のvalidation/final_confirmation成果物0。selected空、passing空、adoption_approved=false。
- 決済理由の照合: stop 8,558、target 7,596、both_stop_first 386、target_gap_capped 58、stop_gap 46、period_boundary 0。
- 新規19テストを静的確認。研究担当の関連59テスト通過はhandoffに記録されているが、本監査者は同じテストを再実行していない。全明細別実装再走・入力OHLC全件再現は独立検証担当の責任範囲。

固定1.8pips＋保有費用0.2pip/日：

|条件|取引数|PF|net R|平均net R|MTM DD R|黒字通貨|
|---|---:|---:|---:|---:|---:|---:|
|H1 first|2,521|0.652677|-539.528802|-0.214014|543.548586|0/11|
|H1 repeat|4,123|0.649988|-888.971462|-0.215613|896.812212|0/11|
|H4 first|621|0.804796|-67.758625|-0.109112|81.181674|3/11|
|H4 repeat|1,057|0.799749|-118.404784|-0.112020|129.165681|2/11|

first候補は比較に対してPF/平均Rが微改善したが、PF・期待値・通貨横断・合算DD・学習3区分を両コストで不通過。H1は単通貨DDも不通過。metadata+0.4でfirstのPFはH1 0.651626、H4 0.803049。不採用のまま終了する。

## 未確認事項・次担当

原著全文との一致、全期間tick品質、実際のバー内経路、実コスト/時刻帯、TradingViewの配信・コンパイル・描画・約定、口座運用は未確認。Pine対応表は移植段階に達していないため対象外であり、条件移植漏れの不存在を主張しない。

責任者は本監査と独立検証報告を統合し、限定モデルの不採用と限界を引き渡す。A01/A02は本補足を参照して説明し、結果を見た後の凍結仕様の書換えや追加探索は行わない。
