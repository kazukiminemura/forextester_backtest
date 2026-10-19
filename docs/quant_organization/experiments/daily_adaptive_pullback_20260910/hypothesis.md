# 日足押戻り・過去実績による月次通貨選択

第一実験daily_edge_reset_20260910の学習結果を見た追試。全15通貨一律のpullback05は黒字でも安定性不足だった。その同一売買規則を、当時までの成績が良い通貨へ適用する。価格形成のトレンド持続性・コストと値幅の関係が通貨/時期で異なり、その差が数か月持続すれば改善し得るという仮説。推論であり実証済みではない。相場特性の反転、短期運、通貨間相関で崩れる。

結果を見て固定した通貨リストではなく、各月初に過去確定取引だけから共通の規則で選択する。この動的規則の選択自体は第一学習成績を見た事後選択であり、真の未使用検証とは呼ばない。追加候補は24/36/60暦月の3つで終了する。比較は第一の固定全通貨pullback05、今回の学習期間だけ比較値を再計算する。

## 変えない売買規則

第一hypothesis.mdのpullback05、次始値、SL2ATR20、TP3R、最大30本close→31本目open、250本warmup、日曜月曜統合、日次MTM、SL優先、保有日ceil、二費用、保有0.2pip primary/0・1pip感度をそのまま使う。上位足なし。全決済、実注文なし。

## 仮想母集団 shadow

全15通貨で毎回2010-01-01から今回phase末まで同じエンジンを連続実行し、出場しなかった取引も仮想保有する。実取引のskipや枠不足はshadowのシグナル・保有・次のエントリーを変更しない。phase境界でshadowを再始動しない。末尾の研究上のperiod_boundary強制精算は月次成績へ一切含めない。実取引はphase開始時flatで、phase前から保有していたshadow取引を途中から買わない。phase末のactual保有は最終close研究精算し、強制精算除外感度も示す。

## 月次選択

月は統合後trading dateの暦月。例えば日曜日が翌月月曜に統合されたら翌月の足として扱う。当月の全15通貨に含まれる最初raw時刻の最小をdecision cutoffとする（日曜のため前月になる場合あり）。そのcutoffより厳密に前にexit exposureが確定したshadowだけを利用する。日中決済の実時刻は不明なのでraw最終+60秒まで未確定とする。lookback下限は対象trading月の24/36/60か月前の1日00:00、下限inclusive、cutoff exclusive。

scoreはmetadata spread+0.4pip往復と保有0.2pip/暦日を引いたshadow netR。各通貨8件以上、平均netR>0のみ資格あり。sum(netR)/(n+10)の降順、同値はsymbol辞書順、最多5通貨。月初に保存し月内固定。月替わりで既存actual保有を決済しない。適格0なら新規取引なし。

## actual資金枠

選ばれた通貨の新規shadow entryだけを追随。最多同時5ポジション。同一構成通貨が含まれるポジションは最多3（方向相殺しないgross count）。USDJPYはUSD/JPY各1として数える。通貨間net exposureや口座証拠金の再現ではない。

entry raw timestamp昇順、同時刻はsymbol辞書順。exit exposure timestampのイベントは同時刻entryより先に処理し枠を解放する。日中決済の資金枠はraw最終+60秒まで占有。entry時に将来のexit成績/理由/保有期間から採否を決めない。月次scoreの情報時刻とentry容量判断をそれぞれ保存する。入場時の枠不足は後日取り直さない。

## 評価

期間はtrain2010–2018、validation2019–2022、final2023–2026-08-31未満。各phase actualはflat restart、shadowの過去履歴は継続母集団として利用。学習だけで3候補を比較し、両費用のgateを通る1候補を最悪PF最大→最悪平均R最大→最大MTM DD最小→ID辞書順で選ぶ。後半失敗時fallbackなし。

gateはprotocol.json。主要条件はtrain75件/PF1.15、validation30件/PF1.10、final30件/PF1.05、全phase平均R>0、DD20R以下、出場5通貨以上、利益通貨が出場通貨の厳密過半数。train3区分のexit年帰属netR全て正。0/1pip保有感度・区分MTM・全通貨shadow比較を併記。期間は既閲覧、実スワップ未確認、価格bid/ask・TZ未確定、口座通貨換算なし。通過も実運用保証ではない。
