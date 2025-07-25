import os
import requests
import json
from dotenv import load_dotenv

# .envファイルを読み込み
load_dotenv()

def get_custom_fields():
    """
    JIRAのカスタムフィールド一覧を取得して、必要なフィールドIDを特定する
    """
    jira_url = os.getenv('JIRA_URL').rstrip('/')
    username = os.getenv('JIRA_USERNAME')
    api_token = os.getenv('JIRA_API_TOKEN')
    
    if not all([jira_url, username, api_token]):
        print("❌ .envファイルにJIRA設定が必要です")
        return
    
    session = requests.Session()
    session.auth = (username, api_token)
    session.headers.update({
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    })
    
    print("🔍 カスタムフィールド一覧を取得中...")
    
    try:
        # カスタムフィールド一覧を取得
        response = session.get(f"{jira_url}/rest/api/2/field")
        
        if response.status_code != 200:
            print(f"❌ フィールド取得エラー: {response.status_code}")
            return
        
        fields = response.json()
        custom_fields = [f for f in fields if f['id'].startswith('customfield_')]
        
        print(f"\n📋 カスタムフィールド ({len(custom_fields)}件):")
        print("=" * 80)
        
        # 必要なフィールド名
        target_fields = {
            '機能分類': 'Function',
            '問合せ分類': 'Inquiry', 
            'TS': 'TS',
            'TS ID': 'TS',
            'TOKEN': 'TOKEN'
        }
        
        found_fields = {}
        
        for field in custom_fields:
            field_id = field['id']
            field_name = field['name']
            
            print(f"ID: {field_id:20} | 名前: {field_name}")
            
            # 必要なフィールドかチェック
            for target_key, target_value in target_fields.items():
                if (target_key in field_name or 
                    target_value.lower() in field_name.lower() or
                    field_name.lower() in target_key.lower()):
                    found_fields[field_name] = field_id
        
        print("\n" + "=" * 80)
        print("🎯 推奨フィールドマッピング:")
        print("=" * 80)
        
        if found_fields:
            for name, field_id in found_fields.items():
                print(f"'{name}' → {field_id}")
        else:
            print("⚠️  自動検出できませんでした。手動で確認してください。")
        
        print("\n📝 コード更新用:")
        print("=" * 50)
        print("以下のフィールドIDを simple_manual_jira_exporter.py と")
        print("simple_lambda_jira_exporter.py の customfield_XXXXX 部分に設定してください:")
        print()
        
        if found_fields:
            field_list = list(found_fields.values())
            for i, field_id in enumerate(field_list[:5]):  # 最大5個
                print(f"'customfield_{10001 + i}' → '{field_id}'  # {list(found_fields.keys())[i]}")
        else:
            print("# 手動で以下のように設定してください:")
            print("'customfield_10001' → 'customfield_XXXXX'  # 機能分類 (Function)")
            print("'customfield_10002' → 'customfield_XXXXX'  # 問合せ分類 (Inquiry)")
            print("'customfield_10003' → 'customfield_XXXXX'  # TS")
            print("'customfield_10004' → 'customfield_XXXXX'  # TS ID")
            print("'customfield_10005' → 'customfield_XXXXX'  # TOKEN")
        
        print(f"\n💾 全フィールド情報をファイルに保存: custom_fields.json")
        
        # JSON ファイルに保存
        with open('custom_fields.json', 'w', encoding='utf-8') as f:
            json.dump({
                'all_fields': fields,
                'custom_fields_only': custom_fields,
                'found_target_fields': found_fields
            }, f, indent=2, ensure_ascii=False)
        
        print("\n🔧 次のステップ:")
        print("1. 上記のフィールドIDをコードに反映")
        print("2. python simple_manual_jira_exporter.py でテスト実行")
        print("3. CSVの出力内容を確認")
        
    except Exception as e:
        print(f"❌ エラー: {str(e)}")


def test_custom_field_values():
    """
    SUPプロジェクトの1件の課題からカスタムフィールドの値を確認
    """
    jira_url = os.getenv('JIRA_URL').rstrip('/')
    username = os.getenv('JIRA_USERNAME')
    api_token = os.getenv('JIRA_API_TOKEN')
    
    session = requests.Session()
    session.auth = (username, api_token)
    session.headers.update({
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    })
    
    print("\n🧪 サポートプロジェクトのサンプル課題を確認中...")
    
    try:
        # サポートプロジェクトの課題を1件取得
        response = session.get(
            f"{jira_url}/rest/api/2/search",
            params={'jql': 'project = SUPPORT', 'maxResults': 1, 'fields': '*all'}
        )
        
        if response.status_code != 200:
            print(f"❌ 課題取得エラー: {response.status_code}")
            return
        
        data = response.json()
        issues = data.get('issues', [])
        
        if not issues:
            print("❌ サポートプロジェクトに課題が見つかりません")
            return
        
        issue = issues[0]
        fields = issue.get('fields', {})
        
        print(f"📄 サンプル課題: {issue['key']} - {fields.get('summary', '')}")
        print("\n📋 カスタムフィールドの値:")
        print("=" * 60)
        
        for field_id, field_value in fields.items():
            if field_id.startswith('customfield_') and field_value is not None:
                print(f"{field_id}: {field_value}")
        
        print(f"\n💾 サンプル課題の詳細をファイルに保存: sample_issue.json")
        
        with open('sample_issue.json', 'w', encoding='utf-8') as f:
            json.dump(issue, f, indent=2, ensure_ascii=False, default=str)
            
    except Exception as e:
        print(f"❌ エラー: {str(e)}")


if __name__ == "__main__":
    print("🔧 JIRA カスタムフィールド調査ツール")
    print("=" * 50)
    
    # カスタムフィールド一覧取得
    get_custom_fields()
    
    # SUPプロジェクトのサンプル確認
    test_custom_field_values()