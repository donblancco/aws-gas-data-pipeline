# 統合データ管理システム

サポート業務に関するJIRA課題、Slackメッセージ、Salesforceデータを自動収集・統合し、レポートを生成する包括的なデータ管理システムです。

## 📋 システム概要

### 主要機能
- **JIRA課題データ自動取得**: AWS Lambda + S3経由でSUPプロジェクトの課題データを毎日自動取得
- **Slack活動監視**: TaskRunnerチャンネルのメッセージを自動収集
- **JIRA-SFDC統合**: 課題データと顧客情報を統合してインパクト分析
- **週次・月次レポート**: TS稼働状況の自動集計とレポート生成

### システムアーキテクチャ
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   JIRA API      │    │   Slack API     │    │   Salesforce    │
│   課題データ    │    │   Messages      │    │   Customer Data │
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
          ▼                      │                      ▼
┌─────────────────┐              │            ┌─────────────────┐
│  AWS Lambda     │              │            │  Manual Upload  │
│  JIRA Exporter  │              │            │   (SFDC Data)   │
│  (JST 04:00)    │              │            └─────────┬───────┘
│                 │              │                      │
│ JIRAからCSV生成 │              │                      │
│ ↓ S3に保存      │              │                      │
└─────────┬───────┘              │                      │
          ▼                      ▼                      ▼
┌─────────────────┐    ┌─────────────────────────────────────────┐
│   AWS S3        │    │        Google Apps Script               │
│   CSV Storage   │◄───┤  ┌─────────┐ ┌─────────┐ ┌─────────────┐│
│                 │    │  │JIRA Sync│ │SlackSync│ │SFDC Join    ││
│ • latest.csv    │    │  │(07:00)  │ │         │ │(07:30)      ││
│ • daily/        │    │  │         │ │         │ │             ││
│   YYYYMMDD.csv  │    │  │S3から   │ │直接API  │ │シート間     ││
└─────────────────┘    │  │CSV取得  │ │呼び出し │ │データ統合  ││
                       │  └─────────┘ └─────────┘ └─────────────┘│
                       └─────────┬───────────────────┬───────────┘
                                 ▼                   ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Google Sheets                               │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐│
│  │JIRA Master  │ │Slack Master │ │JIRA Impact  │ │TS稼働       ││
│  │Spreadsheet  │ │Spreadsheet  │ │Check Sheet  │ │チェック     ││
│  │             │ │             │ │             │ │             ││
│  │S3からの     │ │Slack APIから│ │JIRAとSFDCの │ │集計・レポート││
│  │JIRAデータ   │ │メッセージ   │ │統合データ   │ │シート群     ││
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

## 🏗️ システム構成

### AWS インフラストラクチャ
- **Lambda関数**: JIRAデータ取得とCSV生成
- **S3バケット**: CSVファイル保存（public-read）
- **EventBridge**: 日次スケジュール実行（JST 04:00）
- **CloudWatch**: ログ監視とアラート

### Google Apps Script
- **データ取得**: S3からCSVファイルを取得
- **データ統合**: 複数データソースの結合処理
- **UI**: カスタムメニューによる手動操作
- **レポート**: 週次・月次の自動集計

## 🗂️ データ構造詳細

### 1. JIRA Master Table
**スプレッドシートID**: `YOUR_JIRA_SPREADSHEET_ID`

#### シート構成
- **ログ**: システム実行履歴（最新100件保持）
- **SUP課題データ**: 現在稼働中の課題（1,244件）
- **org_sup**: 全履歴データ（4,346件）

#### データ項目（12列）
| 列 | フィールド名 | 説明 | JIRA API マッピング |
|---|---|---|---|
| A | 課題タイプ | Support等 | `issuetype.name` |
| B | 課題キー | SUP-XXXX形式 | `key` |
| C | 課題ID | JIRA内部ID | `id` |
| D | 要約 | 課題の概要 | `summary` |
| E | 機能分類 (Function) | カスタムフィールド | `customfield_10141` |
| F | 問合せ分類 (Inquiry) | カスタムフィールド | `customfield_10140` |
| G | 報告者 | 課題報告者名 | `reporter.displayName` |
| H | TS | 担当テクニカルサポート | `customfield_10129` |
| I | 担当者 | アサイン先 | `assignee.displayName` |
| J | 優先度 | High/Medium/Low | `priority.name` |
| K | 作成日 | 課題作成日時 | `created` |
| L | TOKEN | 顧客識別トークン | `customfield_10163` |

### 2. Slack Master Table
**スプレッドシートID**: `YOUR_SLACK_SPREADSHEET_ID`

#### シート構成
- **TS_ASK**: 顧客からの技術的質問（66件）
- **TaskRunner**: Slackチャンネルの全メッセージ（587件）

#### TS_ASK データ項目
| 列名 | 説明 | データ型 | 用途 |
|------|------|----------|------|
| DATE | 投稿日時 | 文字列 | 時系列分析 |
| NAME | 投稿者メールアドレス | 文字列 | ユーザー識別 |
| TOKEN | 顧客識別トークン | 文字列 | JIRA/SFDC連携キー |
| 導入方式 | プロキシ/Widget等 | 文字列 | 技術分類 |
| TARGET_URL | 対象サイトURL（JSON形式） | 文字列 | サポート対象 |
| QUESTION | 質問内容 | 文字列 | 問合せ内容 |

### 3. JIRA Impact Check
**スプレッドシートID**: `YOUR_IMPACT_CHECK_SPREADSHEET_ID`

#### シート構成
- **JOIN結果_SUP_SFDC**: JIRA課題と顧客情報の統合データ（249件）
- **SUP課題データ**: JIRAからの課題データ（644件）
- **sfdc**: Salesforce顧客データ（1,433件）
- **ログ**: 統合処理の実行履歴

#### SFDC データ項目
| 列名 | 説明 | データ型 |
|------|------|----------|
| トークンキー | 顧客識別子 | 文字列 |
| 初回商談: 商談名 | 商談情報 | 文字列 |
| 契約管理: エンドユーザ: 取引先名 | 顧客企業名 | 文字列 |
| 合計月額 | 月額契約金額 | 数値 |

### 4. TS稼働チェック
レポート生成用ワークシート集

#### シート構成と役割
- **weekly_Newticket**: 週次新規チケット集計
- **Weekly_TS-ASK**: 週次TS問合せ集計  
- **monthly_Newticket**: 月次新規チケット集計
- **Monthly_bug**: 月次バグ報告（16件）
- **Monthly_TS_ASK**: 月次TS問合せ（19件）
- **TS_ASK_cp**: TS問合せデータコピー（1,000件）
- **JIRA_copy**: JIRAデータコピー（1,000件）

## 🤖 GAS プロジェクト詳細

### 1. jira.gs - JIRA データ自動取得
**目的**: S3からJIRAのCSVエクスポートを毎日自動取得

#### 主要関数
- `updateSheetsFromS3()`: メイン処理（S3→スプレッドシート）
- `fetchWithRetry()`: HTTP通信のリトライ機能（最大3回）
- `validateData()`: CSVデータの検証（12列チェック）
- `logExecution()`: 実行ログの記録
- `setupTrigger()`: 定期実行トリガーの設定

#### 実行スケジュール
- **頻度**: 毎日
- **実行時刻**: 07:00（Lambda実行3時間後）
- **データソース**: AWS S3の固定CSV（`latest.csv`）
- **処理フロー**: 
  1. 📥 **S3からCSV取得**
     - URL: `https://wovn-sup-jira-exports.s3.amazonaws.com/SUP-project-exports/latest.csv`
     - 認証: 不要（public-read設定）
     - エンコーディング: UTF-8
  2. 🔍 **データ検証**
     - 列数チェック（12列必須）
     - 内容の妥当性確認
     - エラー時はリトライ（最大3回）
  3. 🚫 **重複チェック**
     - 課題キー（B列: SUP-XXXX）でユニーク判定
     - 既存データとの突合
  4. ➕ **新規データ追記**
     - 「SUP課題データ」シートに新規行のみ追加
     - ヘッダー行の自動生成（初回）
  5. 📊 **実行ログ記録**
     - 処理件数、実行時間、エラー情報を「ログ」シートに記録

#### 設定値
```javascript
const CONFIG = {
  CSV_URL: 'https://your-company-exports.s3.amazonaws.com/project-exports/latest.csv',
  SPREADSHEET_ID: 'YOUR_JIRA_SPREADSHEET_ID',
  WORKSHEET_NAME: 'SUP課題データ',
  LOG_WORKSHEET_NAME: 'ログ',
  MAX_RETRIES: 3,
  RETRY_DELAY: 1000
};
```

### 2. join_sfdc.gs - JIRA-SFDC データ統合
**目的**: SUPプロジェクトの課題とSalesforceの顧客情報を統合

#### 主要関数
- `joinSupDataWithSfdcKeepComments()`: メイン統合処理
- `setupDailyTrigger()`: 定期実行トリガー設定
- `deleteDailyTrigger()`: トリガー削除
- `checkTriggers()`: トリガー状況確認

#### 実行スケジュール
- **頻度**: 毎日
- **実行時刻**: 07:30（JIRAデータ取得後）
- **処理フロー**:
  1. SUPデータとSFDCデータを取得
  2. TOKENキーでデータをマッチング
  3. 既存のコメントを保持
  4. 統合結果を新しいシートに出力

#### データマッピング
- **結合キー**: TOKEN（SUP） ⟷ トークンキー（SFDC）
- **出力項目**: 課題情報 + 顧客企業名 + 月額契約金額 + コメント

### 3. slack.gs - Slack メッセージ取得
**目的**: TaskRunnerチャンネルのメッセージを自動取得

#### 主要関数
- `fetchSlackMessagesDaily()`: メイン処理

#### 実行方式
- **取得方式**: 増分取得（前回取得以降のメッセージのみ）
- **保存先**: TaskRunnerシート
- **API**: Slack Web API（`conversations.history`）
- **認証**: Slack Bot Token

#### 設定値
```javascript
const token = "YOUR_SLACK_API_TOKEN";
const channel = "C08DHM22ARM"; // TaskRunnerチャンネル
```

### 4. weekly_TS_ASK.gs - 週次集計
**目的**: DATE-DATE列から週別の件数を集計

#### 主要関数
- `countWeeklyFromDateDateColumn_final()`: 週次集計処理

#### 処理内容
- 日付データから週の開始日（月曜日）を計算
- 週ごとの件数を集計
- 「週別集計」シートに結果を出力

## ☁️ AWS Lambda システム

### lambda_jira_exporter.py - JIRA データエクスポーター

#### 主要機能
- **JIRA API連携**: REST API v2を使用したデータ取得
- **S3ファイル出力**: 日次ファイル + 最新ファイルの2系統
- **Basic認証**: JIRAトークンベース認証
- **エラーハンドリング**: リトライ機能とCloudWatchログ

#### 実行スケジュール
- **トリガー**: EventBridge（毎日JST 04:00）
- **対象期間**: 前日作成課題（`created >= startOfDay(-1) AND created < startOfDay()`）
- **最大取得件数**: 5,000件

#### 出力ファイル仕様
1. **latest.csv**（GAS連携用）
   - **用途**: Google Apps Scriptが参照する最新データ
   - **形式**: 標準12列（ヘッダー + データ行）
   - **更新**: 毎日JST 04:00に上書き
   - **アクセス**: パブリック読み取り可能
   ```
   課題タイプ,課題キー,課題ID,要約,機能分類 (Function),問合せ分類 (Inquiry),報告者,TS,担当者,優先度,作成日,TOKEN
   Support,SUP-3349,53302,2025年2月のCopilotログ出し...,その他,,Rong Chen,Shoji Go,,,,Woep0G
   ```

2. **daily/SUP_created_YYYYMMDD.csv**（履歴保存用）
   - **用途**: 日次データの履歴保存・監査
   - **形式**: 拡張17列（日付メタデータ + 12列）
   - **保存先**: `s3://wovn-sup-jira-exports/SUP-project-exports/daily/`
   - **保持期間**: 90日間（自動削除）
   ```
   作成日,年,月,日,エクスポート日,課題タイプ,課題キー,課題ID,要約,機能分類 (Function),問合せ分類 (Inquiry),報告者,TS,担当者,優先度,作成日時,TOKEN
   2025年7月15日,2025,7,15,2025-07-16,Support,SUP-3349,53302,...
   ```

#### 環境変数
```bash
JIRA_URL=https://your-domain.atlassian.net
JIRA_USERNAME=your-email@company.com
JIRA_API_TOKEN=your-jira-token
S3_BUCKET=your-company-exports
S3_PREFIX=SUP-project-exports/
```

#### データフロー詳細
```
【JIRA データパイプライン】
JIRA REST API → AWS Lambda → AWS S3 → Google Apps Script → Google Sheets
      ↓             ↓           ↓           ↓                    ↓
   前日作成課題   CSV変換・生成  CSV保存    HTTP取得           シート追記
   ・SUP-XXXX    ・12列形式    ・latest.csv ・S3 URL指定      ・重複除去
   ・カスタム     ・文字エンコ   ・daily/    ・認証なし        ・ログ記録
    フィールド     ード対応      YYYYMMDD    ・リトライ機能
```

## ⏰ 実行スケジュール統合

### 日次実行フロー
```
JST 04:00 - AWS Lambda実行
├── 🔍 JIRA API呼び出し
│   ├── 前日作成課題を検索（JQL: created >= startOfDay(-1)）
│   ├── SUP専用カスタムフィールドを含む12項目取得
│   └── 最大5,000件まで取得
├── 📄 CSV生成・変換
│   ├── 12列の標準形式（GAS用）
│   ├── 17列の日次形式（メタデータ付き）
│   └── UTF-8エンコーディング
├── ☁️ S3保存
│   ├── latest.csv（GASが参照する固定ファイル）
│   ├── daily/SUP_created_YYYYMMDD.csv（履歴保存）
│   └── public-read権限で保存
└── 📊 CloudWatchログ出力

JST 07:00 - JIRA データ同期（GAS）
├── 🌐 S3からCSV取得
│   ├── 固定URL: https://wovn-sup-jira-exports.s3.amazonaws.com/.../latest.csv
│   ├── HTTP GETリクエスト（認証なし）
│   └── リトライ機能（最大3回、指数バックオフ）
├── ✅ データ検証・処理
│   ├── CSV形式チェック（12列必須）
│   ├── 課題キー（SUP-XXXX）による重複チェック
│   └── 新規データのみ抽出
├── 📝 Google Sheets更新
│   ├── 「SUP課題データ」シートに追記
│   ├── ヘッダー行の自動生成
│   └── 列幅・書式の自動調整
└── 📋 実行ログ記録（「ログ」シート）

JST 07:30 - JIRA-SFDC統合（GAS）
├── 📊 シート間データ統合
│   ├── SUPデータ（S3経由で取得済み）
│   ├── SFDCデータ（手動アップロード）
│   └── TOKENキーでマッチング
├── 🔄 統合処理
│   ├── 既存コメントの保持
│   ├── 新しい「JOIN結果_SUP_SFDC」シート作成
│   └── 顧客情報（企業名・月額）の付加
└── 💾 結果保存・ログ記録
```

### 週次・月次処理
- **週次集計**: 手動実行（`weekly_TS_ASK.gs`）
- **月次レポート**: 各種集計シートの自動更新

## 🚀 セットアップ手順

### 1. AWS環境構築

#### 前提条件
- AWS CLI設定済み
- Terraform >= 1.0
- JIRA管理者権限
- 適切なIAM権限

#### デプロイ手順
```bash
# 1. Terraform設定
cd terraform
cp terraform.tfvars.example terraform.tfvars

# 2. 環境変数設定
vi terraform.tfvars
# jira_url, jira_username, jira_api_token を設定

# 3. インフラ構築
terraform init
terraform plan
terraform apply
```

#### 作成されるリソース
- Lambda関数（jira-csv-exporter）
- S3バケット（wovn-sup-jira-exports）
- EventBridgeルール（日次実行）
- IAMロール・ポリシー
- CloudWatchロググループ

### 2. Google Apps Script設定

#### セットアップ手順
1. **スプレッドシート準備**:
   - 各用途に応じたスプレッドシートを作成
   - 適切な共有設定を実施

2. **GASプロジェクト作成**:
   - 拡張機能 → Apps Script でプロジェクト作成
   - 各.gsファイルの内容をコピー

3. **設定値更新**:
   - スプレッドシートIDを実際のIDに変更
   - API認証情報を設定

4. **権限承認**:
   - 各関数の初回実行で権限承認
   - 必要なスコープを確認・許可

5. **トリガー設定**:
   - `setupTrigger`等の関数で定期実行を設定

### 3. 認証情報管理

#### JIRA API設定
1. JIRAアカウントでAPIトークンを生成
2. Terraformの環境変数に設定
3. Lambda環境変数で管理

#### Slack API設定
1. Slack Appを作成
2. Bot Tokenを取得
3. GAS内で直接設定（セキュリティ要改善）

#### Salesforce データ
- 手動アップロード方式
- 定期的なデータ更新が必要

## 📊 レポート機能詳細

### 自動生成レポート

#### 週次レポート
- **新規チケット数**: 週ごとの新規課題作成数
- **バグ報告傾向**: バグ課題の発生パターン
- **TS問合せ件数**: 技術サポートへの問合せ数
- **顧客別集計**: TOKEN別の活動状況

#### 月次レポート
- **TSごとの稼働状況**: 担当者別の処理件数
- **課題種別分析**: カテゴリ別の傾向分析
- **顧客インパクト分析**: 契約金額別の課題分布
- **処理時間分析**: 課題解決にかかる時間

### カスタムレポート作成
1. **データソース特定**: 必要なシートとデータ範囲
2. **集計ロジック実装**: GAS関数での処理ロジック
3. **可視化実装**: グラフ・表の自動生成
4. **定期実行設定**: トリガーでの自動更新

## 🛠️ 運用・保守

### 定期メンテナンス

#### 日次チェック項目
- [ ] Lambda実行状況確認（CloudWatch）
- [ ] S3ファイル更新確認
- [ ] GAS実行ログ確認
- [ ] データ件数の妥当性確認

#### 週次チェック項目
- [ ] 全システムの正常稼働確認
- [ ] エラーログの詳細確認
- [ ] データ整合性の確認
- [ ] API制限の監視

#### 月次チェック項目
- [ ] パフォーマンス分析
- [ ] ストレージ使用量確認
- [ ] コスト分析
- [ ] セキュリティ監査

### モニタリング

#### 重要な監視指標
- **データ取得成功率**: 95%以上を維持
- **Lambda実行時間**: 平均2-5秒以内
- **GAS実行時間**: 平均1-3秒以内
- **データ増加率**: 日次10-50件程度
- **エラー発生率**: 1%未満

#### アラート設定
```bash
# CloudWatch監視例
aws logs filter-log-events \
  --log-group-name /aws/lambda/jira-csv-exporter \
  --filter-pattern "ERROR" \
  --region us-east-1
```

### バックアップ戦略

#### 自動バックアップ
- **Lambda**: 日次データ90日保持
- **GAS**: ログ最新100件保持
- **S3**: バージョニング30日

#### 手動バックアップ（月次）
1. 全スプレッドシートをエクスポート
2. GASコードをローカル保存
3. 設定情報をドキュメント化
4. Terraformステート保存

## 🚨 トラブルシューティング

### よくある問題と対処法

#### 1. Lambda実行エラー
**症状**: `JIRA API認証エラー`
**原因**: APIトークンの期限切れ
**対処法**:
```bash
# 1. JIRAでAPIトークン再生成
# 2. Terraform変数更新
terraform apply -var="jira_api_token=new-token"
```

#### 2. S3アクセスエラー
**症状**: `CSV取得エラー`
**原因**: バケットポリシーまたは権限不足
**対処法**:
```bash
# S3ファイル確認
aws s3 ls s3://wovn-sup-jira-exports/SUP-project-exports/ --region us-east-1

# 権限確認
aws s3api get-bucket-policy --bucket wovn-sup-jira-exports
```

#### 3. GAS実行制限エラー
**症状**: `Exceeded maximum execution time`
**原因**: 処理データ量過多
**対処法**:
- バッチサイズを削減
- 処理を分割実行
- 不要データの削除

#### 4. データ不整合
**症状**: 件数の不一致
**原因**: 重複処理または欠損
**対処法**:
1. 実行ログの詳細確認
2. 手動での差分確認
3. 再処理の実行

### エラーコード一覧

| システム | エラーコード | 説明 | 対処法 |
|----------|-------------|------|--------|
| Lambda | 401 | JIRA認証エラー | APIトークン確認 |
| Lambda | 500 | 内部エラー | CloudWatchログ確認 |
| GAS | CSV_EMPTY | CSVファイルが空 | S3ファイル確認 |
| GAS | INVALID_COLUMNS | 列数不正 | データ形式確認 |
| GAS | RATE_LIMITED | API制限 | 実行間隔調整 |

### 緊急時対応

#### システム停止時
1. **即座の対応**:
   ```bash
   # Lambda停止
   aws lambda put-function-configuration \
     --function-name jira-csv-exporter \
     --environment "Variables={}"
   
   # GASトリガー停止
   # スプレッドシートのメニューから手動停止
   ```

2. **復旧手順**:
   - 問題箇所の特定・修正
   - 段階的なシステム再開
   - データ整合性の確認

#### データ破損時
1. **被害状況確認**:
   - S3バックアップからの復元
   - スプレッドシート履歴の確認

2. **復旧作業**:
   - バックアップデータの適用
   - 手動でのデータ修正
   - 再処理の実行

## 💰 コスト管理

### AWS利用料金
- **Lambda**: 月額 $1-5（実行時間による）
- **S3**: 月額 $1-3（ストレージ使用量による）
- **CloudWatch**: 月額 $1-2（ログ量による）

### 最適化施策
- 不要な日次ファイルの定期削除
- Lambda実行時間の最適化
- ログ保存期間の調整

## 📚 関連リソース

### 技術ドキュメント
- [Google Apps Script Documentation](https://developers.google.com/apps-script)
- [JIRA REST API Documentation](https://developer.atlassian.com/cloud/jira/platform/rest/v2/intro/)
- [Slack Web API](https://api.slack.com/web)
- [AWS Lambda Documentation](https://docs.aws.amazon.com/lambda/)

### 社内リソース
- **JIRAプロジェクト**: SUP
- **Slackチャンネル**: #task_runner
- **担当チーム**: テクニカルサポート部
- **AWS環境**: Production Account

### 運用連絡先
- **システム管理者**: [管理者名] - [email]
- **業務担当者**: [担当者名] - [email]
- **緊急連絡先**: [連絡先] - [phone]

## 📋 更新履歴

| 日付 | バージョン | 変更内容 | 担当者 |
|------|------------|----------|--------|
| 2025-07-16 | 2.0.0 | Lambda統合・全体統合版作成 | システム管理者 |
| 2025-07-14 | 1.0.0 | 初版作成（個別システム） | システム管理者 |

---

> **重要**: このシステムは顧客情報を含むため、セキュリティガイドラインに従って運用してください。APIトークンの定期更新、アクセス権限の最小化、監査ログの定期確認を実施してください。機密情報はプレースホルダーに置き換えています。
