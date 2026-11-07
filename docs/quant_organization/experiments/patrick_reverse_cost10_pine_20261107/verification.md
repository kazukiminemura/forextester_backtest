# TradingViewでの動作確認

2026-11-07、主担当がTradingView Desktopの新規Pineエディタに最終ファイルを貼り付け、OANDA:EURJPYの15分足に追加。コンパイルが通り、インジケーター名、損益パネル、過去のEntry・TP・SLラベルを確認した。エディタのスクリプトは未保存。

- PineのSHA-256: `567cf3c4cfadff7ede0c1d3322393c5eae2866334183c5bc65d9d41549296ea3`
- エディタから全ソースをコピーして `agent_runs/patrick_reverse_cost10_pine_20261107/editor_readback.txt` に保存。改行を正規化して読み取った文字列は36,275文字で完全一致。
- 2026-08-02～2026-11-06のTradingView内蔵履歴で、通常費用パネルは28決済、勝率42.86%、PF_R 0.405を表示。表示・実行確認時の値であり、Forex Testerとの同値性や後半期間の収益性の検証は行っていない。旧版とラベルが重なるため個別取引の価格配置は画面では照合していない。
- Patrick関連のローカルpytestは61件通過。元PineのSHA-256は `dc31af681b043540f8566b02f41921ec925a9606b4955b46c54e026b32b2f0f9` のまま。
