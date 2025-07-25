import os
import csv
import json
import urllib.request
import urllib.error
import urllib.parse
import base64
import boto3
from datetime import datetime
from typing import List, Dict
import logging
from io import StringIO

# Lambda用ロガー設定
logger = logging.getLogger()
logger.setLevel(logging.INFO)

class LambdaJiraS3Exporter:
    def __init__(self):
        """
        環境変数から設定を読み込む Lambda用 JIRA→S3 エクスポーター
        """
        self.jira_url = os.environ.get('JIRA_URL', '').rstrip('/')
        self.username = os.environ.get('JIRA_USERNAME', '')
        self.api_token = os.environ.get('JIRA_API_TOKEN', '')
        
        # S3設定
        self.s3_bucket = os.environ.get('S3_BUCKET', '')
        self.s3_prefix = os.environ.get('S3_PREFIX', 'project-exports/')
        
        # 設定チェック
        if not all([self.jira_url, self.username, self.api_token]):
            raise ValueError("JIRA_URL, JIRA_USERNAME, JIRA_API_TOKEN を環境変数に設定してください")
        
        # AWS S3クライアント
        self.s3_client = boto3.client('s3') if self.s3_bucket else None
        
        # Basic認証のヘッダー作成
        credentials = f"{self.username}:{self.api_token}"
        encoded_credentials = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')
        self.auth_header = f"Basic {encoded_credentials}"
    
    def test_connection(self) -> bool:
        """JIRA接続テスト"""
        try:
            req = urllib.request.Request(f"{self.jira_url}/rest/api/2/myself")
            req.add_header('Authorization', self.auth_header)
            req.add_header('Accept', 'application/json')
            
            with urllib.request.urlopen(req) as response:
                if response.status == 200:
                    user_info = json.loads(response.read().decode('utf-8'))
                    logger.info(f"JIRA接続成功: {user_info.get('displayName', 'Unknown')}")
                    return True
                else:
                    logger.error(f"JIRA接続失敗: {response.status}")
                    return False
        except Exception as e:
            logger.error(f"JIRA接続エラー: {str(e)}")
            return False
    
    def search_issues(self, jql: str, max_results: int = 1000) -> List[Dict]:
        """JQLクエリで課題を検索（サポートプロジェクト用カスタムフィールド対応）"""
        # サポートプロジェクト専用 - 10フィールドのみ取得
        fields = [
            'issuetype',           # 課題タイプ
            'summary',             # 要約
            'reporter',            # 報告者
            'assignee',            # 担当者
            'priority',            # 優先度
            'created',             # 作成日
            # サポート専用カスタムフィールド
            'customfield_10141',   # 機能分類 (Function)
            'customfield_10140',   # 問合せ分類 (Inquiry)
            'customfield_10129',   # TS
            'customfield_10163'    # TOKEN
        ]
        
        all_issues = []
        start_at = 0
        
        while True:
            params = {
                'jql': jql,
                'fields': ','.join(fields),
                'maxResults': min(100, max_results - len(all_issues)),
                'startAt': start_at
            }
            
            try:
                # URLパラメータを構築
                query_string = urllib.parse.urlencode(params)
                url = f"{self.jira_url}/rest/api/2/search?{query_string}"
                
                req = urllib.request.Request(url)
                req.add_header('Authorization', self.auth_header)
                req.add_header('Accept', 'application/json')
                
                with urllib.request.urlopen(req) as response:
                    if response.status != 200:
                        logger.error(f"検索エラー: {response.status}")
                        break
                    
                    data = json.loads(response.read().decode('utf-8'))
                    issues = data.get('issues', [])
                
                    if not issues:
                        break
                    
                    all_issues.extend(issues)
                    logger.info(f"取得中: {len(all_issues)} / {data.get('total', 0)}")
                    
                    if len(all_issues) >= data.get('total', 0) or len(all_issues) >= max_results:
                        break
                    
                    start_at += len(issues)
                    
            except Exception as e:
                logger.error(f"検索エラー: {str(e)}")
                break
        
        return all_issues
    
    def format_field_value(self, field_value, field_type: str = 'string') -> str:
        """フィールド値をCSV用にフォーマット（サポートプロジェクト用拡張）"""
        if field_value is None:
            return ''
        
        if field_type == 'user':
            return field_value.get('displayName', '') if isinstance(field_value, dict) else str(field_value)
        elif field_type == 'status':
            return field_value.get('name', '') if isinstance(field_value, dict) else str(field_value)
        elif field_type == 'priority':
            return field_value.get('name', '') if isinstance(field_value, dict) else str(field_value)
        elif field_type == 'issuetype':
            return field_value.get('name', '') if isinstance(field_value, dict) else str(field_value)
        elif field_type == 'resolution':
            return field_value.get('name', '') if isinstance(field_value, dict) else str(field_value)
        elif field_type == 'datetime':
            if field_value:
                try:
                    dt = datetime.fromisoformat(field_value.replace('Z', '+00:00'))
                    return dt.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    return str(field_value)
            return ''
        else:
            # カスタムフィールドやその他のフィールド
            if isinstance(field_value, dict):
                # オブジェクト型のカスタムフィールド（選択肢など）
                if 'value' in field_value:
                    return str(field_value['value'])
                elif 'name' in field_value:
                    return str(field_value['name'])
                elif 'displayName' in field_value:
                    return str(field_value['displayName'])
                else:
                    return str(field_value)
            elif isinstance(field_value, list):
                # 配列型のカスタムフィールド（マルチセレクトなど）
                return ', '.join([str(item.get('value', item.get('name', item))) if isinstance(item, dict) else str(item) for item in field_value])
            else:
                return str(field_value)
    
    def issues_to_csv_string(self, issues: List[Dict]) -> str:
        """課題をCSV文字列に変換"""
        if not issues:
            return ""
        
        # サポートプロジェクト専用ヘッダー（11列）- 指定された順番
        headers = [
            '課題タイプ',
            '課題キー', 
            '課題ID',
            '要約',
            '機能分類 (Function)',
            '問合せ分類 (Inquiry)',
            '報告者',
            'TS',
            '担当者',
            '優先度',
            '作成日',
            'TOKEN'
        ]
        
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(headers)
        
        for issue in issues:
            fields = issue.get('fields', {})
            
            # 指定された順番でデータ行を作成
            row = [
                self.format_field_value(fields.get('issuetype'), 'issuetype'),     # 課題タイプ
                issue.get('key', ''),                                              # 課題キー
                issue.get('id', ''),                                               # 課題ID
                fields.get('summary', ''),                                         # 要約
                self.format_field_value(fields.get('customfield_10141')),         # 機能分類 (Function)
                self.format_field_value(fields.get('customfield_10140')),         # 問合せ分類 (Inquiry)
                self.format_field_value(fields.get('reporter'), 'user'),          # 報告者
                self.format_field_value(fields.get('customfield_10129'), 'user'), # TS（ユーザー型）
                self.format_field_value(fields.get('assignee'), 'user'),          # 担当者
                self.format_field_value(fields.get('priority'), 'priority'),      # 優先度
                self.format_field_value(fields.get('created'), 'datetime'),       # 作成日
                self.format_field_value(fields.get('customfield_10163'))          # TOKEN
            ]
            
            writer.writerow(row)
        
        return output.getvalue()
    
    def issues_to_daily_csv_string(self, issues: List[Dict]) -> str:
        """課題を日次CSV文字列に変換（メタデータ付き）"""
        if not issues:
            return create_daily_csv_header()
        
        # 日次CSV用ヘッダー（日付情報を追加）
        headers = [
            '作成日', '年', '月', '日', 'エクスポート日',  # 日次メタデータ
            '課題タイプ', '課題キー', '課題ID', '要約',
            '機能分類 (Function)', '問合せ分類 (Inquiry)', '報告者', 'TS',
            '担当者', '優先度', '作成日時', 'TOKEN'
        ]
        
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(headers)
        
        for issue in issues:
            fields = issue.get('fields', {})
            date_info = issue.get('date_info', {})
            
            # 日次メタデータ + 課題データの行を作成
            row = [
                date_info.get('date_label', ''),           # 作成日
                date_info.get('year', ''),                 # 年
                date_info.get('month', ''),                # 月
                date_info.get('day', ''),                  # 日
                date_info.get('export_date', ''),          # エクスポート日
                self.format_field_value(fields.get('issuetype'), 'issuetype'),     # 課題タイプ
                issue.get('key', ''),                                              # 課題キー
                issue.get('id', ''),                                               # 課題ID
                fields.get('summary', ''),                                         # 要約
                self.format_field_value(fields.get('customfield_10141')),         # 機能分類 (Function)
                self.format_field_value(fields.get('customfield_10140')),         # 問合せ分類 (Inquiry)
                self.format_field_value(fields.get('reporter'), 'user'),          # 報告者
                self.format_field_value(fields.get('customfield_10129'), 'user'), # TS（ユーザー型）
                self.format_field_value(fields.get('assignee'), 'user'),          # 担当者
                self.format_field_value(fields.get('priority'), 'priority'),      # 優先度
                self.format_field_value(fields.get('created'), 'datetime'),       # 作成日時
                self.format_field_value(fields.get('customfield_10163'))          # TOKEN
            ]
            
            writer.writerow(row)
        
        return output.getvalue()
    
    
    def upload_latest_to_s3(self, csv_content: str) -> str:
        """S3に最新CSVファイル（固定名）をアップロード"""
        if not self.s3_client or not self.s3_bucket:
            logger.warning("S3設定が不完全です")
            return ""
        
        try:
            latest_key = f"{self.s3_prefix}latest.csv"
            
            self.s3_client.put_object(
                Bucket=self.s3_bucket,
                Key=latest_key,
                Body=csv_content.encode('utf-8'),
                ContentType='text/csv',
                ContentEncoding='utf-8',
                # 公開読み取り権限はバケットポリシーで設定済み
                Metadata={
                    'last_updated': datetime.now().isoformat(),
                    'data_type': 'latest_snapshot'
                }
            )
            
            latest_url = f"https://{self.s3_bucket}.s3.amazonaws.com/{latest_key}"
            logger.info(f"最新ファイルS3アップロード完了: {latest_url}")
            
            return latest_url
            
        except Exception as e:
            logger.error(f"最新ファイルS3アップロードエラー: {str(e)}")
            return ""
    
    def upload_daily_to_s3(self, csv_content: str, filename: str, year: int, month: int, day: int) -> str:
        """S3に日次CSVファイルをアップロード"""
        if not self.s3_client or not self.s3_bucket:
            logger.warning("S3設定が不完全です")
            return ""
        
        try:
            # 日次ファイル用のキー
            daily_key = f"{self.s3_prefix}daily/{filename}"
            
            self.s3_client.put_object(
                Bucket=self.s3_bucket,
                Key=daily_key,
                Body=csv_content.encode('utf-8'),
                ContentType='text/csv',
                ContentEncoding='utf-8',
                # 公開読み取り権限はバケットポリシーで設定済み
                # メタデータを追加
                Metadata={
                    'year': str(year),
                    'month': str(month),
                    'day': str(day),
                    'export_date': datetime.now().strftime('%Y-%m-%d'),
                    'data_type': 'daily_created'
                }
            )
            
            # 日次ファイルのURLを返す
            daily_url = f"https://{self.s3_bucket}.s3.amazonaws.com/{daily_key}"
            logger.info(f"日次S3アップロード完了: {daily_url}")
            
            return daily_url
            
        except Exception as e:
            logger.error(f"日次S3アップロードエラー: {str(e)}")
            return ""
    


def lambda_handler(event, context):
    """Lambda関数のエントリーポイント（前日作成課題取得版）"""
    
    try:
        # 前日作成された課題を取得
        jql = 'project = "SUPPORT" AND created >= startOfDay(-1) AND created < startOfDay() ORDER BY created ASC'
        max_results = 5000
        
        # 前日の日付情報を取得
        import datetime
        today = datetime.datetime.now()
        # 前日の日付を計算
        yesterday = today - datetime.timedelta(days=1)
        year = yesterday.year
        month = yesterday.month
        day = yesterday.day
        
        # ファイル名：前日作成課題用
        filename = f"SUPPORT_created_{year}{month:02d}{day:02d}.csv"
        
        logger.info(f"前日作成課題取得開始 - JQLクエリ: {jql}")
        logger.info(f"対象期間: {year}年{month}月{day}日")
        logger.info(f"日次ファイル名: {filename}")
        
        # エクスポーター初期化
        exporter = LambdaJiraS3Exporter()
        
        # 接続テスト
        if not exporter.test_connection():
            raise Exception("JIRA接続に失敗しました")
        
        # 課題検索
        issues = exporter.search_issues(jql, max_results)
        
        # 日次データにメタデータを追加
        daily_data = []
        if issues:
            for issue in issues:
                # 各課題に日付情報を追加
                issue['date_info'] = {
                    'year': year,
                    'month': month,
                    'day': day,
                    'export_date': today.strftime('%Y-%m-%d'),
                    'date_label': f"{year}年{month}月{day}日"
                }
                daily_data.append(issue)
        
        logger.info(f"前日作成課題: {len(daily_data)}件")
        
        if not daily_data:
            logger.warning("前日作成された課題が見つかりませんでした")
            # 空データでもファイルを作成（ヘッダーのみ）
            empty_csv = create_daily_csv_header()
            daily_url = exporter.upload_daily_to_s3(empty_csv, filename, year, month, day)
            
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': '前日作成された課題が見つかりませんでした',
                    'issue_count': 0,
                    'date_info': f"{year}年{month}月{day}日",
                    'jql': jql,
                    'daily_filename': filename,
                    'daily_csv_url': daily_url,
                    'timestamp': today.isoformat()
                }, ensure_ascii=False)
            }
        
        # 日次CSV作成（メタデータ付き）
        daily_csv_content = exporter.issues_to_daily_csv_string(daily_data)
        
        # 標準CSV作成（Google Apps Script用）
        standard_csv_content = exporter.issues_to_csv_string(daily_data)
        
        # S3アップロード（日次ファイル）
        daily_url = exporter.upload_daily_to_s3(daily_csv_content, filename, year, month, day)
        
        # S3アップロード（最新ファイル）
        latest_url = exporter.upload_latest_to_s3(standard_csv_content)
        
        logger.info(f"日次エクスポート完了: {len(daily_data)}件")
        
        # レスポンス
        response_body = {
            'message': f'{year}年{month}月{day}日に作成されたサポート課題をS3にアップロードしました',
            'issue_count': len(daily_data),
            'date_info': f"{year}年{month}月{day}日",
            'daily_filename': filename,
            'daily_csv_url': daily_url,
            'latest_csv_url': latest_url,
            'note': 'Google Apps Scriptが前日作成課題データを取得してGoogle Sheetsに追記します',
            'jql': jql,
            'date_range': '前日作成課題（前日00:00〜23:59）',
            'timestamp': today.isoformat()
        }
        
        return {
            'statusCode': 200,
            'body': json.dumps(response_body, ensure_ascii=False)
        }
        
    except Exception as e:
        error_message = f"エラーが発生しました: {str(e)}"
        logger.error(error_message)
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': error_message,
                'timestamp': datetime.now().isoformat()
            })
        }


def create_daily_csv_header():
    """日次CSV用のヘッダーのみのCSVを作成"""
    headers = [
        '作成日', '年', '月', '日', 'エクスポート日',
        '課題タイプ', '課題キー', '課題ID', '要約',
        '機能分類 (Function)', '問合せ分類 (Inquiry)', '報告者', 'TS',
        '担当者', '優先度', '作成日時', 'TOKEN'
    ]
    return ','.join(headers) + '\n'



# ローカルテスト用
if __name__ == "__main__":
    # 自動実行テスト用のイベント（空でOK）
    test_event = {}
    
    # ローカル実行
    result = lambda_handler(test_event, None)
    print(json.dumps(result, indent=2, ensure_ascii=False))