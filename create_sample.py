import openpyxl

wb = openpyxl.Workbook()
sheet = wb.active
sheet.title = "Test Cases"

headers = [
    "Test Case ID", "Positive/Negative/Edge", "Test Case Scenario", 
    "Pre-Conditions", "Test Steps", "Test Step Detail", "Test Data", 
    "Expected Results", "Actual Results", "PASSED", "FAILED", "Dokumentasi"
]
sheet.append(headers)

tc1 = [
    "TC-WEB-01", "Positive", "Memverifikasi proses pembuatan Customer Offer",
    "Pengguna login ke Odoo", "Masuk ke modul Sales.\nPilih menu Customer Offers.",
    "Masuk ke modul Sales.\nPilih menu 'Customer Offers'.\nKlik tombol 'New'.\nPilih Customer 'AGUS SUTIKNO/PBG'.\nSet Order Date dengan tanggal saat ini.\nSet Valid Date menjadi '14 Days'.\nKlik tombol 'Add a line'.\nPada wizard 'Create Product Detail', pilih Type 'OSS'.\nPilih Product '[25555] PortoLady GLM-8 size 36-40 @48'.\nInput Qty '10'.\nKlik tombol 'Save & Close'.\nKlik tombol 'Confirm'.",
    "Customer: AGUS SUTIKNO/PBG\nType: OSS\nProduct: [25555] PortoLady GLM-8 size 36-40 @48\nQty: 10",
    "Status berubah menjadi 'Confirmed' setelah klik tombol 'Confirm'.",
    "", "", "", ""
]
sheet.append(tc1)

wb.save("sample_test_cases.xlsx")
print("sample_test_cases.xlsx created!")
