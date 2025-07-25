function joinSupDataWithSfdcKeepComments() {
  // スプレッドシートのIDを指定
  const spreadsheetId = "YOUR_SPREADSHEET_ID";
  const ss = SpreadsheetApp.openById(spreadsheetId);
  
  // 2つのシートを取得
  const supSheet = ss.getSheetByName("SUP課題データ");
  const sfdcSheet = ss.getSheetByName("sfdc");
  
  if (!supSheet || !sfdcSheet) {
    Logger.log("シートが見つかりません。シート名を確認してください。");
    return;
  }
  
  // フィルターをクリア
  if (supSheet.getFilter()) {
    supSheet.getFilter().remove();
  }
  if (sfdcSheet.getFilter()) {
    sfdcSheet.getFilter().remove();
  }
  
  // 結果シート名
  const resultSheetName = "JOIN結果_SUP_SFDC";
  let resultSheet = ss.getSheetByName(resultSheetName);
  
  // 既存のコメントを保存
  let existingComments = {};
  if (resultSheet) {
    const existingData = resultSheet.getDataRange().getValues();
    const existingHeaders = existingData[0];
    
    // 課題キーの列インデックスを取得
    const keyIndex = existingHeaders.indexOf("課題キー");
    const commentIndex = existingHeaders.indexOf("コメント");
    
    if (keyIndex !== -1 && commentIndex !== -1) {
      for (let i = 1; i < existingData.length; i++) {
        const key = existingData[i][keyIndex];
        const comment = existingData[i][commentIndex];
        if (key && comment) {
          existingComments[key] = comment;
        }
      }
    }
    
    // 既存シートを削除
    ss.deleteSheet(resultSheet);
  }
  
  // データを取得
  const supData = supSheet.getDataRange().getValues();
  const sfdcData = sfdcSheet.getDataRange().getValues();
  
  // ヘッダー行を取得
  const supHeaders = supData[0];
  const sfdcHeaders = sfdcData[0];
  
  // SUP課題データから抽出したい列を定義
  const extractColumns = [
    "課題タイプ",
    "課題キー", 
    "要約",
    "報告者",
    "TS",
    "担当者",
    "TOKEN"
  ];
  
  // 抽出したい列のインデックスを取得
  const extractIndexes = extractColumns.map(col => {
    const index = supHeaders.indexOf(col);
    if (index === -1) {
      Logger.log(`警告: 列「${col}」が見つかりません`);
    }
    return index;
  }).filter(index => index !== -1);
  
  // TOKENの列のインデックスを取得
  const tokenIndex = supHeaders.indexOf("TOKEN");
  const tokenKeyIndex = sfdcHeaders.indexOf("トークンキー");
  const kadaiKeyIndex = supHeaders.indexOf("課題キー");
  
  if (tokenIndex === -1 || tokenKeyIndex === -1 || kadaiKeyIndex === -1) {
    Logger.log("必要なカラムが見つかりません");
    return;
  }
  
  // sfdcのデータをトークンキーでマッピング
  const tokenMap = {};
  for (let i = 1; i < sfdcData.length; i++) {
    const tokenKey = sfdcData[i][tokenKeyIndex];
    if (tokenKey) {
      tokenMap[tokenKey] = sfdcData[i];
    }
  }
  
  // JOINした結果を格納する配列
  const joinedData = [];
  
  // ヘッダー行を作成（抽出したい列のみ + sfdc情報 + コメント）
  const combinedHeaders = [
    ...extractColumns,
    "契約管理: エンドユーザ: 取引先名",
    "合計月額",
    "コメント"
  ];
  joinedData.push(combinedHeaders);
  
  // データをJOIN
  for (let i = 1; i < supData.length; i++) {
    const supRow = supData[i];
    const token = supRow[tokenIndex];
    const kadaiKey = supRow[kadaiKeyIndex];
    
    // 抽出したい列のデータのみを取得
    const extractedRow = extractIndexes.map(index => supRow[index]);
    
    // sfdcデータを追加
    if (token && tokenMap[token]) {
      // マッチするデータがある場合
      const sfdcRow = tokenMap[token];
      const torihikisaki = sfdcRow[sfdcHeaders.indexOf("契約管理: エンドユーザ: 取引先名")] || "";
      const gokei = sfdcRow[sfdcHeaders.indexOf("合計月額")] || "";
      
      extractedRow.push(torihikisaki, gokei);
    } else {
      // マッチするデータがない場合は空文字を追加
      extractedRow.push("", "");
    }
    
    // 既存のコメントを復元
    const existingComment = existingComments[kadaiKey] || "";
    extractedRow.push(existingComment);
    
    joinedData.push(extractedRow);
  }
  
  // 新しいシートを作成
  resultSheet = ss.insertSheet(resultSheetName);
  
  // データを書き込み
  if (joinedData.length > 0) {
    resultSheet.getRange(1, 1, joinedData.length, joinedData[0].length).setValues(joinedData);
    
    // ヘッダー行を太字にする
    resultSheet.getRange(1, 1, 1, joinedData[0].length).setFontWeight("bold");
    
    // コメント列の背景色を変更
    const commentColumnIndex = joinedData[0].length;
    resultSheet.getRange(1, commentColumnIndex, joinedData.length, 1).setBackground("#fff2cc");
    
    // 列幅を自動調整
    resultSheet.autoResizeColumns(1, joinedData[0].length - 1); // コメント列以外を自動調整
    
    // コメント列の横幅を広く設定（400ピクセル）
    resultSheet.setColumnWidth(commentColumnIndex, 400);
  }
  
  Logger.log(`JOIN処理が完了しました。既存のコメントも復元されています。`);
  Logger.log(`処理件数: ${joinedData.length - 1}件`);
  Logger.log(`復元されたコメント数: ${Object.keys(existingComments).length}件`);
}

// 毎朝7:30の自動実行トリガーを設定する関数
function setupDailyTrigger() {
  // 既存のトリガーを削除
  const triggers = ScriptApp.getProjectTriggers();
  triggers.forEach(trigger => {
    if (trigger.getHandlerFunction() === 'joinSupDataWithSfdcKeepComments') {
      ScriptApp.deleteTrigger(trigger);
    }
  });
  
  // 新しいトリガーを作成（毎日7:30）
  ScriptApp.newTrigger('joinSupDataWithSfdcKeepComments')
    .timeBased()
    .everyDays(1)
    .atHour(7)
    .nearMinute(30)
    .create();
  
  Logger.log('毎朝7:30のトリガーを設定しました');
}

// トリガーを削除する関数
function deleteDailyTrigger() {
  const triggers = ScriptApp.getProjectTriggers();
  let deletedCount = 0;
  
  triggers.forEach(trigger => {
    if (trigger.getHandlerFunction() === 'joinSupDataWithSfdcKeepComments') {
      ScriptApp.deleteTrigger(trigger);
      deletedCount++;
    }
  });
  
  Logger.log(`${deletedCount}個のトリガーを削除しました`);
}

// 現在のトリガー状況を確認する関数
function checkTriggers() {
  const triggers = ScriptApp.getProjectTriggers();
  
  Logger.log('=== 現在のトリガー一覧 ===');
  triggers.forEach((trigger, index) => {
    const func = trigger.getHandlerFunction();
    const source = trigger.getEventType();
    
    if (source === ScriptApp.EventType.CLOCK) {
      Logger.log(`${index + 1}. 関数: ${func}, 実行間隔: 毎日`);
    } else {
      Logger.log(`${index + 1}. 関数: ${func}, イベント: ${source}`);
    }
  });
  
  if (triggers.length === 0) {
    Logger.log('トリガーは設定されていません');
  }
}

// テスト用関数
function testJoinFunction() {
  Logger.log('テスト実行開始');
  try {
    joinSupDataWithSfdcKeepComments();
    Logger.log('テスト実行成功');
  } catch (error) {
    Logger.log(`テスト実行エラー: ${error.toString()}`);
  }
}