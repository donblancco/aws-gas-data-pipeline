function fetchSlackMessagesDaily() {
  const token = "YOUR_SLACK_API_TOKEN";
  const channel = "C08DHM22ARM";
  const scriptProperties = PropertiesService.getScriptProperties();

  // 前回取得したタイムスタンプ（なければ24時間前）
  const lastTs = scriptProperties.getProperty("last_ts") || Math.floor((Date.now() - 24 * 60 * 60 * 1000) / 1000).toString();

  const url = `https://slack.com/api/conversations.history?channel=${channel}&oldest=${lastTs}&limit=1000`;

  const response = UrlFetchApp.fetch(url, {
    headers: {
      Authorization: `Bearer ${token}`
    }
  });

  const data = JSON.parse(response.getContentText());
  const messages = data.messages;

  if (!messages || messages.length === 0) return;

  // 日付の昇順に並び替え（古い順に追記）
  messages.sort((a, b) => parseFloat(a.ts) - parseFloat(b.ts));

  const sheet = SpreadsheetApp.openById("YOUR_SPREADSHEET_ID")
    .getSheetByName("TaskRunner");

  messages.forEach(msg => {
    const date = new Date(Number(msg.ts) * 1000);
    sheet.appendRow([date, msg.user || '', msg.text || '']);
  });

  // 最後のタイムスタンプを保存
  scriptProperties.setProperty("last_ts", messages[messages.length - 1].ts);
}
