import os
import csv
import requests
from datetime import datetime
from typing import List, Dict
import logging
from dotenv import load_dotenv

# .envファイルを読み込み
load_dotenv()

class JiraCSVExporter:
    def __init__(self):
        """
        環境変数から設定を読み込む JIRA CSV エクスポーター
        """
        self.jira_url = os.getenv('JIRA_URL').rstrip('/')
        self.username = os.getenv('JIRA_USERNAME')
        self.api_token = os.getenv('JIRA_API_TOKEN')
        
        # 設定チェック
        if not all([self.jira_url, self.username, self.api_token]):
            raise ValueError("JIRA_URL, JIRA_USERNAME, JIRA_API_TOKEN を .env ファイルに設定してください")
        
        # リクエストセッション設定
        self.session = requests.Session()
        self.session.auth = (self.username, self.api_token)
        self.session.headers.update({
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        })
        
        # ログ設定
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
    
    def test_connection(self) -> bool:
        """JIRA接続テスト"""
        try:
            response = self.session.get(f"{self.jira_url}/rest/api/2/myself")
            if response.status_code == 200:
                user_info = response.json()
                self.logger.info(f"✓ JIRA接続成功: {user_info.get('displayName', 'Unknown')}")
                return True
            else:
                self.logger.error(f"✗ JIRA接続失敗: {response.status_code}")
                return False
        except Exception as e:
            self.logger.error(f"✗ JIRA接続エラー: {str(e)}")
            return False
    
    def get_projects(self) -> List[Dict]:
        """利用可能なプロジェクト一覧を取得"""
        try:
            response = self.session.get(f"{self.jira_url}/rest/api/2/project")
            if response.status_code == 200:
                projects = response.json()
                self.logger.info(f"✓ プロジェクト取得成功: {len(projects)}件")
                return projects
            else:
                self.logger.error(f"✗ プロジェクト取得失敗: {response.status_code}")
                return []
        except Exception as e:
            self.logger.error(f"✗ プロジェクト取得エラー: {str(e)}")
            return []
    
    def search_issues(self, jql: str, max_results: int = 1000) -> List[Dict]:
        """JQLクエリで課題を検索（サポートプロジェクト用カスタムフィールド対応）"""
        # サポートプロジェクト専用 - 15フィールドのみ取得
        fields = [
            'issuetype',           # 課題タイプ
            'summary',             # 要約
            'reporter',            # 報告者
            'assignee',            # 担当者
            'priority',            # 優先度
            'status',              # ステータス
            'resolution',          # 解決状況
            'created',             # 作成日
            'resolutiondate',      # 解決日
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
                response = self.session.get(
                    f"{self.jira_url}/rest/api/2/search",
                    params=params
                )
                
                if response.status_code != 200:
                    self.logger.error(f"✗ 検索エラー: {response.status_code}")
                    break
                
                data = response.json()
                issues = data.get('issues', [])
                
                if not issues:
                    break
                
                all_issues.extend(issues)
                self.logger.info(f"取得中: {len(all_issues)} / {data.get('total', 0)}")
                
                if len(all_issues) >= data.get('total', 0) or len(all_issues) >= max_results:
                    break
                
                start_at += len(issues)
                
            except Exception as e:
                self.logger.error(f"✗ 検索エラー: {str(e)}")
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
    
    def export_to_csv(self, issues: List[Dict], filename: str = None) -> str:
        """課題をCSVファイルにエクスポート（サポートプロジェクト専用 16列）"""
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"SUPPORT_project_export_{timestamp}.csv"
        
        if not issues:
            self.logger.warning("エクスポートする課題がありません")
            return filename
        
        # サポートプロジェクト専用ヘッダー（15列）- 指定された順番
        headers = [
            '課題タイプ',           # 1
            '課題キー',             # 2
            '課題ID',              # 3
            '要約',                # 4
            '機能分類 (Function)',  # 5
            '問合せ分類 (Inquiry)', # 6
            '報告者',              # 7
            'TS',                 # 8
            '担当者',              # 9
            '優先度',              # 10
            'ステータス',           # 11
            '解決状況',            # 12
            '作成日',              # 13
            '解決日',              # 14
            'TOKEN'               # 15
        ]
        
        try:
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(headers)
                
                for issue in issues:
                    fields = issue.get('fields', {})
                    
                    # サポートプロジェクト専用データ行（15列）- 指定された順番
                    row = [
                        self.format_field_value(fields.get('issuetype'), 'issuetype'),     # 1. 課題タイプ
                        issue.get('key', ''),                                              # 2. 課題キー
                        issue.get('id', ''),                                               # 3. 課題ID
                        fields.get('summary', ''),                                         # 4. 要約
                        self.format_field_value(fields.get('customfield_10141')),         # 5. 機能分類 (Function)
                        self.format_field_value(fields.get('customfield_10140')),         # 6. 問合せ分類 (Inquiry)
                        self.format_field_value(fields.get('reporter'), 'user'),          # 7. 報告者
                        self.format_field_value(fields.get('customfield_10129'), 'user'), # 8. TS（ユーザー型）
                        self.format_field_value(fields.get('assignee'), 'user'),          # 9. 担当者
                        self.format_field_value(fields.get('priority'), 'priority'),      # 10. 優先度
                        self.format_field_value(fields.get('status'), 'status'),          # 11. ステータス
                        self.format_field_value(fields.get('resolution'), 'resolution'),  # 12. 解決状況
                        self.format_field_value(fields.get('created'), 'datetime'),       # 13. 作成日
                        self.format_field_value(fields.get('resolutiondate'), 'datetime'), # 14. 解決日
                        self.format_field_value(fields.get('customfield_10163'))          # 15. TOKEN
                    ]
                    
                    writer.writerow(row)
            
            self.logger.info(f"✓ CSVエクスポート完了: {filename} ({len(issues)}件, 15列)")
            return filename
            
        except Exception as e:
            self.logger.error(f"✗ CSVエクスポートエラー: {str(e)}")
            raise


def main():
    """メイン実行関数"""
    print("=== サポートプロジェクト専用 JIRA CSV Export Tool ===")
    print()
    
    try:
        # エクスポーター初期化
        exporter = JiraCSVExporter()
        
        # 接続テスト
        if not exporter.test_connection():
            print("JIRA接続に失敗しました。.envファイルの設定を確認してください。")
            return
        
        # プロジェクト一覧表示
        projects = exporter.get_projects()
        if projects:
            print("\n利用可能なプロジェクト:")
            for i, project in enumerate(projects[:10], 1):
                print(f"{i:2d}. {project['key']} - {project['name']}")
            if len(projects) > 10:
                print(f"    ... 他 {len(projects) - 10} 件")
        
        print("\n" + "="*50)
        
        # JQLクエリ例（サポートプロジェクト専用）
        jql_examples = {
            "1": ("サポートプロジェクトの全課題", "project = SUPPORT"),
            "2": ("サポートプロジェクトの未完了課題", "project = SUPPORT AND status != Done AND status != Closed"),
            "3": ("サポートプロジェクトの完了課題", "project = SUPPORT AND status = Done"),
            "4": ("サポートプロジェクトの今月の課題", "project = SUPPORT AND created >= -30d"),
            "5": ("サポートプロジェクトの過去7日間の課題", "project = SUPPORT AND created >= -7d"),
            "6": ("カスタムJQLを入力", "custom")
        }
        
        print("エクスポートしたいデータを選択してください:")
        for key, (description, _) in jql_examples.items():
            print(f"{key}. {description}")
        
        choice = input("\n選択 (1-6): ").strip()
        
        if choice in jql_examples:
            if choice == "6":
                jql = input("JQLクエリを入力してください: ").strip()
            else:
                jql = jql_examples[choice][1]
                print(f"実行するJQLクエリ: {jql}")
        else:
            print("無効な選択です。サポートプロジェクトの全課題を取得します。")
            jql = "project = SUPPORT"
        
        print("\n検索中...")
        
        # 課題検索（サポートプロジェクトの場合は制限を緩和）
        max_results = 5000  # サポートプロジェクトの全データを取得
        issues = exporter.search_issues(jql, max_results=max_results)
        
        if not issues:
            print("該当する課題が見つかりませんでした。")
            return
        
        print(f"\n{len(issues)}件の課題が見つかりました。")
        
        # ファイル名入力
        default_filename = f"SUPPORT_project_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        filename = input(f"ファイル名を入力してください (デフォルト: {default_filename}): ").strip()
        
        if not filename:
            filename = default_filename
        
        # CSVエクスポート
        print("\nエクスポート中...")
        result_filename = exporter.export_to_csv(issues, filename)
        
        print(f"\n✓ エクスポート完了!")
        print(f"  ファイル: {result_filename}")
        print(f"  件数: {len(issues)}件")
        print(f"  列数: 15列（サポートプロジェクト専用フォーマット）")
        print(f"  実行時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
    except KeyboardInterrupt:
        print("\n処理を中断しました。")
    except Exception as e:
        print(f"\nエラーが発生しました: {str(e)}")


if __name__ == "__main__":
    main()