/**
 * サポートJIRA課題データ自動取得・更新スクリプト
 * S3からCSVデータを取得してGoogle Sheetsに転記
 * 毎日朝7時に自動実行
 */

// 設定値
const CONFIG = {
  // S3の固定CSVファイルURL
  CSV_URL: 'https://your-company-exports.s3.amazonaws.com/project-exports/latest.csv',
  
  // Google SheetsのスプレッドシートID
  SPREADSHEET_ID: 'YOUR_SPREADSHEET_ID',
  
  // ワークシート名
  WORKSHEET_NAME: 'サポート課題データ',
  
  // ログ用ワークシート名
  LOG_WORKSHEET_NAME: 'ログ',
  
  // リトライ設定
  MAX_RETRIES: 3,
  RETRY_DELAY: 1000 // ミリ秒
};

/**
 * エラーハンドリング付きHTTPリクエスト
 */
function fetchWithRetry(url, retries = CONFIG.MAX_RETRIES) {
  for (let i = 0; i < retries; i++) {
    try {
      const response = UrlFetchApp.fetch(url, {
        muteHttpExceptions: true,
        headers: {
          'User-Agent': 'GoogleAppsScript-JIRASync/1.0'
        }
      });
      
      if (response.getResponseCode() === 200) {
        return response;
      } else {
        throw new Error(`HTTP ${response.getResponseCode()}: ${response.getContentText()}`);
      }
    } catch (error) {
      console.log(`取得試行 ${i + 1}/${retries} 失敗: ${error.message}`);
      if (i === retries - 1) throw error;
      Utilities.sleep(CONFIG.RETRY_DELAY * (i + 1)); // 指数バックオフ
    }
  }
}

/**
 * CSVデータの検証
 */
function validateData(data) {
  if (!data || data.length < 2) {
    throw new Error('CSVデータが空または不正です');
  }
  
  const expectedColumns = 12;
  if (data[0].length !== expectedColumns) {
    throw new Error(`列数が期待値(${expectedColumns})と異なります: ${data[0].length}`);
  }
  
  return true;
}

/**
 * S3からCSVデータを取得してGoogle Sheetsを更新
 */
function updateSheetsFromS3() {
  const startTime = new Date();
  let status = 'SUCCESS';
  let message = '';
  let rowCount = 0;
  
  try {
    console.log('S3からCSVデータ取得開始...');
    
    // S3からCSVデータを取得
    const response = fetchWithRetry(CONFIG.CSV_URL);
    const csvText = response.getContentText('UTF-8');
    
    if (!csvText.trim()) {
      throw new Error('CSVファイルが空です');
    }
    
    // CSVをパース
    const csvData = Utilities.parseCsv(csvText);
    validateData(csvData);
    
    console.log(`CSVデータ取得完了: ${csvData.length}行`);
    
    // スプレッドシートを開く
    const spreadsheet = SpreadsheetApp.openById(CONFIG.SPREADSHEET_ID);
    
    // データシートの準備
    let dataSheet;
    try {
      dataSheet = spreadsheet.getSheetByName(CONFIG.WORKSHEET_NAME);
    } catch (e) {
      dataSheet = spreadsheet.insertSheet(CONFIG.WORKSHEET_NAME);
    }
    
    // 既存データの確認
    const existingRows = dataSheet.getLastRow();
    let isNewSheet = existingRows === 0;
    
    // 新しいシートの場合はヘッダーを追加
    if (isNewSheet && csvData.length > 0) {
      const headerRange = dataSheet.getRange(1, 1, 1, csvData[0].length);
      headerRange.setValues([csvData[0]]);
      headerRange.setFontWeight('bold');
      headerRange.setBackground('#f0f0f0');
      
      // 列幅の自動調整
      dataSheet.autoResizeColumns(1, csvData[0].length);
    }
    
    // データを追記（ヘッダーを除く）
    if (csvData.length > 1) {
      const dataRows = csvData.slice(1); // ヘッダーを除く
      
      // 重複チェック（課題キーで判定）
      let newDataRows = dataRows;
      if (existingRows > 1) {
        // 既存データの課題キーを取得（B列：課題キー）
        const existingData = dataSheet.getRange(2, 2, existingRows - 1, 1).getValues();
        const existingKeys = existingData.map(row => row[0]);
        
        // 新しいデータから重複を除外
        newDataRows = dataRows.filter(row => !existingKeys.includes(row[1])); // B列が課題キー
      }
      
      if (newDataRows.length > 0) {
        const startRow = existingRows + 1;
        const range = dataSheet.getRange(startRow, 1, newDataRows.length, newDataRows[0].length);
        range.setValues(newDataRows);
        
        rowCount = newDataRows.length;
      } else {
        rowCount = 0;
      }
    }
    
    if (rowCount > 0) {
      message = `データ追記完了: ${rowCount}件の新規課題データ`;
    } else {
      message = `データ確認完了: 新規課題データはありませんでした`;
    }
    console.log(message);
    
  } catch (error) {
    status = 'ERROR';
    message = `エラー: ${error.message}`;
    console.error(message);
    console.error(error.stack);
  }
  
  // ログを記録
  logExecution(startTime, new Date(), status, message, rowCount);
  
  return {
    status: status,
    message: message,
    rowCount: rowCount,
    executionTime: new Date() - startTime
  };
}

/**
 * 実行ログをログシートに記録
 */
function logExecution(startTime, endTime, status, message, rowCount) {
  try {
    const spreadsheet = SpreadsheetApp.openById(CONFIG.SPREADSHEET_ID);
    
    // ログシートの準備
    let logSheet;
    try {
      logSheet = spreadsheet.getSheetByName(CONFIG.LOG_WORKSHEET_NAME);
    } catch (e) {
      logSheet = spreadsheet.insertSheet(CONFIG.LOG_WORKSHEET_NAME);
    }
    
    // ヘッダーが存在しない場合は追加
    if (logSheet.getLastRow() === 0) {
      logSheet.getRange(1, 1, 1, 6).setValues([
        ['実行日時', 'ステータス', 'メッセージ', '処理行数', '実行時間(秒)', 'CSV URL']
      ]);
      logSheet.getRange(1, 1, 1, 6).setFontWeight('bold').setBackground('#f0f0f0');
    }
    
    // ログエントリを追加
    const executionTimeSeconds = Math.round((endTime - startTime) / 1000);
    const logEntry = [
      startTime,
      status,
      message,
      rowCount,
      executionTimeSeconds,
      CONFIG.CSV_URL
    ];
    
    // 最後の行に追加
    const lastRow = logSheet.getLastRow();
    logSheet.getRange(lastRow + 1, 1, 1, 6).setValues([logEntry]);
    
    // 古いログを削除（最新100件まで保持）
    const maxRows = 101; // ヘッダー + 100件
    if (logSheet.getLastRow() > maxRows) {
      const rowsToDelete = logSheet.getLastRow() - maxRows;
      logSheet.deleteRows(maxRows + 1, rowsToDelete);
    }
    
  } catch (error) {
    console.error('ログ記録エラー:', error.message);
  }
}

/**
 * 設定確認用関数
 */
function checkConfiguration() {
  console.log('=== 設定確認 ===');
  console.log(`CSV URL: ${CONFIG.CSV_URL}`);
  console.log(`スプレッドシートID: ${CONFIG.SPREADSHEET_ID}`);
  console.log(`データシート名: ${CONFIG.WORKSHEET_NAME}`);
  console.log(`ログシート名: ${CONFIG.LOG_WORKSHEET_NAME}`);
  
  try {
    // スプレッドシートアクセステスト
    const spreadsheet = SpreadsheetApp.openById(CONFIG.SPREADSHEET_ID);
    console.log(`スプレッドシート名: ${spreadsheet.getName()}`);
    
    // CSV URLアクセステスト
    const response = UrlFetchApp.fetch(CONFIG.CSV_URL, { muteHttpExceptions: true });
    console.log(`CSV URLレスポンス: ${response.getResponseCode()}`);
    
    if (response.getResponseCode() === 200) {
      const csvText = response.getContentText('UTF-8');
      const csvData = Utilities.parseCsv(csvText);
      console.log(`CSVデータ行数: ${csvData.length}`);
      console.log(`CSVヘッダー: ${csvData[0].join(', ')}`);
    }
    
    console.log('設定確認完了 - 問題なし');
    return true;
  } catch (error) {
    console.error('設定エラー:', error.message);
    return false;
  }
}

/**
 * テスト実行用関数
 */
function testUpdate() {
  console.log('=== テスト実行開始 ===');
  const result = updateSheetsFromS3();
  console.log('=== テスト実行結果 ===');
  console.log(JSON.stringify(result, null, 2));
  return result;
}

/**
 * 定期実行トリガーのセットアップ
 */
function setupTrigger() {
  // 既存のトリガーを削除
  const triggers = ScriptApp.getProjectTriggers();
  triggers.forEach(trigger => {
    if (trigger.getHandlerFunction() === 'updateSheetsFromS3') {
      ScriptApp.deleteTrigger(trigger);
    }
  });
  
  // 新しいトリガーを作成（毎日朝7時）
  ScriptApp.newTrigger('updateSheetsFromS3')
    .timeBased()
    .everyDays(1)
    .atHour(7)
    .nearMinute(0)
    .create();
  
  console.log('定期実行トリガーを設定しました（毎日朝7:00）');
}

/**
 * トリガー削除用関数
 */
function deleteTriggers() {
  const triggers = ScriptApp.getProjectTriggers();
  triggers.forEach(trigger => {
    if (trigger.getHandlerFunction() === 'updateSheetsFromS3') {
      ScriptApp.deleteTrigger(trigger);
    }
  });
  console.log('すべてのトリガーを削除しました');
}

/**
 * 手動実行用関数（メニューから実行可能）
 */
function manualUpdate() {
  const ui = SpreadsheetApp.getUi();
  
  try {
    ui.alert('データ更新開始', 'S3からJIRAデータを取得してシートを更新します。', ui.ButtonSet.OK);
    
    const result = updateSheetsFromS3();
    
    if (result.status === 'SUCCESS') {
      ui.alert('更新完了', 
        `${result.message}\n実行時間: ${Math.round(result.executionTime / 1000)}秒`, 
        ui.ButtonSet.OK);
    } else {
      ui.alert('更新エラー', result.message, ui.ButtonSet.OK);
    }
    
  } catch (error) {
    ui.alert('エラー', `実行中にエラーが発生しました: ${error.message}`, ui.ButtonSet.OK);
  }
}

/**
 * データシートをクリア
 */
function clearDataSheet() {
  try {
    const spreadsheet = SpreadsheetApp.openById(CONFIG.SPREADSHEET_ID);
    const dataSheet = spreadsheet.getSheetByName(CONFIG.WORKSHEET_NAME);
    
    if (dataSheet) {
      dataSheet.clear();
      console.log('データシートをクリアしました');
    } else {
      console.log('データシートが見つかりません');
    }
  } catch (error) {
    console.error('データクリアエラー:', error.message);
  }
}

/**
 * カスタムメニューの作成
 */
function onOpen() {
  const ui = SpreadsheetApp.getUi();
  ui.createMenu('JIRA連携')
    .addItem('手動更新', 'manualUpdate')
    .addSeparator()
    .addItem('設定確認', 'checkConfiguration')
    .addItem('テスト実行', 'testUpdate')
    .addSeparator()
    .addItem('データクリア', 'clearDataSheet')
    .addSeparator()
    .addItem('トリガー設定', 'setupTrigger')
    .addItem('トリガー削除', 'deleteTriggers')
    .addToUi();
}