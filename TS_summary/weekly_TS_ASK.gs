function countWeeklyFromDateDateColumn_final() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getActiveSheet();

  const dateColIndex = 7; // 「DATE-DATE」列は 7列目（G列）
  const numRows = sheet.getLastRow() - 1;
  if (numRows < 1) return;

  const dateValues = sheet.getRange(2, dateColIndex, numRows, 1).getValues();
  const weekMap = {};

  for (let i = 0; i < dateValues.length; i++) {
    const date = dateValues[i][0];
    if (!date || Object.prototype.toString.call(date) !== "[object Date]") continue;

    // 月曜日を週の開始日とする
    const monday = new Date(date);
    const day = monday.getDay(); // 0 = 日曜, 1 = 月曜
    const diff = (day === 0 ? -6 : 1 - day); // 日曜なら前の月曜、月〜土ならその週の月曜
    monday.setDate(monday.getDate() + diff);
    monday.setHours(0, 0, 0, 0); // 時刻リセット

    const key = Utilities.formatDate(monday, Session.getScriptTimeZone(), "yyyy-MM-dd");
    weekMap[key] = (weekMap[key] || 0) + 1;
  }

  // 出力用シート（週別集計）
  const outputSheetName = "週別集計";
  let outputSheet = ss.getSheetByName(outputSheetName);
  if (!outputSheet) {
    outputSheet = ss.insertSheet(outputSheetName);
  } else {
    outputSheet.clearContents();
  }

  outputSheet.appendRow(["週（開始日）", "件数"]);
  const sortedWeeks = Object.keys(weekMap).sort();
  sortedWeeks.forEach(week => {
    outputSheet.appendRow([week, weekMap[week]]);
  });
}
