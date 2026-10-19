# YTT × Jev 独立品質監査

2026-10-10 JST。担当は品質監査。編集責任は本書のみ。初期判定 **NEEDS_EVIDENCE / 実装中・再監査待ち**。

## 監査対象と実行範囲

`charter.md`、`board.md`、本実験の `hypothesis.md / data_inventory.md / validation.md`、TypeSafe skill、`scripts/research_ytt_jev.py` とその既存会計・応答検証依存を読取確認した。実装担当が並行変更中であり、以下の初期所見は最終版認定ではない。初期読取終盤の runner SHA256 は `eb791fa4134d60787d3b6330940614a9179bb043b70f3af0456454a962f85989`。

公式 [Models](https://docs.typesafe.ai/models.md) を本監査で GET 確認し、jev-1.13.0、入力100万token当たり0.042 USD、出力無料、64k request 上限を確認。web toolの取得エラー後、Python urllibによる公開文書GETで確認した。推論API、秘密値取得、実注文は実施していない。

## 初期所見

1. **P1・未解決: 予算の範囲が出力ディレクトリ単位。** 初期実装は `--output` 配下にだけ `reservations.jsonl` と lock を作る。出力先を変えると承認100円に対する引当90円を新たに使用できる。今回の承認に対して出力先を固定するか、承認単位の共有台帳と排他が必要。キャッシュが存在するのに対応予約がない場合も fail closed とする必要がある。これは通常の同一出力での予約精算が壊れているという所見ではない。
2. **P1・再現済み: 失敗3件停止が再実行でリセット。** 初期 `infer` は `result['failures']=0` から開始し、過去失敗を読み戻さない。同じ7件のsynthetic payload、偽key、必ずTimeoutErrorになる偽transport、tempdirで2回実行した。初回3件、再開3件、計6件の偽送信になった。外部通信なし、終了コード0。3失敗で実験を停止する仕様に対して累積停止が必要。
3. **P2・表示制約: 円口座値にAI料金を含めていない。** 会計は100万円開始・90万円floor、0.5%risk、最大25倍・1000通貨stepのUSDJPY単独。API料金の控除はない。最新版途中には「API usage fees ... excluded from trading P/L」が追加されており、局所的な改善確認用P/Lであることを明示すること。AI込み総利益・口座純資産として扱う場合は別途料金込み再計算が必要。検証者の提案ゲートと相違が残るため、責任者が結果前に範囲を固定する。
4. **P2・更新確認待ち: 選抜前の後期実行。** 最初の読取では phase 指定だけで後期を評価できたが、その後 `later_selection` に training hash と independent_review_passed を要求する経路が追加された。最終固定仕様、protocol、training判定の責任者承認との照合が未完了。後期の直接指定だけで進めないことは改善されている。

## 現時点で確認できた整合

1. 送信前予約は追記・flush・fsync、同一出力の排他lockあり。成功usageのみ精算、最大65,536tokenを超えるusageは応答validatorが拒否。失敗/不明分は予約額を残し、同じhashの再送は避ける。settlementと応答usageの不一致、JSON破損は例外停止する構造。
2. Jevと同待機対照は共通 `delayed_signals` を利用。確定信号後1本を待ち、その足のSL到達・突破水準内への戻り・不完全足・時間gapで両方とも無効化する。部分応答では有効応答母集団の `covered_control` も作成する。
3. 決済は従来会計を再利用し、同足TP/SLはSL優先、SLgapは始値、TPgapは目標価格上限。RRは1/1.5/2のみ、SL固定・始値基準TP延長。価格・損益は決定的計算でありJevへ算術を委任していない。
4. 全期間既閲覧、価格side/時刻不明、swap未実測、AI確率≠勝率、部分応答≠完全検証を文書・結果limitationsに明記。`adoption_approved=False` の保持を確認。

## 未確認と引渡し判定

凍結protocol、最終source/test SHA、全入力の再照合、完成版behavior tests、実API応答・費用台帳、全候補独立再現、期別/通貨別のCI・採用gate、TradingView対応表は未確認。Pineには未採用AI条件を組み込まず、今回のPython研究連携とPine直接連携を混同しない。

現時点は初期所見の責任者返却まで。**有料本実行・研究合格・Pine出力・TradingView実機確認・実運用承認を認定しない。** 最終コード受領後、予算永続性と完成結果を再監査する。

## 修正版の独立再テスト（source 3d77d453）

対象 runner SHA256 `3d77d4539d90e57c5b9cc61d6128e3c16ec862f93ba92628bd080752750ea477` を実行前後に照合。新hypothesis/protocolを読取。監査独自のPython一時ディレクトリ、偽transport、固定偽keyを利用し、外部API・秘密値読取なし。終了コード0。

|項目|実測|判定|
|---|---|---|
|累積失敗3件停止|初回3 calls / 3 failures / 1.6515072円予約、再開0 calls / failures 3|初期P1の失敗再開問題を解消|
|固定出力先|実transportを指定しない別出力で、key読取前にValueError|出力先による予算再作成経路を解消|
|成功精算|100 input tokensの偽成功2件→0.00168円|一致|
|settlement金額改変|成功後の精算額を0へ変更→Settlement does not match validated response|送信前停止|
|台帳欠落|成功1件後にledgerを除去、同じ1件＋新1件を再実行→新規1 call、responseは2件、報告課金0.00084円|**P1残存**。旧成功1件の費用を忘れて継続|

残存P1の修正条件: `responses/*.json` の既存hash全件に予約があることを送信前に確認し、孤立responseが1件でもあれば例外停止する。旧responseとledgerが両方意図的に削除された状況を検出する外部監査証跡の保証まで要求するものではない。

protocolの `api.execution_order` は「結果非依存固定hash order」とあるが、runnerは期間中点分割＋通貨交互の結果非依存順。結果前に記載を実装へ一致させること。API料金は別報告、採用cash gate時には控除必須とprotocolに固定されたため、初期P2は明示された研究制約として保持する。

この時点の引渡しは **NEEDS_EVIDENCE / 台帳欠落P1修正待ち**。研究結果および実API応答は未確認。

## 最終pre-API監査（source 3d9e0f34）

runner SHA256 `3d9e0f34507019e30265e5aa723f5f672cd3dbbac7785419be037c9d3d1c591a` を独立照合した。外部通信なしの独自再テストを同SHAで実施し、終了コード0、`PRE_API_GUARDS_PASS_NO_NETWORK`。

1. 孤立response検査を確認。偽成功1件の後にledgerだけ削除した再現で、`Cached responses lack durable reservations; refuse budget reset` により新規transport呼出0。残存P1解消。
2. 累積失敗は初回3 calls、再開0 calls / failures 3。固定出力先以外の通常live呼出は拒否。成功2件×100tokenの合計0.00168円精算も一致。
3. 精算額を0へ改変したledgerは、`Settlement does not match validated response` により拒否。監査テスト中のAPIkeyは常に固定偽値。公開モデル文書GET以外の外部通信、秘密値取得、API課金なし。
4. protocolの順序表記は時刻中点分割＋通貨round-robinへ修正され、実装と一致。API料金除外を費用込み利益と扱わない制約、採用cash gate時の料金控除義務を保持。

**判定: PRE_API_GUARDS_PASSED。** 初期P1所見は解消した。責任者が仕様・入力・コードを凍結した後、承認100円に対する引当90円上限内の研究用smoke実行へ引渡し可。研究合格・勝率/RR改善・Pine連携・TradingView実機確認・実運用承認は引き続き未認定。実APIの応答、課金実績、完全coverage、独立会計と採用判定は後続の監査対象。

## 実API smoke25の独立費用・応答監査

2026-10-10 10:31:29 JST に読取監査。責任者が実行した初期25件の保存結果 `agent_runs/ytt_jev_20261010/training_results_smoke25.json` と、台帳最初の25 reserve/settleおよび対応responseを照合した。監査担当による追加API呼出なし。監査独自のJSON/Decimal/hashlib検算を実行し、終了コード0、`INDEPENDENT_SMOKE25_AUDIT_OK_NO_API_CALLS`。

|確認項目|独立再計算|
|---|---:|
|有効応答|25 / 25|
|accept分類|6 / 25（トレード勝率ではない）|
|input tokens合計|35,120|
|公表単価によるUSD概算|0.00147504 USD|
|安全200円/USD換算|0.295008円|
|平均応答時間|0.1972990000秒|
|最大応答時間|0.2302573000秒|

requestのcanonical bytes SHA、要求と保存requestの一致、凍結question全文、jev-1.13.0要求/応答版、24本の状態allowlist、選択肢分布・最大選択・閾値0.5、valid/latency、実usage、各精算額とsmoke合計が一致。口座・未来損益・銘柄日付を送る追加fieldなし。API確率を勝率に置換した表示なし。初期smoke結果は `NEEDS_EVIDENCE / adoption_approved=false` を保持している。

再現識別子:

- runner SHA256: `3d9e0f34507019e30265e5aa723f5f672cd3dbbac7785419be037c9d3d1c591a`。freeze内sourceと現物一致。
- smoke result SHA256: `2be259f5e19887a89e5caff2cba4647ae9c0126e3eba84c62cf90d196fe75e18`。
- freeze.json SHA256: `3467ab91150fc7cbd86940b53169295d573e42c6444f5e54b384abb98c0eced2`。

同時に読み取った進行中台帳の703行は352予約/351精算、未精算1件を最大予約のまま数えた保守合計4.6898208円。snapshot SHA256 `8f512042631658ae80c48ccba737063671e074a48211865d4167b07e1c7cffdf`。ここで全703行の順序・重複なし・予約定数・精算先予約存在を検査したが、response本文の全件検算対象は初期25件に限定する。台帳は実行中に伸びており、この費用は最終費用でも請求書実測でもない。

**判定: SMOKE25_RESPONSE_AND_COST_VERIFIED / 全研究はRUNNING。** 初期API連携・費用計算に新しい重大所見なし。6659母候補の全coverage・費用後会計・期間選抜・勝率/RR改善は未確認で、初期25件を根拠に改善成功とは判定しない。

## 実走終了後の最終独立監査

対象は責任者が終了コード0を受領したtraining実走の保存物。監査担当はAPI再送せず、現物JSON/CSV/SHAの別実装読取検算を実施した。監査コマンド終了コード0、`FINAL_INDEPENDENT_AUDIT_ALL_MATCH_NO_API`。runner・テスト・依存・仕様・入力一覧を含むfreeze_manifest **11/11 SHA一致**、保存execution/entry900 **6/6入力SHA一致**。

### 応答・費用・停止

|項目|独立検算|
|---|---:|
|予定有効母候補|6,659|
|送信済み|1,887（初期25＋継続1,862）|
|契約有効応答|1,884|
|契約無効応答|3|
|未送信|4,772|
|有効応答なし合計|4,775|
|有効応答input tokens|2,646,595|
|有効usageに基づくUSD概算|0.11115699 USD|
|安全200円/USDによる精算|22.231398円|
|無効3件の最大予約保持|1.6515072円|
|管理費用合計|**23.8829052円**|

費用は公表単価と保守換算による管理額であり、カード請求額・税額を実測したものではない。無効応答にも計4,295 tokensのusage fieldは保存されているが、事前規則どおり精算せず65,536 tokens/件の予約を保持した。承認100円・運用引当90円のどちらも超えていない。

全1,887件でrequest canonical hash、要求一覧との一致、凍結rubric、要求/応答model、確率型・有限範囲・合計、latency、accepted、予約/精算との対応を照合。responseの余剰・予約重複・精算重複なし。有効応答のみの精算額が一致。

無効3件はすべて「回答choiceが表示probabilitiesの最大選択肢ではない」という凍結契約違反であり、通信timeoutではない。

|request hashの先頭|choice|選択probability|最大probability|
|---|---|---:|---:|
|0ebc13fb2296|accept|0.41|0.42|
|a8c3a8f9951b|skip|0.45|0.46|
|4048297e7f7a|uncertain|0.36|0.37|

この3件を後から有効化したり閾値を緩めたりしていない。保存結果failures=3、最後の送信までの全予約と応答が存在し、inference.lockなし、後期selection/later/latest出力なし。前段の同一sourceによる再開テストで累積3失敗後の新規送信0を確認済み。**予算が残っていても、この凍結実験の追加送信・自動再試行は停止規則に反するため不可。**

### 期間・通貨・取引集計

USDJPY/EURUSD/GBPUSDの有効応答は各628件、accept分類は196/114/150件。母候補と有効/accept件数、欠測件数がresult coverageと一致した。AI分類のaccept率を勝率と呼んでいない。

**60 CSV・37,490取引観測**（比較arm/RR/費用条件の重複を含む）について、risk、TP、spread/slippage、gross/net price、gross/net Rを別計算した。Jev/covered_control/delay_controlの元候補集合への所属も全件照合。件数、合計R、平均R、PF、wins、closed-trade DD、incomplete露出件数、勝率、実現payoffの各10集計がJSONと一致した。

通常費用・3通貨合算の部分応答対照は以下。元候補全件の改善証明ではない。

|RR|arm|決済数|費用後勝率|PF_R|実現平均利益/平均損失|net R|
|---|---|---:|---:|---:|---:|---:|
|1|covered_control|1,246|45.7464%|0.779928|0.924968|-111.418025|
|1|Jev|302|46.3576%|0.813185|0.940971|-20.969314|
|1.5|covered_control|1,230|40.9756%|0.802348|1.155764|-109.907350|
|1.5|Jev|300|42.3333%|0.796741|1.085324|-25.406589|
|2|covered_control|1,209|38.6270%|0.795470|1.263895|-118.138208|
|2|Jev|297|40.4040%|0.796994|1.175567|-26.279625|

勝率の部分比較は増えていても、RR1.5/2では実現payoffが対照より低く、全Jev案は費用後赤字。取引数・母集団の違うnetRの絶対値だけを「利益改善」としない。CIと全母候補検証は完了していない。価格と約定の独立全M1再生、fees控除後口座、ライブ運用遅延はこの最終監査の実行範囲外。

識別子:

- 最終training_results.json SHA256: `06df3a8cecbba686479265c596d197fc5330a65cf2eb733f903ce6ac665cf8a8`。
- 最終reservations.jsonl SHA256: `0d836929fee36c80f43849677c7fa51f129701a489d687557e3ebd1ff29ed03a`。
- runnerは上記 `3d9e0f34507019e30265e5aa723f5f672cd3dbbac7785419be037c9d3d1c591a` から変更なし。

### 最終引渡し判定

**AUDITED_NEEDS_EVIDENCE_PARTIAL_NO_ADOPTION。** 未解消の重大な費用台帳・保存成績の実装不一致は認めない。部分研究の結果と停止理由を説明する成果物として引渡し可。全研究完了・勝率とRR双方の改善証明・研究合格とは認定しない。現行PineへJev条件を採用せず、TradingView実機済み・実運用承認へ昇格させない。初期P1は解消済み、残る制約は欠測と既閲覧データ、仮費用/未実測swap、円口座API料金別計上、未実施の独立検証範囲である。
