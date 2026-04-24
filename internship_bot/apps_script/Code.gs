function doPost(e) {
  try {
    if (!e || !e.postData || !e.postData.contents) {
      return jsonResponse_({ status: "error", message: "Empty request body" });
    }

    const payload = JSON.parse(e.postData.contents);
    const expectedToken = PropertiesService.getScriptProperties().getProperty("SHEETS_WEBHOOK_TOKEN") || "";

    if (expectedToken && String(payload.token || "") !== expectedToken) {
      return jsonResponse_({ status: "error", message: "Invalid token" });
    }

    const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
    if (!spreadsheet) {
      return jsonResponse_({ status: "error", message: "No active spreadsheet. Bind this script to your target Google Sheet." });
    }

    const operations = Array.isArray(payload.operations) ? payload.operations : [];
    const results = [];

    operations.forEach(function (operation) {
      results.push(runUpsertOperation_(spreadsheet, operation));
    });

    return jsonResponse_({ status: "ok", results: results });
  } catch (error) {
    return jsonResponse_({
      status: "error",
      message: String(error && error.message ? error.message : error),
    });
  }
}

function runUpsertOperation_(spreadsheet, operation) {
  const sheetName = String(operation.sheet || "").trim();
  const keyField = String(operation.keyField || "").trim();
  const headers = Array.isArray(operation.headers) ? operation.headers : [];
  const preserveFields = Array.isArray(operation.preserveFields) ? operation.preserveFields : [];
  const rows = Array.isArray(operation.rows) ? operation.rows : [];

  if (!sheetName || !keyField || headers.length === 0) {
    throw new Error("Operation must include sheet, keyField, and headers");
  }

  const sheet = ensureSheetWithHeaders_(spreadsheet, sheetName, headers);
  const existing = loadExistingRows_(sheet, headers, keyField);

  let updated = 0;
  const appendValues = [];

  rows.forEach(function (incomingRow) {
    const normalizedRow = normalizeRowObject_(incomingRow, headers);
    const key = String(normalizedRow[keyField] || "").trim();

    if (!key) {
      return;
    }

    if (Object.prototype.hasOwnProperty.call(existing.rowIndexByKey, key)) {
      const rowIndex = existing.rowIndexByKey[key];
      const oldRow = existing.rowsByKey[key] || {};

      preserveFields.forEach(function (field) {
        const oldValue = String(oldRow[field] || "").trim();
        const newValue = String(normalizedRow[field] || "").trim();
        if (oldValue && !newValue) {
          normalizedRow[field] = oldRow[field];
        }
      });

      sheet
        .getRange(rowIndex, 1, 1, headers.length)
        .setValues([headers.map(function (header) {
          return normalizeCellValue_(normalizedRow[header]);
        })]);
      updated += 1;
      return;
    }

    appendValues.push(headers.map(function (header) {
      return normalizeCellValue_(normalizedRow[header]);
    }));
  });

  let appended = 0;
  if (appendValues.length > 0) {
    const startRow = Math.max(sheet.getLastRow() + 1, 2);
    sheet.getRange(startRow, 1, appendValues.length, headers.length).setValues(appendValues);
    appended = appendValues.length;
  }

  return {
    sheet: sheetName,
    updated: updated,
    appended: appended,
  };
}

function ensureSheetWithHeaders_(spreadsheet, sheetName, headers) {
  let sheet = spreadsheet.getSheetByName(sheetName);
  if (!sheet) {
    sheet = spreadsheet.insertSheet(sheetName);
  }

  const currentHeaders = sheet.getRange(1, 1, 1, headers.length).getValues()[0];
  const headersMatch = headers.every(function (header, index) {
    return String(currentHeaders[index] || "") === String(header);
  });

  if (!headersMatch) {
    sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
  }

  return sheet;
}

function loadExistingRows_(sheet, headers, keyField) {
  const output = {
    rowIndexByKey: {},
    rowsByKey: {},
  };

  const lastRow = sheet.getLastRow();
  if (lastRow < 2) {
    return output;
  }

  const values = sheet.getRange(2, 1, lastRow - 1, headers.length).getValues();
  values.forEach(function (rowValues, index) {
    const rowObject = {};
    headers.forEach(function (header, colIndex) {
      rowObject[header] = rowValues[colIndex];
    });

    const key = String(rowObject[keyField] || "").trim();
    if (!key) {
      return;
    }

    output.rowIndexByKey[key] = index + 2;
    output.rowsByKey[key] = rowObject;
  });

  return output;
}

function normalizeRowObject_(incomingRow, headers) {
  const safeRow = incomingRow && typeof incomingRow === "object" ? incomingRow : {};
  const normalized = {};

  headers.forEach(function (header) {
    normalized[header] = Object.prototype.hasOwnProperty.call(safeRow, header)
      ? safeRow[header]
      : "";
  });

  return normalized;
}

function normalizeCellValue_(value) {
  if (value === null || value === undefined) {
    return "";
  }

  if (typeof value === "object") {
    return JSON.stringify(value);
  }

  return String(value);
}

function jsonResponse_(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
