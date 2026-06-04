import openpyxl

wb = openpyxl.load_workbook("UAT_sample.xlsx", data_only=True)
sheet = wb.active

headers = []
for cell in sheet[1]:
    headers.append(cell.value)
    
print("HEADERS:", headers)

row2 = []
for cell in sheet[2]:
    row2.append(cell.value)
    
print("ROW 2:", row2)
